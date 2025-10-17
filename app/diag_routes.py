from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from app.config import get_settings


router = APIRouter(prefix="/diag", tags=["diagnostics"])


def _route_descriptor(route: APIRoute) -> Dict[str, Any]:
    endpoint = route.endpoint
    handler_name = getattr(endpoint, "__name__", repr(endpoint))
    handler_module = getattr(endpoint, "__module__", "")
    return {
        "path": route.path,
        "methods": sorted(route.methods or []),
        "name": route.name,
        "handler": f"{handler_module}.{handler_name}".strip("."),
    }




@router.get("/routes")
async def list_routes(request: Request) -> List[Dict[str, Any]]:
    http_routes: List[Dict[str, Any]] = []
    for route in request.app.routes:
        if isinstance(route, APIRoute):
            http_routes.append(_route_descriptor(route))
    http_routes.sort(key=lambda item: (item["path"], ",".join(item["methods"])))
    return http_routes




@router.get("/capabilities")
async def list_capabilities(request: Request) -> Dict[str, Any]:
    settings = get_settings()
    http_paths = {route.path for route in request.app.routes if isinstance(route, APIRoute)}

    features = {
        "stt_file": "/stt" in http_paths,
        "chain_http": "/speak" in http_paths,
        "terms": True,
        "noise": settings.noise_suppressor,
        "provider": "elevenlabs" if settings.xi_api_key else "none",
    }

    env_required = {
        "tts": ["XI_API_KEY"],
        "ivc": ["XI_API_KEY"],
        "terms_admin": [],
    }

    return {
        "features": features,
        "env_required": env_required,
    }
