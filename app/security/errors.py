from __future__ import annotations

from typing import Any, Dict

from starlette.responses import JSONResponse


def json_error(status_code: int, code: str, detail: str) -> JSONResponse:
    payload: Dict[str, Any] = {"code": code, "detail": detail}
    return JSONResponse(payload, status_code=status_code)
