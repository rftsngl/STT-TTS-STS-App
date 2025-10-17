from __future__ import annotations

import asyncio
import base64
import difflib
import json
import os
import secrets
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool

from dotenv import dotenv_values

from app.config import get_settings
from app.security.api_key import is_enabled, mask as mask_key, verify_api_key
from app.terms_api import _parse_csv_entries, _parse_json_entries
from app.terms_store import get_terms_store
from app.voice_utils import get_eleven_provider
from providers.elevenlabs_tts import ElevenLabsError, save_alias


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
REPORTS_DIR = REPO_ROOT / "reports"
UI_RUNS_DIR = REPORTS_DIR / "ui_runs"
TOOLS_DIR = REPO_ROOT / "tools"
RESTART_SCRIPT = TOOLS_DIR / "restart_app.ps1"

ENV_BACKUP_TEMPLATE = ".env.{timestamp}.bak"
CONFIG_LOCK = asyncio.Lock()
MAX_BACKUPS = 50
MAX_LOG_LINES = 400

CONFIG_EXPLICIT_KEYS = {
    "ELEVEN_DEFAULT_VOICE_ALIAS",
    "ELEVEN_DEFAULT_VOICE_ID",
    "ENABLE_SECURITY",
    "VAD_AGGRESSIVENESS",
    "ENDPOINT_SILENCE_MS",
    "MIN_UTTERANCE_MS",
    "MIN_CHARS",
    "API_KEY",
    "XI_API_KEY",
    "RATE_BUCKET_BURST",
    "BACKOFF_RETRIES",
    "BACKOFF_BASE_MS",
    "BACKOFF_MAX_MS",
    "BACKOFF_JITTER_MS",
    "CB_FAILURE_RATIO",
    "CB_WINDOW",
    "CB_COOLDOWN_MS",
    "CB_HALF_OPEN_MAX",
    "HTTP_READ_TIMEOUT_SEC",
    "HTTP_WRITE_TIMEOUT_SEC",
    "UPSTREAM_CONNECT_TIMEOUT_SEC",
    "UPSTREAM_READ_TIMEOUT_SEC",
}

CONFIG_PREFIX_WHITELIST = ("RATE_LIMIT_", "RESILIENCE_")


SENSITIVE_KEYS = {"API_KEY", "XI_API_KEY"}
BOOLEAN_KEYS = {"ENABLE_SECURITY"}

RESILIENCE_KEYS = {
    "CB_FAILURE_RATIO",
    "CB_WINDOW",
    "CB_COOLDOWN_MS",
    "CB_HALF_OPEN_MAX",
    "BACKOFF_RETRIES",
    "BACKOFF_BASE_MS",
    "BACKOFF_MAX_MS",
    "BACKOFF_JITTER_MS",
}

LIMIT_KEYS = [
    "RATE_LIMIT_GLOBAL_RPM",
    "RATE_LIMIT_IP_RPM",
    "RATE_BUCKET_BURST",
]


def _collect_limit_entries(settings) -> List[Dict[str, Any]]:
    env_map = _filter_allowed(_read_env_map())
    entries: List[Dict[str, Any]] = []
    for key in LIMIT_KEYS:
        env_value = env_map.get(key)
        effective_value = getattr(settings, key.lower(), None)
        entries.append(
            {
                "key": key,
                "value": env_value or "",
                "effective": effective_value,
                "masked": _display_value(key, env_value),
            }
        )
    return entries


def _collect_resilience_entries(settings) -> List[Dict[str, Any]]:
    env_map = _filter_allowed(_read_env_map())
    entries: List[Dict[str, Any]] = []
    for key in sorted(RESILIENCE_KEYS):
        env_value = env_map.get(key)
        effective_value = getattr(settings, key.lower(), None)
        entries.append(
            {
                "key": key,
                "value": env_value or "",
                "effective": effective_value,
            }
        )
    return entries


router = APIRouter(prefix="/ui", tags=["ui"])


def _ensure_dirs() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    UI_RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _mask(value: Optional[str]) -> str:
    if not value:
        return ""
    return mask_key(value)


def _tail_lines(path: Path, limit: int = MAX_LOG_LINES) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()[-limit:]
    masked_lines: List[str] = []
    settings = get_settings()
    secrets_to_strip = [value for value in (settings.api_key, settings.xi_api_key) if value]
    for line in lines:
        cleaned = line.rstrip("\n")
        for secret in secrets_to_strip:
            cleaned = cleaned.replace(secret, _mask(secret))
        masked_lines.append(cleaned)
    return masked_lines


def _python_executable() -> str:
    candidates = [
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return os.environ.get("PYTHON", "") or "python"


def _powershell_command(script: Path) -> List[str]:
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]


def _run_command(name: str, command: Sequence[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    _ensure_dirs()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = UI_RUNS_DIR / f"{name}_{timestamp}.log"
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    import subprocess

    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            list(command),
            cwd=str(REPO_ROOT),
            env=merged_env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "log_file": _relative(log_path),
        "log_tail": _tail_lines(log_path),
    }


async def _run_subprocess(name: str, command: Sequence[str], env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return await run_in_threadpool(_run_command, name, command, env)


async def _call_internal(
    request: Request,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    data: Any = None,
    params: Mapping[str, Any] | None = None,
    files: Any = None,
    admin: bool = False,
    timeout: float = 60.0,
) -> httpx.Response:
    settings = get_settings()
    headers: Dict[str, str] = {}
    if is_enabled(settings) and settings.api_key:
        headers["X-API-Key"] = settings.api_key
    
    # Pass ElevenLabs API key from request headers
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    if elevenlabs_key:
        headers["X-ElevenLabs-Key"] = elevenlabs_key
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://internal", timeout=timeout) as client:
        response = await client.request(
            method,
            path,
            headers=headers,
            json=json_body,
            data=data,
            params=params,
            files=files,
        )
    return response


def _require_api_key_header(request: Request) -> None:
    # API key protection disabled
    pass


def _has_valid_admin_header(request: Request) -> bool:
    return False


def _require_admin_key(request: Request) -> None:
    # Admin functionality now accessible without API key
    pass


def _admin_mode(settings) -> bool:
    return False


def _is_allowed_key(key: str) -> bool:
    if key in CONFIG_EXPLICIT_KEYS:
        return True
    for prefix in CONFIG_PREFIX_WHITELIST:
        if key.startswith(prefix):
            return True
    return False


def _normalize_env_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    needs_quotes = any(ch in value for ch in ' \t#"\n\r')
    if needs_quotes:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _extract_key(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):]
    if "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    return key or None


def _read_env_text() -> str:
    if not ENV_PATH.exists():
        return ""
    return ENV_PATH.read_text(encoding="utf-8")


def _read_env_map() -> Dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    values = dotenv_values(ENV_PATH)
    result: Dict[str, str] = {}
    for key, value in values.items():
        if value is None:
            continue
        result[key] = str(value)
    return result


def _filter_allowed(env_map: Mapping[str, str]) -> Dict[str, str]:
    return {key: value for key, value in env_map.items() if _is_allowed_key(key)}


def _render_env_text(original: str, updated_map: Mapping[str, str], keys_to_update: Iterable[str]) -> str:
    keys = {key for key in keys_to_update if key in updated_map}
    if not keys:
        return original
    lines = original.splitlines()
    new_lines: List[str] = []
    written: set[str] = set()
    for line in lines:
        key = _extract_key(line)
        if key and key in keys:
            new_lines.append(f"{key}={_format_env_value(updated_map[key])}")
            written.add(key)
        else:
            new_lines.append(line)
    for key in sorted(keys):
        if key not in written:
            new_lines.append(f"{key}={_format_env_value(updated_map[key])}")
    content = "\n".join(new_lines).rstrip("\n")
    return f"{content}\n" if content else ""


def _display_value(key: str, value: Optional[str]) -> str:
    if value is None:
        return ""
    if key in SENSITIVE_KEYS and value:
        return _mask(value)
    return str(value)


def _diff_entries(current: Mapping[str, str], updated: Mapping[str, str], keys: Iterable[str]) -> Tuple[List[Dict[str, Any]], bool]:
    summary: List[Dict[str, Any]] = []
    changed = False
    for key in sorted(set(keys)):
        if not _is_allowed_key(key):
            continue
        before = current.get(key, "")
        after = updated.get(key, "")
        is_changed = before != after
        if is_changed:
            changed = True
        summary.append(
            {
                "key": key,
                "before": _display_value(key, before),
                "after": _display_value(key, after),
                "changed": is_changed,
            }
        )
    return summary, changed


def _create_env_backup() -> Optional[Path]:
    if not ENV_PATH.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    destination = ENV_PATH.with_name(ENV_BACKUP_TEMPLATE.format(timestamp=timestamp))
    shutil.copy2(ENV_PATH, destination)
    return destination


def _list_env_backups(limit: int = MAX_BACKUPS) -> List[Dict[str, Any]]:
    backups: List[Dict[str, Any]] = []
    for path in sorted(ENV_PATH.parent.glob(".env.*.bak"), key=lambda item: item.name, reverse=True)[:limit]:
        stat = path.stat()
        backups.append(
            {
                "name": path.name,
                "path": _relative(path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return backups


def _write_atomic_env(content: str) -> None:
    temp_path = ENV_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(temp_path, ENV_PATH)


def _clear_settings_cache() -> None:
    cache_clear = getattr(get_settings, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def _config_preview_sync(updates: Mapping[str, Any]) -> Dict[str, Any]:
    filtered = {key: _normalize_env_value(value) for key, value in updates.items() if _is_allowed_key(key)}
    base_text = _read_env_text()
    current_map = _read_env_map()
    target_map = current_map.copy()
    target_map.update(filtered)
    summary, has_changes = _diff_entries(current_map, target_map, filtered.keys())
    new_text = _render_env_text(base_text, target_map, filtered.keys())
    diff_lines = list(
        difflib.unified_diff(
            base_text.splitlines(),
            new_text.splitlines(),
            fromfile=".env[current]",
            tofile=".env[proposed]",
            lineterm="",
        )
    )
    return {
        "changes": summary,
        "has_changes": has_changes,
        "diff": diff_lines,
    }


def _config_apply_sync(updates: Mapping[str, Any], create_backup: bool = True) -> Dict[str, Any]:
    filtered = {key: _normalize_env_value(value) for key, value in updates.items() if _is_allowed_key(key)}
    if not filtered:
        return {"applied": False, "reason": "NO_ALLOWED_KEYS"}
    base_text = _read_env_text()
    current_map = _read_env_map()
    target_map = current_map.copy()
    target_map.update(filtered)
    summary, has_changes = _diff_entries(current_map, target_map, filtered.keys())
    if not has_changes:
        return {"applied": False, "reason": "NO_CHANGES", "changes": summary}
    backup_path: Optional[Path] = None
    if create_backup and ENV_PATH.exists():
        backup_path = _create_env_backup()
    new_text = _render_env_text(base_text, target_map, filtered.keys())
    _write_atomic_env(new_text)
    _clear_settings_cache()
    get_settings()
    diff_lines = list(
        difflib.unified_diff(
            base_text.splitlines(),
            new_text.splitlines(),
            fromfile=".env[before]",
            tofile=".env[after]",
            lineterm="",
        )
    )
    return {
        "applied": True,
        "changes": summary,
        "backup": _relative(backup_path) if backup_path else None,
        "diff": diff_lines,
    }


def _config_read_sync(admin_unlocked: bool) -> Dict[str, Any]:
    settings = get_settings()
    env_map = _filter_allowed(_read_env_map())
    allowed: set[str] = set(env_map.keys()) | set(CONFIG_EXPLICIT_KEYS)
    field_names = []
    try:
        field_names = list(getattr(settings, "__fields__").keys())  # type: ignore[attr-defined]
    except AttributeError:
        pass
    for name in field_names:
        env_key = name.upper()
        if _is_allowed_key(env_key):
            allowed.add(env_key)
    entries: List[Dict[str, Any]] = []
    for key in sorted(allowed):
        if not _is_allowed_key(key):
            continue
        env_value = env_map.get(key)
        attr_name = key.lower()
        effective_value = getattr(settings, attr_name, None)
        value_field = ""
        if env_value is not None and key not in SENSITIVE_KEYS:
            value_field = str(env_value)
        entry: Dict[str, Any] = {
            "key": key,
            "value": value_field,
            "masked": _display_value(key, env_value),
            "effective": _display_value(key, _normalize_env_value(effective_value) if effective_value is not None else None),
            "from_env": env_value is not None,
            "is_sensitive": key in SENSITIVE_KEYS,
            "editable": admin_unlocked,
        }
        entries.append(entry)
    last_modified = None
    if ENV_PATH.exists():
        last_modified = datetime.fromtimestamp(ENV_PATH.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "entries": entries,
        "last_modified": last_modified,
        "backups": _list_env_backups(),
    }


async def _safe_internal_json(
    request: Request,
    method: str,
    path: str,
    *,
    params: Optional[Mapping[str, Any]] = None,
    json_body: Any = None,
    data: Any = None,
    admin: bool = False,
    timeout: float = 30.0,
) -> Optional[Any]:
    try:
        response = await _call_internal(
            request,
            method,
            path,
            params=params,
            json_body=json_body,
            data=data,
            admin=admin,
            timeout=timeout,
        )
    except Exception:
        return None
    if response.status_code >= 400:
        try:
            return response.json()
        except Exception:
            return {"error": response.status_code, "detail": response.text}
    try:
        return response.json()
    except Exception:
        return None


def _reports_summary() -> Dict[str, Optional[str]]:
    summary: Dict[str, Optional[str]] = {}
    status_json = REPORTS_DIR / "status_report.json"
    status_md = REPORTS_DIR / "status_report.md"
    probe_matrix = REPORTS_DIR / "probe_matrix.md"
    tests_junit = REPORTS_DIR / "tests" / "junit.xml"
    bench_summary = REPORTS_DIR / "bench" / "summary.md"
    summary["status_json"] = _relative(status_json) if status_json.exists() else None
    summary["status_markdown"] = _relative(status_md) if status_md.exists() else None
    summary["probe_matrix"] = _relative(probe_matrix) if probe_matrix.exists() else None
    summary["tests_junit"] = _relative(tests_junit) if tests_junit.exists() else None
    summary["bench_summary"] = _relative(bench_summary) if bench_summary.exists() else None
    return summary


def _parse_terms_upload(filename: str, raw: bytes) -> List[Dict[str, Any]]:
    if not raw:
        return []
    text = raw.decode("utf-8-sig")
    lowered = (filename or "").lower()
    if lowered.endswith(".json"):
        return _parse_json_entries(text)
    if lowered.endswith(".csv"):
        return _parse_csv_entries(text)
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return _parse_json_entries(text)
    return _parse_csv_entries(text)


def _terms_import_preview_sync(filename: str, raw: bytes) -> Dict[str, Any]:
    entries = _parse_terms_upload(filename, raw)
    store = get_terms_store()
    current_entries = store.list_entries()
    normalize = getattr(store, "_normalize_src")
    current_map = {normalize(item.get("src", "")): item for item in current_entries if item.get("src")}
    added: List[Dict[str, Any]] = []
    updated: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []
    for entry in entries:
        src = entry.get("src", "")
        key = normalize(src) if src else ""
        payload = {k: entry.get(k) for k in ("src", "dst", "type", "priority", "active")}
        existing = current_map.get(key)
        if not existing:
            added.append(payload)
        else:
            comparable = {k: existing.get(k) for k in ("src", "dst", "type", "priority", "active")}
            if comparable == payload:
                unchanged.append(payload)
            else:
                updated.append({"before": comparable, "after": payload})
    return {
        "total": len(entries),
        "added": len(added),
        "updated": len(updated),
        "unchanged": len(unchanged),
        "sample_added": added[:5],
        "sample_updated": updated[:5],
        "sample_unchanged": unchanged[:5],
    }


async def _status_payload(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    admin_mode_flag = _admin_mode(settings)
    admin_unlocked = _has_valid_admin_header(request)
    partial_errors: List[str] = []
    health = await _safe_internal_json(request, "GET", "/health")
    metrics = await _safe_internal_json(
        request,
        "GET",
        "/diag/metrics/summary",
        params={"window": "5m"},
    )
    terms_data: Any
    if admin_mode_flag and not admin_unlocked:
        terms_data = {"error": "ADMIN_REQUIRED"}
    else:
        terms_response = await _safe_internal_json(request, "GET", "/terms", admin=admin_unlocked or admin_mode_flag)
        if isinstance(terms_response, dict) and "error" in terms_response:
            terms_data = terms_response
        elif terms_response is None and not admin_mode_flag:
            store = get_terms_store()
            terms_data = {"entries": store.list_entries(), "stats": store.stats()}
        elif terms_response is None:
            terms_data = {"error": "unavailable"}
        else:
            terms_data = terms_response
    voices_resp = await _safe_internal_json(request, "GET", "/voices")
    aliases_resp = await _safe_internal_json(request, "GET", "/voices/aliases")
    voices_payload = {
        "voices": voices_resp.get("voices", []) if isinstance(voices_resp, dict) else [],
        "aliases": aliases_resp.get("aliases", []) if isinstance(aliases_resp, dict) else [],
    }
    health_payload = health or {"status": "unknown"}
    compute_info = {
        "configured": settings.device,
        "configured_source": health_payload.get("configured_device", settings.device),
        "effective": health_payload.get("device"),
        "fallback_reason": health_payload.get("device_fallback_reason"),
        "torch_cuda": bool(health_payload.get("torch_cuda")),
        "ctranslate2_cuda": bool(health_payload.get("ctranslate2_cuda")),
        "cuda_device_count": int(health_payload.get("cuda_device_count") or 0),
    }
    if not isinstance(voices_resp, dict):
        partial_errors.append("voices")
    if not isinstance(terms_data, dict) or terms_data.get("error"):
        partial_errors.append("terms")
    reports = _reports_summary()
    status_report = _read_json(REPORTS_DIR / "status_report.json")

    security_info = {
        "enable_security": settings.enable_security,
        "api_key_present": bool(settings.api_key),
        "api_key_masked": _mask(settings.api_key),
        "xi_api_key_present": bool(settings.xi_api_key),
        "xi_api_key_masked": _mask(settings.xi_api_key),
    }

    default_voice = {
        "alias": settings.eleven_default_voice_alias,
        "voice_id": settings.eleven_default_voice_id,
    }

    limits_info = {
        "rate_limit_global_rpm": settings.rate_limit_global_rpm,
        "rate_limit_ip_rpm": settings.rate_limit_ip_rpm,
        "rate_bucket_burst": settings.rate_bucket_burst,
    }


    resilience_info = {
        "cb_failure_ratio": settings.cb_failure_ratio,
        "cb_window": settings.cb_window,
        "cb_cooldown_ms": settings.cb_cooldown_ms,
        "cb_half_open_max": settings.cb_half_open_max,
        "backoff_retries": settings.backoff_retries,
        "backoff_base_ms": settings.backoff_base_ms,
        "backoff_max_ms": settings.backoff_max_ms,
        "backoff_jitter_ms": settings.backoff_jitter_ms,
    }

    cb_counts = {}
    if isinstance(metrics, dict):
        counts = metrics.get("cb_state_counts")
        if isinstance(counts, dict):
            cb_counts = counts

    config_data: Optional[Dict[str, Any]] = None
    try:
        config_data = await run_in_threadpool(_config_read_sync, admin_unlocked)
    except Exception:
        partial_errors.append("config")

    try:
        limit_entries = _collect_limit_entries(settings)
    except Exception:
        limit_entries = []
        partial_errors.append("limits")

    try:
        resilience_entries = _collect_resilience_entries(settings)
    except Exception:
        resilience_entries = []
        partial_errors.append("resilience")

    return {
        "generated_at": _now_iso(),
        "admin_mode": admin_mode_flag,
        "admin_unlocked": admin_unlocked,
        "security": security_info,
        "default_voice": default_voice,
        "limits": limits_info,
        "resilience": resilience_info,
        "cb_state_counts": cb_counts,
        "health": health_payload,
        "compute": compute_info,
        "metrics": metrics,
        "terms": terms_data,
        "voices": voices_payload,
        "reports": reports,
        "status_report": status_report,
        "config_data": config_data,
        "limits_data": {
            "entries": limit_entries,
            "admin_mode": admin_mode_flag,
            "admin_unlocked": admin_unlocked,
        },
        "resilience_data": {
            "entries": resilience_entries,
            "admin_mode": admin_mode_flag,
            "admin_unlocked": admin_unlocked,
        },
        "partial_errors": partial_errors,
    }


async def _collect_audio_bytes(response: httpx.Response) -> bytes:
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = {"detail": response.text or "Upstream error"}
        raise HTTPException(status_code=response.status_code, detail=detail)
    chunks: List[bytes] = []
    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
    return b"".join(chunks)


async def _execute_runner(action: str) -> Dict[str, Any]:
    action = action.lower()
    if action == "probe":
        python = _python_executable()
        script = REPO_ROOT / "tools" / "probe.py"
        if not script.exists():
            raise HTTPException(status_code=404, detail={"code": "MISSING_SCRIPT", "message": "tools/probe.py not found"})
        result = await _run_subprocess("probe", [python, str(script)])
        result["artifacts"] = {
            "capabilities_report": _relative(REPORTS_DIR / "capabilities_report.json"),
            "probe_matrix": _relative(REPORTS_DIR / "probe_matrix.md"),
        }
        return result
    if action == "tests":
        script = REPO_ROOT / "tools" / "run_tests.ps1"
        if script.exists():
            command = _powershell_command(script)
        else:
            python = _python_executable()
            command = [python, "-m", "pytest", "-q"]
        result = await _run_subprocess("tests", command)
        result["artifacts"] = {
            "junit": _relative(REPORTS_DIR / "tests" / "junit.xml"),
            "html": _relative(REPORTS_DIR / "tests" / "report.html"),
        }
        return result
    if action == "bench":
        script = REPO_ROOT / "tools" / "run_benchmarks.ps1"
        if script.exists():
            command = _powershell_command(script)
        else:
            python = _python_executable()
            command = [python, "tools/bench_http.py"]
        result = await _run_subprocess("bench", command)
        result["artifacts"] = {
            "summary": _relative(REPORTS_DIR / "bench" / "summary.md"),
        }
        return result
    if action == "status":
        python = _python_executable()
        script = REPO_ROOT / "tools" / "status_report.py"
        if not script.exists():
            raise HTTPException(status_code=404, detail={"code": "MISSING_SCRIPT", "message": "tools/status_report.py not found"})
        result = await _run_subprocess("status", [python, str(script)])
        result["artifacts"] = {
            "status_json": _relative(REPORTS_DIR / "status_report.json"),
            "status_markdown": _relative(REPORTS_DIR / "status_report.md"),
        }
        return result
    raise HTTPException(status_code=404, detail={"code": "UNKNOWN_ACTION", "message": f"Runner '{action}' is not supported"})


@router.get("", response_class=HTMLResponse)
async def ui_root() -> str:
    return _html_page()


@router.get("/login", response_class=HTMLResponse)
async def ui_login() -> str:
    return _html_page()


@router.post("/api/auth/login")
async def api_login(request: Request) -> Dict[str, Any]:
    """API key ile giriş yapma endpoint'i"""
    payload = await request.json()
    api_key = payload.get("api_key", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail={"code": "MISSING_KEY", "message": "API key gerekli"})
    
    # API key'i doğrula
    settings = get_settings()
    if not verify_api_key(api_key, settings):
        raise HTTPException(status_code=401, detail={"code": "INVALID_KEY", "message": "Geçersiz API key"})
    
    return {
        "success": True,
        "message": "Giriş başarılı",
        "api_key": api_key
    }


@router.get("/api/status")
async def ui_status(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    return await _status_payload(request)


@router.get("/api/config/read")
async def config_read(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    settings = get_settings()
    admin_unlocked = _has_valid_admin_header(request)
    return await run_in_threadpool(_config_read_sync, admin_unlocked)


@router.get("/api/config/list")
async def config_list(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    return {"backups": await run_in_threadpool(_list_env_backups)}


@router.post("/api/config/preview")
async def config_preview(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = payload.get("updates") or {}
    return await run_in_threadpool(_config_preview_sync, updates)


@router.post("/api/config/apply")
async def config_apply(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = payload.get("updates") or {}
    create_backup = bool(payload.get("backup", True))
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, updates, create_backup)
    return result


@router.post("/api/config/backup")
async def config_backup(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    backup_path = await run_in_threadpool(_create_env_backup)
    if not backup_path:
        raise HTTPException(status_code=404, detail={"code": "NO_ENV", "message": ".env file not found"})
    return {"backup": _relative(backup_path)}


@router.post("/api/config/restart")
async def config_restart(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    if not RESTART_SCRIPT.exists():
        return {"status": "missing", "message": "tools/restart_app.ps1 not found"}
    result = await _run_subprocess("restart", _powershell_command(RESTART_SCRIPT))
    return result


@router.get("/api/limits")
async def limits_read(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    settings = get_settings()
    entries = _collect_limit_entries(settings)
    return {
        "entries": entries,
        "admin_mode": _admin_mode(settings),
        "admin_unlocked": _has_valid_admin_header(request, settings),
    }


@router.post("/api/limits/preview")
async def limits_preview(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {key: value for key, value in (payload.get("updates") or {}).items() if key in LIMIT_KEYS or key.startswith("RATE_LIMIT_")}
    return await run_in_threadpool(_config_preview_sync, updates)


@router.post("/api/limits/apply")
async def limits_apply(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {key: value for key, value in (payload.get("updates") or {}).items() if key in LIMIT_KEYS or key.startswith("RATE_LIMIT_")}
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, updates, True)
    return result


@router.get("/api/security")
async def security_read(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    settings = get_settings()
    return {
        "admin_mode": _admin_mode(settings),
        "admin_unlocked": _has_valid_admin_header(request, settings),
        "enable_security": settings.enable_security,
        "api_key_masked": _mask(settings.api_key),
        "xi_api_key_masked": _mask(settings.xi_api_key),
    }


@router.post("/api/security/preview")
async def security_preview(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {}
    if "ENABLE_SECURITY" in payload:
        updates["ENABLE_SECURITY"] = payload["ENABLE_SECURITY"]
    return await run_in_threadpool(_config_preview_sync, updates)


@router.post("/api/security/apply")
async def security_apply(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {}
    if "ENABLE_SECURITY" in payload:
        updates["ENABLE_SECURITY"] = payload["ENABLE_SECURITY"]
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, updates, True)
    return result


@router.post("/api/security/rotate")
async def security_rotate(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    new_key = secrets.token_urlsafe(48)
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, {"API_KEY": new_key}, True)
    result["api_key"] = new_key
    result["masked"] = _mask(new_key)
    return result


@router.post("/api/config/elevenlabs-key")
async def save_elevenlabs_key(request: Request) -> Dict[str, Any]:
    # No API key required for this endpoint (used during login)
    payload = await request.json()
    api_key = payload.get("api_key", "").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail={"code": "MISSING_KEY", "message": "API key gerekli"})
    
    if not api_key.startswith("sk_"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_KEY", "message": "ElevenLabs API key 'sk_' ile başlamalı"})
    
    # API key'i doğrula (basit format kontrolü)
    if len(api_key) < 20:
        raise HTTPException(status_code=400, detail={"code": "INVALID_KEY", "message": "Geçersiz API key formatı"})
    
    try:
        async with CONFIG_LOCK:
            result = await run_in_threadpool(_config_apply_sync, {"XI_API_KEY": api_key}, True)
        
        if result.get("applied"):
            return {
                "success": True,
                "message": "ElevenLabs API key başarıyla kaydedildi",
                "masked_key": _mask(api_key)
            }
        else:
            logger.error("Failed to apply config: %s", result)
            raise HTTPException(status_code=500, detail={"code": "SAVE_FAILED", "message": "API key kaydedilemedi"})
    except Exception as e:
        logger.error("Error saving ElevenLabs API key: %s", str(e))
        raise HTTPException(status_code=500, detail={"code": "SAVE_FAILED", "message": f"API key kaydedilemedi: {str(e)}"})


@router.get("/api/config/elevenlabs-key")
async def get_elevenlabs_key_status(request: Request) -> Dict[str, Any]:
    # No API key required for this endpoint (used during login)
    settings = get_settings()
    
    return {
        "configured": bool(settings.xi_api_key),
        "masked_key": _mask(settings.xi_api_key) if settings.xi_api_key else None,
        "has_valid_format": settings.xi_api_key.startswith("sk_") if settings.xi_api_key else False
    }


@router.get("/api/resilience")
async def resilience_read(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    settings = get_settings()
    entries = _collect_resilience_entries(settings)
    return {
        "entries": entries,
        "admin_mode": _admin_mode(settings),
        "admin_unlocked": _has_valid_admin_header(request, settings),
    }


@router.post("/api/resilience/preview")
async def resilience_preview(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {key: value for key, value in (payload.get("updates") or {}).items() if key in RESILIENCE_KEYS or key.startswith("RESILIENCE_")}
    return await run_in_threadpool(_config_preview_sync, updates)


@router.post("/api/resilience/apply")
async def resilience_apply(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates = {key: value for key, value in (payload.get("updates") or {}).items() if key in RESILIENCE_KEYS or key.startswith("RESILIENCE_")}
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, updates, True)
    return result


@router.get("/api/voices")
async def voices_read(request: Request) -> Dict[str, Any]:
    # No API key required - uses ElevenLabs key from header
    response = await _safe_internal_json(request, "GET", "/voices")
    aliases_resp = await _safe_internal_json(request, "GET", "/voices/aliases")
    return {
        "voices": response.get("voices", []) if isinstance(response, dict) else [],
        "aliases": aliases_resp.get("aliases", []) if isinstance(aliases_resp, dict) else [],
    }


@router.post("/api/voices/alias")
async def voices_alias(request: Request) -> Response:
    _require_admin_key(request)
    payload = await request.json()
    response = await _call_internal(request, "POST", "/voices/aliases", json_body=payload, admin=True)
    return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type"))


@router.post("/api/voices/default")
async def voices_default(request: Request) -> Dict[str, Any]:
    _require_admin_key(request)
    payload = await request.json()
    updates: Dict[str, Any] = {}
    alias = (payload.get("alias") or "").strip()
    voice_id = payload.get("voice_id")
    if alias:
        updates["ELEVEN_DEFAULT_VOICE_ALIAS"] = alias
    if voice_id is not None:
        updates["ELEVEN_DEFAULT_VOICE_ID"] = voice_id
    if not updates:
        raise HTTPException(status_code=400, detail={"code": "NO_UPDATES", "message": "Provide alias or voice_id"})
    async with CONFIG_LOCK:
        result = await run_in_threadpool(_config_apply_sync, updates, True)
    return result


@router.post("/api/ivc")
async def voices_clone(
    request: Request,
    name: str = Form(...),
    alias: str = Form("user"),
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    _require_admin_key(request)
    if not files:
        raise HTTPException(status_code=422, detail={"code": "NO_FILES", "message": "Upload at least one audio sample"})
    if len(files) > 3:
        raise HTTPException(status_code=422, detail={"code": "TOO_MANY_FILES", "message": "Upload up to 3 samples"})
    buffers: List[Tuple[str, bytes, str]] = []
    for upload in files:
        data = await upload.read()
        if not data:
            continue
        buffers.append(
            (
                upload.filename or "sample.wav",
                data,
                upload.content_type or "application/octet-stream",
            )
        )
    if not buffers:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_FILES", "message": "Uploaded files were empty"})
    files_payload = [("files", (filename, data, content_type)) for filename, data, content_type in buffers]
    form_data = {"name": name, "alias": alias}
    response = await _call_internal(
        request,
        "POST",
        "/providers/elevenlabs/ivc",
        data=form_data,
        files=files_payload,
        admin=True,
        timeout=180.0,
    )
    if response.status_code == 200:
        return {"status": "proxied", "result": response.json()}
    if response.status_code not in {404, 501}:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    provider = get_eleven_provider(require=True)
    temp_paths: List[str] = []
    try:
        for filename, data, _content_type in buffers:
            suffix = os.path.splitext(filename)[1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(data)
                temp_paths.append(tmp.name)
        voice_id = provider.create_ivc(name=name, files=temp_paths)
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc
    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass
    entry = save_alias(alias=alias or "user", voice_id=voice_id, name=name, source="ivc")
    return {"status": "fallback", "voice_id": voice_id, "alias": entry.get("alias")}


@router.delete("/api/voices/{voice_id}")
async def delete_voice(request: Request, voice_id: str) -> Dict[str, Any]:
    """Delete a voice from ElevenLabs."""
    _require_admin_key(request)
    provider = get_eleven_provider(require=True)
    try:
        provider.delete_voice(voice_id)
        return {"status": "success", "message": f"Voice {voice_id} deleted"}
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.delete("/api/aliases/{alias}")
async def delete_alias_endpoint(request: Request, alias: str) -> Dict[str, Any]:
    """Delete a voice alias."""
    _require_admin_key(request)
    from providers.elevenlabs_tts import delete_alias
    try:
        delete_alias(alias)
        return {"status": "success", "message": f"Alias {alias} deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "DELETE_FAILED", "message": str(exc)}) from exc


@router.get("/api/voices/{voice_id}/details")
async def get_voice_details(request: Request, voice_id: str) -> Dict[str, Any]:
    """Get detailed voice information."""
    # No API key required - uses ElevenLabs key from header
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=True, api_key=elevenlabs_key)
    try:
        voice_info = provider.get_voice(voice_id)
        return voice_info
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.post("/api/voices/{voice_id}/edit")
async def edit_voice(request: Request, voice_id: str) -> Dict[str, Any]:
    """Edit voice metadata."""
    _require_admin_key(request)
    payload = await request.json()
    name = payload.get("name")
    description = payload.get("description")
    
    provider = get_eleven_provider(require=True)
    try:
        result = provider.edit_voice(voice_id, name=name, description=description)
        return result
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.get("/api/models")
async def get_models(request: Request) -> Dict[str, Any]:
    """Get available ElevenLabs models."""
    # No API key required - uses ElevenLabs key from header
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=True, api_key=elevenlabs_key)
    try:
        models = provider.get_models()
        return {"models": models}
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.get("/api/subscription")
async def get_subscription(request: Request) -> Dict[str, Any]:
    """Get user subscription info and quota."""
    # No API key required - uses ElevenLabs key from header
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=True, api_key=elevenlabs_key)
    try:
        subscription = provider.get_user_subscription()
        return subscription
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.get("/api/history")
async def get_history(request: Request, page_size: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Get generation history."""
    # No API key required - uses ElevenLabs key from header
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=True, api_key=elevenlabs_key)
    try:
        history = provider.get_history(page_size=page_size)
        return {"history": history, "count": len(history)}
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.delete("/api/history/{history_item_id}")
async def delete_history_item(request: Request, history_item_id: str) -> Dict[str, Any]:
    """Delete a history item."""
    _require_admin_key(request)
    provider = get_eleven_provider(require=True)
    try:
        provider.delete_history_item(history_item_id)
        return {"status": "success", "message": "History item deleted"}
    except ElevenLabsError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "detail": exc.detail}) from exc


@router.get("/api/terms/list")
async def terms_list(request: Request) -> Dict[str, Any]:
    _require_api_key_header(request)
    store = get_terms_store()
    entries = store.list_entries()
    stats = store.stats()
    settings = get_settings()
    admin_required = _admin_mode(settings) and not _has_valid_admin_header(request, settings)
    return {
        "entries": entries,
        "stats": stats, # entries listesindeki her objenin id'si var
        "admin_required": admin_required,
    }


@router.post("/api/terms/crud")
async def terms_crud(request: Request) -> Response:
    _require_admin_key(request)
    payload = await request.json()
    action = (payload.get("action") or "").lower()
    if action not in {"create", "update", "delete", "reload"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ACTION", "message": "Action must be create/update/delete/reload"})
    if action == "create":
        body = payload.get("data") or {}
        response = await _call_internal(request, "POST", "/terms", json_body=body, admin=True)
    elif action == "update":
        entry_id = payload.get("id")
        if not entry_id: # pragma: no cover
            raise HTTPException(status_code=400, detail={"code": "MISSING_ID", "message": "Entry id is required"})
        body = payload.get("data") or {}
        response = await _call_internal(request, "PUT", f"/terms/{entry_id}", json_body=body, admin=True)
    elif action == "delete":
        entry_id = payload.get("id")
        if not entry_id: # pragma: no cover
            raise HTTPException(status_code=400, detail={"code": "MISSING_ID", "message": "Entry id is required"})
        response = await _call_internal(request, "DELETE", f"/terms/{entry_id}", admin=True)
    else:
        response = await _call_internal(request, "POST", "/terms/reload", admin=True)
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


@router.post("/api/terms/import")
async def terms_import(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    _require_admin_key(request)
    raw = await file.read()
    files = {"file": (file.filename or "terms.upload", raw, file.content_type or "application/octet-stream")}
    response = await _call_internal(request, "POST", "/terms/import", files=files, admin=True)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@router.post("/api/terms/import/preview")
async def terms_import_preview(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    _require_admin_key(request)
    raw = await file.read()
    return await run_in_threadpool(_terms_import_preview_sync, file.filename or "", raw)


@router.get("/api/terms/export")
async def terms_export(request: Request) -> Response:
    _require_admin_key(request)
    response = await _call_internal(request, "GET", "/terms/export", admin=True)
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


@router.post("/api/runners/{action}")
async def runners_action(request: Request, action: str) -> Dict[str, Any]:
    _require_admin_key(request)
    return await _execute_runner(action)


@router.get("/api/logs/tail")
async def logs_tail(request: Request, lines: int = Query(100, ge=1, le=10000)) -> Dict[str, Any]:
    """Get tail of metrics log file."""
    _require_api_key_header(request)
    settings = get_settings()
    metrics_path = Path(settings.metrics_jl_path)
    
    if not metrics_path.exists():
        return {
            "log_file": str(metrics_path),
            "lines": [],
            "message": "Log file does not exist yet"
        }
    
    # Read last N lines
    try:
        with metrics_path.open("r", encoding="utf-8") as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
        return {
            "log_file": str(metrics_path),
            "total_lines": len(all_lines),
            "showing_lines": len(tail_lines),
            "lines": [line.strip() for line in tail_lines]
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, 
            detail={"code": "READ_ERROR", "message": f"Failed to read log: {str(exc)}"}
        ) from exc


@router.get("/api/logs/ui/tail")
async def logs_ui_tail(request: Request, path: str) -> Dict[str, Any]:
    """Get tail of UI test log file."""
    _require_api_key_header(request)
    _ensure_dirs()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = (UI_RUNS_DIR / candidate.name).resolve()
    else:
        try:
            candidate = candidate.resolve()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Log not found"}) from None
    ui_runs_root = UI_RUNS_DIR.resolve()
    if ui_runs_root not in candidate.parents and candidate != ui_runs_root:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PATH", "message": "Path outside ui_runs directory"})
    if not candidate.exists():
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Log not found"})
    return {
        "log_file": _relative(candidate),
        "log_tail": _tail_lines(candidate),
    }


@router.post("/api/playground/tts")
async def playground_tts(request: Request) -> Dict[str, Any]:
    # No API key required - uses ElevenLabs key from header
    payload = await request.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_TEXT", "message": "Text is required"})
    body = {"text": text}
    for key in ("voice_alias", "voice_id", "model_id", "output_format", "voice_settings"):
        if payload.get(key):
            body[key] = payload[key]
    response = await _call_internal(request, "POST", "/tts", json_body=body, timeout=120.0)
    audio = await _collect_audio_bytes(response)
    mime_type = response.headers.get("content-type") or "audio/mpeg"
    return {
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "mime_type": mime_type,
        "bytes": len(audio),
    }


@router.post("/api/playground/speak")
async def playground_speak(
    request: Request,
    audio_file: UploadFile = File(...),
    voice_alias: Optional[str] = Form(None),
    voice_id: Optional[str] = Form(None),
) -> Dict[str, Any]:
    # No API key required - uses ElevenLabs key from header
    raw = await audio_file.read()
    if not raw:
        raise HTTPException(status_code=422, detail={"code": "EMPTY_FILE", "message": "Upload a non-empty audio file"})
    data: Dict[str, Any] = {}
    if voice_alias:
        data["voice_alias"] = voice_alias
    if voice_id:
        data["voice_id"] = voice_id
    files = {
        "audio_file": (
            audio_file.filename or "sample.wav",
            raw,
            audio_file.content_type or "application/octet-stream",
        )
    }
    response = await _call_internal(request, "POST", "/speak", data=data, files=files, timeout=240.0)
    audio = await _collect_audio_bytes(response)
    mime_type = response.headers.get("content-type") or "audio/mpeg"
    return {
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "mime_type": mime_type,
        "bytes": len(audio),
    }


def _html_page() -> str:
    template_path = REPO_ROOT / 'app' / 'templates' / 'ui_admin.html'
    return template_path.read_text(encoding='utf-8')

@router.get("", response_class=HTMLResponse)
async def ui_root() -> str:
    return _html_page()


__all__ = ["router"]
