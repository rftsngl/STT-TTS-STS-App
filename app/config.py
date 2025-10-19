from functools import lru_cache
from pathlib import Path
from typing import Literal
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_ENV_LOADED = False


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=False)
    else:
        load_dotenv(override=False)
    _ENV_LOADED = True


def _as_bool(value: str | int | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _as_float(value: str | float | int | None, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value.strip())
    except Exception:
        return default


class Settings(BaseModel):
    # CUDA/GPU support disabled - always use CPU
    device: Literal["auto", "cuda", "cpu"] = Field(default="cpu")
    bind_host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    max_duration_seconds: int = Field(default=900)
    default_language: str = Field(default="tr")
    default_timestamps: Literal["segments", "words"] = Field(default="segments")
    vad_aggressiveness: int = Field(default=2)
    endpoint_silence_ms: int = Field(default=350)
    partial_interval_ms: int = Field(default=500)
    # ElevenLabs API key - should be provided by user via environment variable
    # Hardcoded key removed for security - use XI_API_KEY environment variable
    xi_api_key: str = Field(default="")
    eleven_model_id: str = Field(default="eleven_flash_v2_5")
    eleven_output_format: str = Field(default="mp3_22050_32")
    eleven_default_voice_id: str = Field(default="")
    eleven_default_voice_alias: str = Field(default="")
    eleven_tts_language: str = Field(default="tr")
    min_utterance_ms: int = Field(default=700)
    min_chars: int = Field(default=6)
    noise_suppressor: Literal["off", "spectral", "rnnoise"] = Field(default="off")
    ns_strength: Literal["low", "medium", "high"] = Field(default="medium")
    log_metrics: bool = Field(default=True)
    metrics_jl_path: str = Field(default="app/logs/metrics.jl")
    terms_file: str = Field(default="data/terms.json")
    terms_apply_to_partials: bool = Field(default=False)
    terms_case_sensitive: bool = Field(default=False)
    terms_max_entries: int = Field(default=10000)
    terms_enable_regex: bool = Field(default=True)
    terms_enable_fuzzy: bool = Field(default=True)
    terms_fuzzy_max_dist: int = Field(default=1)
    metrics_summary_max_rows: int = Field(default=200000)
    target_total_ms: float = Field(default=250.0)
    target_stt_ms: float = Field(default=120.0)
    target_tts_ms: float = Field(default=120.0)
    enable_security: bool = Field(default=False)
    api_key: str = Field(default="")
    max_upload_mb: int = Field(default=20)
    max_body_mb: int = Field(default=25)
    rate_limit_global_rpm: int = Field(default=300)
    rate_limit_ip_rpm: int = Field(default=150)
    rate_bucket_burst: float = Field(default=2.0)
    security_protect_all: bool = Field(default=True)
    http_read_timeout_sec: int = Field(default=30)
    http_write_timeout_sec: int = Field(default=60)
    upstream_connect_timeout_sec: int = Field(default=6)
    upstream_read_timeout_sec: int = Field(default=25)

    # STT Provider Configuration - Faster-Whisper disabled, only ElevenLabs supported
    stt_provider: Literal["elevenlabs", "faster-whisper"] = Field(default="elevenlabs")
    elevenlabs_stt_api_key: str = Field(default="")
    stt_fallback_enabled: bool = Field(default=False)
    stt_fallback_provider: Literal["elevenlabs", "faster-whisper"] = Field(default="elevenlabs")

    # Database Configuration
    database_path: str = Field(default="./data/speech_app.db")
    encryption_key: str = Field(default="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()
    return Settings(
        device=os.environ.get("DEVICE", "cpu"),  # CUDA disabled, always use CPU
        bind_host=os.environ.get("BIND_HOST", "127.0.0.1"),
        port=os.environ.get("PORT", "8000"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        max_duration_seconds=os.environ.get("MAX_DURATION_SECONDS", "900"),
        default_language=os.environ.get("DEFAULT_LANGUAGE", "tr"),
        default_timestamps=os.environ.get("DEFAULT_TIMESTAMPS", "segments"),
        vad_aggressiveness=os.environ.get("VAD_AGGRESSIVENESS", "2"),
        endpoint_silence_ms=os.environ.get("ENDPOINT_SILENCE_MS", "350"),
        partial_interval_ms=os.environ.get("PARTIAL_INTERVAL_MS", "500"),
        xi_api_key=os.environ.get("XI_API_KEY", ""),
        eleven_model_id=os.environ.get("ELEVEN_MODEL_ID", "eleven_flash_v2_5"),
        eleven_output_format=os.environ.get("ELEVEN_OUTPUT_FORMAT", "mp3_22050_32"),
        eleven_default_voice_id=os.environ.get("ELEVEN_DEFAULT_VOICE_ID", ""),
        eleven_default_voice_alias=os.environ.get("ELEVEN_DEFAULT_VOICE_ALIAS", ""),
        eleven_tts_language=os.environ.get("ELEVEN_TTS_LANGUAGE", "tr"),
        min_utterance_ms=os.environ.get("MIN_UTTERANCE_MS", "700"),
        min_chars=os.environ.get("MIN_CHARS", "6"),
        noise_suppressor=os.environ.get("NOISE_SUPPRESSOR", "off"),
        ns_strength=os.environ.get("NS_STRENGTH", "medium"),
        log_metrics=_as_bool(os.environ.get("LOG_METRICS"), True),
        metrics_jl_path=os.environ.get("METRICS_JL_PATH", "app/logs/metrics.jl"),
        terms_file=os.environ.get("TERMS_FILE", "data/terms.json"),
        terms_apply_to_partials=_as_bool(os.environ.get("TERMS_APPLY_TO_PARTIALS"), False),
        terms_case_sensitive=_as_bool(os.environ.get("TERMS_CASE_SENSITIVE"), False),
        terms_max_entries=os.environ.get("TERMS_MAX_ENTRIES", "10000"),
        terms_enable_regex=_as_bool(os.environ.get("TERMS_ENABLE_REGEX"), True),
        terms_enable_fuzzy=_as_bool(os.environ.get("TERMS_ENABLE_FUZZY"), True),
        terms_fuzzy_max_dist=os.environ.get("TERMS_FUZZY_MAX_DIST", "1"),
        metrics_summary_max_rows=os.environ.get("METRICS_SUMMARY_MAX_ROWS", "200000"),
        target_total_ms=os.environ.get("TARGET_TOTAL_MS", "250"),
        target_stt_ms=os.environ.get("TARGET_STT_MS", "120"),
        target_tts_ms=os.environ.get("TARGET_TTS_MS", "120"),
        enable_security=_as_bool(os.environ.get("ENABLE_SECURITY"), False),
        api_key=os.environ.get("API_KEY", ""),
        max_upload_mb=os.environ.get("MAX_UPLOAD_MB", "20"),
        max_body_mb=os.environ.get("MAX_BODY_MB", "25"),
        rate_limit_global_rpm=os.environ.get("RATE_LIMIT_GLOBAL_RPM", "300"),
        rate_limit_ip_rpm=os.environ.get("RATE_LIMIT_IP_RPM", "150"),
        rate_bucket_burst=os.environ.get("RATE_BUCKET_BURST", "2.0"),
        security_protect_all=_as_bool(os.environ.get("SECURITY_PROTECT_ALL"), True),
        http_read_timeout_sec=os.environ.get("HTTP_READ_TIMEOUT_SEC", "30"),
        http_write_timeout_sec=os.environ.get("HTTP_WRITE_TIMEOUT_SEC", "60"),
        upstream_connect_timeout_sec=os.environ.get("UPSTREAM_CONNECT_TIMEOUT_SEC", "6"),
        upstream_read_timeout_sec=os.environ.get("UPSTREAM_READ_TIMEOUT_SEC", "25"),
        stt_provider=os.environ.get("STT_PROVIDER", "elevenlabs"),  # Faster-Whisper disabled
        elevenlabs_stt_api_key=os.environ.get("ELEVENLABS_STT_API_KEY", ""),
        stt_fallback_enabled=_as_bool(os.environ.get("STT_FALLBACK_ENABLED"), False),  # Fallback disabled
        stt_fallback_provider=os.environ.get("STT_FALLBACK_PROVIDER", "elevenlabs"),
        database_path=os.environ.get("DATABASE_PATH", "./data/speech_app.db"),
        encryption_key=os.environ.get("ENCRYPTION_KEY", ""),
    )
