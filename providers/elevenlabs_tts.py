from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Tuple

import requests
from loguru import logger

from app.config import get_settings
from app.resilience.circuit import CircuitBreaker


class ElevenLabsError(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(f"{status_code} {code}: {detail}")


def _mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    visible = api_key[:4]
    return f"{visible}{'*' * max(len(api_key) - 4, 0)}"


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ALIASES_PATH = DATA_DIR / "voice_aliases.json"
LOCK_PATH = DATA_DIR / "voice_aliases.lock"
_DEFAULT_DOC = {"aliases": []}


class _FileLock:
    def __init__(self, path: Path, timeout: float = 5.0, interval: float = 0.1) -> None:
        self.path = path
        self.timeout = timeout
        self.interval = interval
        self._fd: Optional[int] = None

    def __enter__(self) -> "_FileLock":
        DATA_DIR.mkdir(exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.time() > deadline:
                    raise TimeoutError(f"Lock acquisition timed out: {self.path}")
                time.sleep(self.interval)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove lock file {}", self.path)


def _ensure_store() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not ALIASES_PATH.exists():
        with _FileLock(LOCK_PATH):
            if not ALIASES_PATH.exists():
                ALIASES_PATH.write_text(json.dumps(_DEFAULT_DOC), encoding="utf-8")


def _load_aliases() -> Dict[str, List[Dict[str, object]]]:
    _ensure_store()
    try:
        with ALIASES_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if not isinstance(data, dict) or "aliases" not in data:
                raise ValueError("Invalid alias store")
            return data
    except (json.JSONDecodeError, ValueError):
        logger.warning("Alias dosyası bozuk, sıfırlanıyor: {}", ALIASES_PATH)
        return _DEFAULT_DOC.copy()


def _write_aliases(doc: Dict[str, List[Dict[str, object]]]) -> None:
    temp_path = ALIASES_PATH.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, ALIASES_PATH)


def list_aliases() -> List[Dict[str, object]]:
    data = _load_aliases()
    return list(data.get("aliases", []))


def resolve_alias(alias: str) -> str:
    for entry in list_aliases():
        if entry.get("alias") == alias:
            voice_id = entry.get("voice_id")
            if voice_id:
                return str(voice_id)
    raise KeyError(alias)


def save_alias(alias: str, voice_id: str, name: Optional[str], source: str) -> Dict[str, object]:
    entry: Dict[str, object]
    with _FileLock(LOCK_PATH):
        data = _load_aliases()
        aliases = data.get("aliases", [])
        for existing in aliases:
            if existing.get("alias") == alias:
                existing["voice_id"] = voice_id
                if name is not None:
                    existing["name"] = name
                existing["source"] = source
                existing.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                entry = existing
                break
        else:
            entry = {
                "alias": alias,
                "voice_id": voice_id,
                "name": name or alias,
                "source": source,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            aliases.append(entry)
            data["aliases"] = aliases
        _write_aliases(data)
    logger.debug("Alias kaydedildi: {} -> {}", alias, voice_id)
    return entry


def delete_alias(alias: str) -> None:
    with _FileLock(LOCK_PATH):
        data = _load_aliases()
        aliases = data.get("aliases", [])
        new_aliases = [entry for entry in aliases if entry.get("alias") != alias]
        if len(new_aliases) == len(aliases):
            raise KeyError(alias)
        data["aliases"] = new_aliases
        _write_aliases(data)
    logger.debug("Alias silindi: {}", alias)


class ElevenLabsProvider:
    BASE_URL = "https://api.elevenlabs.io"

    def __init__(
        self,
        api_key: str,
        model_id: str,
        output_format: str,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.model_id = model_id
        self.output_format = output_format
        self._session = session or requests.Session()
        settings = get_settings()
        self._retries = max(int(settings.backoff_retries), 0)
        self._backoff_base = max(int(settings.backoff_base_ms), 0) / 1000.0
        self._backoff_max = max(int(settings.backoff_max_ms), 0) / 1000.0
        self._backoff_jitter_ms = max(int(settings.backoff_jitter_ms), 0)
        self._connect_timeout = max(float(settings.upstream_connect_timeout_sec), 0.1)
        self._read_timeout = max(float(settings.upstream_read_timeout_sec), 0.1)
        self._http_read_timeout = max(float(settings.http_read_timeout_sec), 0.1)
        self._http_write_timeout = max(float(settings.http_write_timeout_sec), 0.1)
        self._circuit = CircuitBreaker(
            failure_ratio=settings.cb_failure_ratio,
            window=settings.cb_window,
            cooldown_ms=settings.cb_cooldown_ms,
            half_open_max=settings.cb_half_open_max,
            name="elevenlabs",
        )
        self._last_stream_metadata: Dict[str, object] = {
            "retries": 0,
            "cb_state": self._circuit.state().value,
        }
        logger.debug(
            "Initialized ElevenLabsProvider (model={}, format={}, key={})",
            model_id,
            output_format,
            _mask_key(api_key),
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        url = f"{self.BASE_URL}{endpoint}"
        merged_headers = self._headers()
        if headers:
            merged_headers.update(headers)

        last_response: Optional[requests.Response] = None
        retries = self._retries
        timeout = kwargs.pop("timeout", None)
        if timeout is None:
            timeout = (self._connect_timeout, self._read_timeout)
        for attempt in range(retries + 1):
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=merged_headers,
                    timeout=timeout,
                    **kwargs,
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt < retries:
                    delay = self._compute_delay(attempt)
                    logger.warning(
                        "ElevenLabs %s retry %s/%s in %.3fs (exception=%s)",
                        endpoint,
                        attempt + 1,
                        retries,
                        delay,
                        exc.__class__.__name__,
                    )
                    if delay:
                        time.sleep(delay)
                    continue
                raise
            status = response.status_code
            if status in (429,) or 500 <= status < 600:
                if attempt < retries:
                    delay = self._compute_delay(attempt)
                    logger.warning(
                        "ElevenLabs {} retry {}/{} in {:.3f}s (status={})",
                        endpoint,
                        attempt + 1,
                        retries,
                        delay,
                        status,
                    )
                    response.close()
                    if delay:
                        time.sleep(delay)
                    continue
            last_response = response
            break
        if last_response is None:  # pragma: no cover
            raise ElevenLabsError(500, "UPSTREAM_ERROR", "No response from ElevenLabs")
        return last_response

    def _compute_delay(self, attempt: int) -> float:
        if self._backoff_base <= 0:
            return 0.0
        delay = self._backoff_base * (2 ** attempt)
        if self._backoff_max > 0:
            delay = min(delay, self._backoff_max)
        return self._circuit.jitter_delay(delay, self._backoff_jitter_ms)

    # region HTTP helpers
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "xi-api-key": self.api_key,
            "Accept": self._accept_header(self.output_format),
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _accept_header(fmt: str) -> str:
        if fmt.startswith("mp3"):
            return "audio/mpeg"
        if fmt.startswith("wav"):
            return "audio/wav"
        return "application/octet-stream"

    @staticmethod
    def _map_error(status_code: int) -> str:
        if status_code == 401:
            return "AUTH_FAILED"
        if status_code in (402, 429):
            return "RATE_LIMIT"
        if 400 <= status_code < 500:
            return "BAD_REQUEST"
        return "UPSTREAM_ERROR"

    def _raise_for_status(self, response: requests.Response) -> None:
        if response.ok:
            return
        code = self._map_error(response.status_code)
        detail = ""
        try:
            payload = response.json()
            detail = payload.get("detail") or payload.get("message") or str(payload)
        except Exception:
            detail = response.text or "Unknown error"
        raise ElevenLabsError(response.status_code, code, detail)

    # endregion

    def stream_tts(
        self,
        text: str,
        *,
        voice_id: str,
        voice_settings: Optional[Dict[str, object]] = None,
        language: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> Generator[bytes, None, None]:
        model = model_id or self.model_id
        fmt = output_format or self.output_format
        url = f"{self.BASE_URL}/v1/text-to-speech/{voice_id}/stream"

        payload: Dict[str, object] = {
            "text": text,
            "model_id": model,
            "output_format": fmt,
        }
        if language:
            payload["language"] = language
        if voice_settings:
            payload["voice_settings"] = voice_settings

        logger.debug(
            "Invoking ElevenLabs stream (voice={}, model={}, format={})",
            voice_id,
            model,
            fmt,
        )

        allowed, probe = self._circuit.allow_request()
        if not allowed:
            logger.info("## circuit elevenlabs deny request (state=%s)", self._circuit.state().value)
            raise ElevenLabsError(503, "UPSTREAM_UNAVAILABLE", "circuit open")

        headers = {
            "Content-Type": "application/json",
            "Accept": self._accept_header(fmt),
            "xi-api-key": self.api_key,
        }
        last_error: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                response = self._session.post(
                    f"{self.BASE_URL}/v1/text-to-speech/{voice_id}/stream",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=(self._connect_timeout, self._read_timeout),
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                self._circuit.record_failure("timeout", probe=probe)
                if attempt >= self._retries:
                    raise ElevenLabsError(504, "UPSTREAM_TIMEOUT", str(exc)) from exc
                delay = self._compute_delay(attempt)
                logger.warning(
                    "ElevenLabs stream timeout %s/%s, retrying in %.3fs (%s)",
                    attempt + 1,
                    self._retries,
                    delay,
                    exc.__class__.__name__,
                )
                if delay:
                    time.sleep(delay)
                continue

            status = response.status_code
            if status in (429,) or 500 <= status < 600:
                self._circuit.record_failure(f"http_{status}", probe=probe)
                if attempt >= self._retries:
                    try:
                        self._raise_for_status(response)
                    finally:
                        response.close()
                delay = self._compute_delay(attempt)
                logger.warning(
                    "ElevenLabs stream status %s (attempt %s/%s), retrying in %.3fs",
                    status,
                    attempt + 1,
                    self._retries,
                    delay,
                )
                response.close()
                if delay:
                    time.sleep(delay)
                continue

            try:
                self._raise_for_status(response)
            except ElevenLabsError:
                self._circuit.record_failure(f"http_{status}", probe=probe)
                response.close()
                raise

            self._circuit.record_success(probe=probe)
            self._last_stream_metadata = {
                "retries": attempt,
                "cb_state": self._circuit.state().value,
            }
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                response.close()
            break
        else:  # pragma: no cover - defensive, should not happen
            if last_error is not None:
                raise ElevenLabsError(503, "UPSTREAM_ERROR", str(last_error)) from last_error
            raise ElevenLabsError(503, "UPSTREAM_ERROR", "Failed to stream ElevenLabs audio")

    def list_voices(self) -> List[Dict[str, object]]:
        url = f"{self.BASE_URL}/v1/voices"
        response = self._request(
            "GET",
            "/v1/voices",
            headers={"Accept": "application/json"},
            timeout=30,
        )
        self._raise_for_status(response)
        data = response.json()
        voices = data.get("voices", [])
        parsed: List[Dict[str, object]] = []
        for item in voices:
            parsed.append(
                {
                    "voice_id": item.get("voice_id"),
                    "name": item.get("name"),
                    "labels": item.get("labels", {}),
                    "languages": item.get("languages", []),
                    "category": item.get("category"),
                }
            )
        return parsed

    def create_ivc(self, name: str, files: Iterable[str], description: str = "") -> str:
        url = f"{self.BASE_URL}/v1/voices/add"
        file_tuples = []
        for path in files:
            file_tuples.append(
                (
                    "files",
                    (
                        Path(path).name,
                        open(path, "rb"),
                        "audio/wav",
                    ),
                )
            )
        payload = {
            "name": name,
            "description": description or f"Cloned voice: {name}",
            "remove_background_noise": "false",  # ElevenLabs API parametresi
        }

        logger.info("Creating voice clone: name='{}'", name)

        try:
            response = self._request(
                "POST",
                "/v1/voices/add",
                headers=self._headers(),
                data=payload,
                files=file_tuples,
                timeout=300,
            )
        finally:
            for _, (_, handle, _) in file_tuples:
                handle.close()

        self._raise_for_status(response)
        data = response.json()
        logger.debug("ElevenLabs voice clone response: {}", data)
        voice_id = data.get("voice_id")
        if not voice_id:
            raise ElevenLabsError(500, "UPSTREAM_ERROR", "Voice ID missing in response")
        logger.info("Voice clone created successfully: voice_id={}", voice_id)
        return voice_id

    def delete_voice(self, voice_id: str) -> None:
        """Delete a voice from ElevenLabs."""
        logger.info("Deleting voice: voice_id={}", voice_id)
        
        response = self._request(
            "DELETE",
            f"/v1/voices/{voice_id}",
            headers=self._headers(),
            timeout=30,
        )
        
        self._raise_for_status(response)
        logger.info("Voice deleted successfully: voice_id={}", voice_id)

    def get_voice(self, voice_id: str) -> Dict[str, object]:
        """Get detailed voice information."""
        response = self._request(
            "GET",
            f"/v1/voices/{voice_id}",
            headers=self._headers(),
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    def edit_voice(self, voice_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, object]:
        """Edit voice metadata."""
        payload = {}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        
        response = self._request(
            "POST",
            f"/v1/voices/{voice_id}/edit",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    def get_models(self) -> List[Dict[str, object]]:
        """Get available TTS models."""
        response = self._request(
            "GET",
            "/v1/models",
            headers=self._headers(),
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    def get_user_subscription(self) -> Dict[str, object]:
        """Get user subscription info and quota."""
        response = self._request(
            "GET",
            "/v1/user/subscription",
            headers=self._headers(),
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    def get_history(self, page_size: int = 100) -> List[Dict[str, object]]:
        """Get generation history."""
        response = self._request(
            "GET",
            "/v1/history",
            headers=self._headers(),
            params={"page_size": page_size},
            timeout=30,
        )
        self._raise_for_status(response)
        data = response.json()
        return data.get("history", [])

    def delete_history_item(self, history_item_id: str) -> None:
        """Delete a history item."""
        response = self._request(
            "DELETE",
            f"/v1/history/{history_item_id}",
            headers=self._headers(),
            timeout=30,
        )
        self._raise_for_status(response)

    async def isolate_audio(
        self,
        audio_data: bytes,
        isolation_type: str = "voice_enhancement",
        noise_reduction: str = "high",
        output_format: str = "wav"
    ) -> bytes:
        """ElevenLabs Audio Isolation API'sini kullanarak ses dosyasını işler."""
        url = f"{self.BASE_URL}/v1/audio-isolation"

        payload = {
            "isolation_type": isolation_type,
            "noise_reduction": noise_reduction,
            "output_format": output_format
        }

        files = {"audio_file": ("audio.wav", audio_data, "audio/wav")}

        logger.debug(
            "ElevenLabs audio isolation çağrılıyor (type={}, noise={}, format={})",
            isolation_type,
            noise_reduction,
            output_format
        )

        allowed, probe = self._circuit.allow_request()
        if not allowed:
            logger.info("## circuit elevenlabs deny request (state=%s)", self._circuit.state().value)
            raise ElevenLabsError(503, "UPSTREAM_UNAVAILABLE", "circuit open")

        headers = {
            "xi-api-key": self.api_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                response = self._session.post(
                    url,
                    data=payload,
                    files=files,
                    headers=headers,
                    timeout=(self._connect_timeout, self._read_timeout),
                )
                self._raise_for_status(response)

                # İşlenmiş ses verisini döndür
                return response.content

            except Exception as exc:
                last_error = exc
                if attempt < self._retries:
                    logger.warning("ElevenLabs audio isolation retry %d: %s", attempt + 1, exc)
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("ElevenLabs audio isolation başarısız: %s", exc)

        if last_error:
            raise ElevenLabsError(500, "ISOLATION_FAILED", f"Audio isolation başarısız: {str(last_error)}")

        raise ElevenLabsError(500, "ISOLATION_FAILED", "Audio isolation işlemi başarısız oldu")

    async def transcribe_audio(
        self,
        audio_data: bytes,
        *,
        language: Optional[str] = None,
        model: str = "eleven_multilingual_v2",
        timestamps: bool = False,
    ) -> Dict[str, object]:
        """
        Transcribe audio using ElevenLabs Speech-to-Text API.

        Args:
            audio_data: Audio file bytes (WAV, MP3, M4A, FLAC supported)
            language: Optional language code (e.g., 'tr', 'en')
            model: STT model to use (default: eleven_multilingual_v2)
            timestamps: Whether to include word-level timestamps

        Returns:
            Dictionary with transcription results:
            {
                "text": str,
                "segments": List[Dict] (if timestamps=True),
                "language": str,
                "duration": float
            }
        """
        url = f"{self.BASE_URL}/v1/speech-to-text"

        # Prepare multipart form data
        files = {"audio": ("audio.wav", audio_data, "audio/wav")}

        data = {
            "model": model,
        }

        if language:
            data["language"] = language

        if timestamps:
            data["timestamps"] = "true"

        logger.debug(
            "ElevenLabs STT çağrılıyor (model={}, language={}, timestamps={})",
            model,
            language,
            timestamps
        )

        headers = {
            "xi-api-key": self.api_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                response = self._session.post(
                    url,
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=(self._connect_timeout, self._read_timeout),
                )
                self._raise_for_status(response)

                result = response.json()
                logger.debug("ElevenLabs STT başarılı: {} karakter", len(result.get("text", "")))
                return result

            except requests.exceptions.Timeout as exc:
                last_error = exc
                if attempt < self._retries:
                    delay = self._compute_delay(attempt)
                    logger.warning("ElevenLabs STT timeout retry %d/%d in %.3fs", attempt + 1, self._retries, delay)
                    if delay:
                        time.sleep(delay)
                else:
                    raise ElevenLabsError(504, "UPSTREAM_TIMEOUT", str(exc)) from exc

            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                if attempt < self._retries:
                    delay = self._compute_delay(attempt)
                    logger.warning("ElevenLabs STT connection error retry %d/%d in %.3fs", attempt + 1, self._retries, delay)
                    if delay:
                        time.sleep(delay)
                else:
                    raise ElevenLabsError(503, "CONNECTION_ERROR", str(exc)) from exc

            except ElevenLabsError:
                raise

            except Exception as exc:
                last_error = exc
                if attempt < self._retries:
                    logger.warning("ElevenLabs STT retry %d: %s", attempt + 1, exc)
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("ElevenLabs STT başarısız: %s", exc)

        if last_error:
            raise ElevenLabsError(500, "STT_FAILED", f"Speech-to-text başarısız: {str(last_error)}")

        raise ElevenLabsError(500, "STT_FAILED", "Speech-to-text işlemi başarısız oldu")

    def transcribe_audio_sync(
        self,
        audio_data: bytes,
        *,
        language: Optional[str] = None,
        model: str = "eleven_multilingual_v2",
        timestamps: bool = False,
    ) -> Dict[str, object]:
        """
        Synchronous version of transcribe_audio.

        Args:
            audio_data: Audio file bytes (WAV, MP3, M4A, FLAC supported)
            language: Optional language code (e.g., 'tr', 'en')
            model: STT model to use (default: eleven_multilingual_v2)
            timestamps: Whether to include word-level timestamps

        Returns:
            Dictionary with transcription results
        """
        url = f"{self.BASE_URL}/v1/speech-to-text"

        # Prepare multipart form data
        files = {"audio": ("audio.wav", audio_data, "audio/wav")}

        data = {
            "model": model,
        }

        if language:
            data["language"] = language

        if timestamps:
            data["timestamps"] = "true"

        logger.debug(
            "ElevenLabs STT (sync) çağrılıyor (model={}, language={}, timestamps={})",
            model,
            language,
            timestamps
        )

        headers = {
            "xi-api-key": self.api_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                response = self._session.post(
                    url,
                    data=data,
                    files=files,
                    headers=headers,
                    timeout=(self._connect_timeout, self._read_timeout),
                )
                self._raise_for_status(response)

                result = response.json()
                logger.debug("ElevenLabs STT (sync) başarılı: {} karakter", len(result.get("text", "")))
                return result

            except requests.exceptions.Timeout as exc:
                last_error = exc
                if attempt < self._retries:
                    delay = self._compute_delay(attempt)
                    logger.warning("ElevenLabs STT timeout retry %d/%d in %.3fs", attempt + 1, self._retries, delay)
                    if delay:
                        time.sleep(delay)
                else:
                    raise ElevenLabsError(504, "UPSTREAM_TIMEOUT", str(exc)) from exc

            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                if attempt < self._retries:
                    delay = self._compute_delay(attempt)
                    logger.warning("ElevenLabs STT connection error retry %d/%d in %.3fs", attempt + 1, self._retries, delay)
                    if delay:
                        time.sleep(delay)
                else:
                    raise ElevenLabsError(503, "CONNECTION_ERROR", str(exc)) from exc

            except ElevenLabsError:
                raise

            except Exception as exc:
                last_error = exc
                if attempt < self._retries:
                    logger.warning("ElevenLabs STT retry %d: %s", attempt + 1, exc)
                    time.sleep(2 ** attempt)
                else:
                    logger.error("ElevenLabs STT başarısız: %s", exc)

        if last_error:
            raise ElevenLabsError(500, "STT_FAILED", f"Speech-to-text başarısız: {str(last_error)}")

        raise ElevenLabsError(500, "STT_FAILED", "Speech-to-text işlemi başarısız oldu")

    @property
    def last_stream_metadata(self) -> Dict[str, object]:
        return dict(self._last_stream_metadata)
