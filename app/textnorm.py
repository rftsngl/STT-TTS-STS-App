import re
from typing import Any, Dict, List, Tuple

from app.config import get_settings
from app.terms_store import get_terms_store

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_SPACING_RE = re.compile(r"\s*([,.;:!?])\s*")
_QUOTE_FIX_RE = re.compile(r"\s*([\"'])\s*")
_NUMBER_GROUP_RE = re.compile(r"(\d)\s*([.,])\s*(\d)")
_ELLIPSIS_RE = re.compile(r"\.{3,}")
_MULTI_PUNCT_RE = re.compile(r"([!?]){2,}")


def normalize_text(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = _NUMBER_GROUP_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}", cleaned)
    cleaned = _PUNCT_SPACING_RE.sub(lambda match: f"{match.group(1)} ", cleaned)
    cleaned = cleaned.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    cleaned = cleaned.replace(" :", ":").replace(" ;", ";")
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = _QUOTE_FIX_RE.sub(lambda m: m.group(1).replace('"', '"').replace("'", "'"), cleaned)
    cleaned = _ELLIPSIS_RE.sub("...", cleaned)
    cleaned = _MULTI_PUNCT_RE.sub(lambda m: m.group(1), cleaned)
    return cleaned.strip()


def apply_terms(text: str, *, for_partial: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
    settings = get_settings()
    if not text:
        return text, []
    if for_partial and not settings.terms_apply_to_partials:
        return text, []
    store = get_terms_store()
    case_sensitive = settings.terms_case_sensitive
    if for_partial:
        enable_regex = False
        enable_fuzzy = False
        fuzzy_dist = 0
    else:
        enable_regex = settings.terms_enable_regex
        enable_fuzzy = settings.terms_enable_fuzzy
        fuzzy_dist = settings.terms_fuzzy_max_dist if enable_fuzzy else 0
    new_text, changes = store.replace(
        text,
        case_sensitive=case_sensitive,
        enable_regex=enable_regex,
        enable_fuzzy=enable_fuzzy,
        fuzzy_dist=fuzzy_dist,
    )
    return new_text, changes


def summarize_term_changes(changes: List[Dict[str, Any]], limit: int = 5) -> Dict[str, Any]:
    if not changes:
        return {"count": 0, "items": []}
    items = []
    for change in changes[:limit]:
        items.append(
            {
                "id": change.get("id"),
                "src": str(change.get("src", ""))[:24],
                "dst": str(change.get("dst", ""))[:24],
                "kind": change.get("kind"),
            }
        )
    return {"count": len(changes), "items": items}
