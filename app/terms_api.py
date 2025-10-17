from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.terms_store import TermsLimitError, TermsValidationError, get_terms_store

router = APIRouter(prefix="/terms", tags=["terms"])


def _require_admin(request: Request) -> None:
    # Admin functionality now accessible with API key only
    pass


def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key in ("id", "src", "dst", "type", "priority", "notes", "active"):
        if key in payload and payload[key] is not None:
            cleaned[key] = payload[key]
    if "priority" in cleaned:
        try:
            cleaned["priority"] = int(cleaned["priority"])
        except (TypeError, ValueError):
            pass
    if "active" in cleaned:
        value = cleaned["active"]
        if isinstance(value, str):
            cleaned["active"] = value.strip().lower() in {"1", "true", "yes", "on"}
        else:
            cleaned["active"] = bool(value)
    return cleaned


def _handle_terms_error(exc: Exception) -> None:
    if isinstance(exc, TermsLimitError):
        raise HTTPException(status_code=422, detail={"code": "TERMS_LIMIT", "message": "Terms limit exceeded"}) from exc
    if isinstance(exc, TermsValidationError):
        code = str(exc) or "INVALID_TERM"
        message = "Invalid term payload"
        if code == "BAD_REGEX":
            message = "Regex pattern is invalid"
        raise HTTPException(status_code=422, detail={"code": code, "message": message}) from exc
    raise exc


@router.get("")
def list_terms() -> Dict[str, Any]:
    store = get_terms_store()
    return {
        "entries": store.list_entries(),
        "stats": store.stats(),
    }


@router.post("")
def create_term(payload: Dict[str, Any]) -> Dict[str, Any]:
    store = get_terms_store()
    try:
        entry = store.add_entry(_clean_payload(payload))
    except Exception as exc:
        _handle_terms_error(exc)
    return {"entry": entry}


@router.put("/{entry_id}")
def update_term(entry_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    store = get_terms_store()
    try:
        entry = store.update_entry(entry_id, _clean_payload(payload))
    except Exception as exc:
        _handle_terms_error(exc)
    return {"entry": entry}


@router.delete("/{entry_id}")
def delete_term(entry_id: str) -> Dict[str, Any]:
    store = get_terms_store()
    try:
        store.delete_entry(entry_id)
    except Exception as exc:
        _handle_terms_error(exc)
    return {"status": "deleted", "id": entry_id}


def _parse_json_entries(content: str) -> List[Dict[str, Any]]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_JSON", "message": "Import file is not valid JSON"}) from exc
    if isinstance(document, dict):
        entries = document.get("entries", [])
    elif isinstance(document, list):
        entries = document
    else:
        raise HTTPException(status_code=400, detail={"code": "INVALID_JSON", "message": "Unsupported JSON structure"})
    if not isinstance(entries, list):
        raise HTTPException(status_code=400, detail={"code": "INVALID_JSON", "message": "entries must be a list"})
    cleaned: List[Dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict):
            cleaned.append(_clean_payload(entry))
    return cleaned


def _parse_csv_entries(content: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(content))
    entries: List[Dict[str, Any]] = []
    for row in reader:
        entries.append(_clean_payload(row))
    return entries


@router.post("/import")
async def import_terms(file: UploadFile = File(...)) -> Dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_IMPORT", "message": "Import payload is empty"})
    text = raw.decode("utf-8")
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    if filename.endswith(".json") or "json" in content_type:
        entries = _parse_json_entries(text)
    else:
        entries = _parse_csv_entries(text)

    store = get_terms_store()
    try:
        result = store.import_entries(entries)
    except Exception as exc:
        _handle_terms_error(exc)
    return {"result": result}


@router.get("/export")
def export_terms() -> JSONResponse:
    store = get_terms_store()
    payload = {"entries": store.list_entries()}
    return JSONResponse(content=payload)


@router.post("/reload")
def reload_terms() -> Dict[str, Any]:
    store = get_terms_store()
    store.reload()
    stats = store.stats()
    logger.info("## terms reloaded entries={}", stats.get("count", 0))
    return {"status": "reloaded", "stats": stats}
