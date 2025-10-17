from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from loguru import logger

from app.config import get_settings

ACCENT_MAP = str.maketrans(
    {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }
)


class TermsLimitError(RuntimeError):
    """Raised when max entry limit is exceeded."""


class TermsValidationError(RuntimeError):
    """Raised when term payload validation fails."""


@dataclass(slots=True)
class TermEntry:
    id: str
    src: str
    dst: str
    type: str
    priority: int
    notes: str
    active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
            "priority": self.priority,
            "notes": self.notes,
            "active": self.active,
        }


def _strip_accents(value: str) -> str:
    if not value:
        return value
    return value.translate(ACCENT_MAP)


def _levenshtein_limited(a: str, b: str, max_dist: int) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        least = max_dist + 1
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            insertion = current[j - 1] + 1
            deletion = previous[j] + 1
            substitution = previous[j - 1] + cost
            value = min(insertion, deletion, substitution)
            current.append(value)
            least = min(least, value)
        previous = current
        if least > max_dist:
            return max_dist + 1
    return previous[-1]


class TermsStore:
    """Persistent store + in-memory index for terms."""

    def __init__(self, path: Path, max_entries: int) -> None:
        self.path = path
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {"entries": []}
        self._ordered_entries: List[Dict[str, Any]] = []
        self._exact_index: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        self._accent_index: Dict[str, str] = {}
        self._compiled_exact: Dict[Tuple[str, bool], re.Pattern] = {}
        self._compiled_regex: Dict[Tuple[str, bool], re.Pattern] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=200)
        self.loaded_at: Optional[datetime] = None

        self._fuzzy_threshold = 512
        self._fuzzy_exact_entries: List[Dict[str, Any]] = []
        self._fuzzy_enabled = True

        self.load()

    # region lifecycle -------------------------------------------------
    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                logger.info("## terms init {}", self.path)
                self._data = {"entries": []}
                self._atomic_write(self._data)
            else:
                with self.path.open("r", encoding="utf-8") as handle:
                    try:
                        self._data = json.load(handle)
                    except json.JSONDecodeError as exc:
                        logger.warning("terms store malformed, resetting: {}", exc)
                        self._data = {"entries": []}
            validated: List[Dict[str, Any]] = []
            for raw in self._data.get("entries", []):
                try:
                    entry = self._validate_payload(raw, existing_id=raw.get("id"))
                    validated.append(entry.to_dict())
                except TermsValidationError as exc:
                    logger.warning("Skipping invalid term during load: {}", exc)
            self._data = {"entries": validated}
            self._ensure_limit(len(validated))
            self._rebuild_indexes()
            self.loaded_at = datetime.now(timezone.utc)
            logger.info(
                "## terms loaded entries={} regex={} fuzzy_enabled={}",
                len(self._ordered_entries),
                self._regex_count(),
                self._fuzzy_enabled,
            )

    def reload(self) -> None:
        self.load()

    def save(self) -> None:
        with self._lock:
            self._ensure_limit(len(self._data["entries"]))
            payload = {"entries": deepcopy(self._data["entries"])}
            self._atomic_write(payload)
            self._record_history("save", {"entries": len(payload["entries"])})
            logger.info("## terms saved entries={}", len(payload["entries"]))

    # endregion --------------------------------------------------------
    # region CRUD ------------------------------------------------------
    def list_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return deepcopy(self._data["entries"])

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._data["entries"]),
                "regex_count": self._regex_count(),
                "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
                "fuzzy_enabled": self._fuzzy_enabled,
                "history": list(self._history),
            }

    def add_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entry = self._validate_payload(payload)
        with self._lock:
            self._ensure_limit(len(self._data["entries"]) + 1)
            entry_dict = entry.to_dict()
            self._data["entries"].append(entry_dict)
            self._record_history("add", {"id": entry.id, "src": entry.src})
            self._rebuild_indexes()
            self.save()
            return entry_dict

    def update_entry(self, entry_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            idx = self._entry_index(entry_id)
            if idx == -1:
                raise TermsValidationError("NOT_FOUND")
            merged = deepcopy(self._data["entries"][idx])
            merged.update(payload)
            entry = self._validate_payload(merged, existing_id=entry_id)
            entry_dict = entry.to_dict()
            self._data["entries"][idx] = entry_dict
            self._record_history("update", {"id": entry.id, "src": entry.src})
            self._rebuild_indexes()
            self.save()
            return entry_dict

    def delete_entry(self, entry_id: str) -> None:
        with self._lock:
            idx = self._entry_index(entry_id)
            if idx == -1:
                raise TermsValidationError("NOT_FOUND")
            removed = self._data["entries"].pop(idx)
            self._record_history("delete", {"id": removed["id"], "src": removed["src"]})
            self._rebuild_indexes()
            self.save()

    def import_entries(self, entries: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        added = 0
        updated = 0
        with self._lock:
            by_src: Dict[str, Tuple[int, Dict[str, Any]]] = {
                self._normalize_src(item["src"]): (idx, item)
                for idx, item in enumerate(self._data["entries"])
            }
            for raw in entries:
                try:
                    entry = self._validate_payload(raw)
                except TermsValidationError as exc:
                    logger.warning("Import term skipped: %s", exc)
                    continue
                key = self._normalize_src(entry.src)
                entry_dict = entry.to_dict()
                current = by_src.get(key)
                if current:
                    current_idx, current_entry = current
                    if entry.priority >= int(current_entry.get("priority", 0)):
                        self._data["entries"][current_idx] = entry_dict
                        by_src[key] = (current_idx, entry_dict)
                        updated += 1
                else:
                    self._ensure_limit(len(self._data["entries"]) + 1)
                    self._data["entries"].append(entry_dict)
                    by_src[key] = (len(self._data["entries"]) - 1, entry_dict)
                    added += 1
            self._record_history("import", {"added": added, "updated": updated})
            self._rebuild_indexes()
            self.save()
        logger.info("## terms import added={} updated={}", added, updated)
        return {"added": added, "updated": updated}

    # endregion --------------------------------------------------------
    # region replacement -----------------------------------------------
    def replace(
        self,
        text: str,
        *,
        case_sensitive: bool,
        enable_regex: bool,
        enable_fuzzy: bool,
        fuzzy_dist: int,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        if not text:
            return text, []
        with self._lock:
            working = text
            changes: List[Dict[str, Any]] = []
            allowed_exact = self._collect_exact_ids(text)

            for entry in self._ordered_entries:
                if not entry["active"]:
                    continue
                if entry["type"] == "exact":
                    if entry["id"] not in allowed_exact:
                        continue
                    pattern = self._compile_exact(entry, case_sensitive)
                    working, entry_changes = self._apply_pattern(working, pattern, entry, "exact")
                else:
                    if not enable_regex:
                        continue
                    pattern = self._compile_regex(entry, case_sensitive)
                    working, entry_changes = self._apply_pattern(working, pattern, entry, "regex")
                if entry_changes:
                    changes.extend(entry_changes)

            if enable_fuzzy and fuzzy_dist > 0 and self._fuzzy_enabled:
                working, fuzzy_changes = self._apply_fuzzy(working, case_sensitive, fuzzy_dist)
                if fuzzy_changes:
                    for change in fuzzy_changes:
                        change["kind"] = "fuzzy"
                    changes.extend(fuzzy_changes)
            return working, changes

    # endregion --------------------------------------------------------

    def _collect_exact_ids(self, text: str) -> set[str]:
        normalized_chars = set(_strip_accents(text.lower()))
        candidates: set[str] = set()
        for char in normalized_chars:
            buckets = self._exact_index.get(char)
            if not buckets:
                continue
            for length, entries in buckets.items():
                if length > len(text):
                    continue
                for entry in entries:
                    candidates.add(entry["id"])
        return candidates

    def _apply_pattern(
        self,
        text: str,
        pattern: re.Pattern,
        entry: Dict[str, Any],
        kind: str,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        matches: List[Dict[str, Any]] = []

        def _replacement(match: re.Match[str]) -> str:
            matches.append(
                {
                    "id": entry["id"],
                    "src": entry["src"],
                    "dst": entry["dst"],
                    "start": match.start(),
                    "end": match.end(),
                    "kind": kind,
                }
            )
            return entry["dst"]

        new_text, count = pattern.subn(_replacement, text)
        if count == 0:
            return text, []
        return new_text, matches

    def _apply_fuzzy(self, text: str, case_sensitive: bool, fuzzy_dist: int) -> Tuple[str, List[Dict[str, Any]]]:
        if not self._fuzzy_enabled or not self._fuzzy_exact_entries:
            return text, []
        token_pattern = re.compile(r"\b\w+\b", re.UNICODE)
        pieces: List[str] = []
        matches: List[Dict[str, Any]] = []
        last_end = 0
        for match in token_pattern.finditer(text):
            start, end = match.span()
            token = match.group(0)
            baseline = token if case_sensitive else token.lower()
            accentless_token = _strip_accents(baseline)
            best_entry: Optional[Dict[str, Any]] = None
            best_distance = fuzzy_dist + 1
            for entry in self._fuzzy_exact_entries:
                candidate = self._accent_index.get(entry["id"], "")
                if abs(len(candidate) - len(accentless_token)) > fuzzy_dist:
                    continue
                distance = _levenshtein_limited(accentless_token, candidate, fuzzy_dist)
                if distance <= fuzzy_dist and distance < best_distance:
                    best_entry = entry
                    best_distance = distance
                    if distance == 0:
                        break
            if best_entry and best_distance <= fuzzy_dist:
                pieces.append(text[last_end:start])
                pieces.append(best_entry["dst"])
                matches.append(
                    {
                        "id": best_entry["id"],
                        "src": best_entry["src"],
                        "dst": best_entry["dst"],
                        "start": start,
                        "end": end,
                        "kind": "fuzzy",
                    }
                )
                last_end = end
        if not matches:
            return text, []
        pieces.append(text[last_end:])
        return "".join(pieces), matches

    def _compile_exact(self, entry: Dict[str, Any], case_sensitive: bool) -> re.Pattern:
        key = (entry["id"], case_sensitive)
        cached = self._compiled_exact.get(key)
        if cached:
            return cached
        flags = re.UNICODE
        if not case_sensitive:
            flags |= re.IGNORECASE
        pattern = re.compile(rf"\b{re.escape(entry['src'])}\b", flags)
        self._compiled_exact[key] = pattern
        return pattern

    def _compile_regex(self, entry: Dict[str, Any], case_sensitive: bool) -> re.Pattern:
        key = (entry["id"], case_sensitive)
        cached = self._compiled_regex.get(key)
        if cached:
            return cached
        flags = re.UNICODE
        if not case_sensitive:
            flags |= re.IGNORECASE
        pattern = re.compile(entry["src"], flags)
        self._compiled_regex[key] = pattern
        return pattern

    def _rebuild_indexes(self) -> None:
        entries = [self._validate_payload(item, existing_id=item.get("id")).to_dict() for item in self._data["entries"]]
        entries.sort(key=lambda e: (-int(e.get("priority", 0)), 0 if e["type"] == "exact" else 1, e["src"]))
        self._ordered_entries = entries
        exact_index: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        accent_index: Dict[str, str] = {}
        fuzzy_exact: List[Dict[str, Any]] = []
        for entry in entries:
            accent_index[entry["id"]] = _strip_accents(entry["src"].lower())
            if entry["type"] == "exact":
                if entry["active"]:
                    fuzzy_exact.append(entry)
                first_char = _strip_accents(entry["src"][:1].lower())
                length = len(entry["src"])
                by_length = exact_index.setdefault(first_char, {})
                by_length.setdefault(length, []).append(entry)
        self._exact_index = exact_index
        self._accent_index = accent_index
        self._compiled_exact.clear()
        self._compiled_regex.clear()
        self._fuzzy_exact_entries = fuzzy_exact
        self._fuzzy_enabled = len(entries) <= self._fuzzy_threshold

    # region utilities -------------------------------------------------
    def _validate_payload(self, payload: Dict[str, Any], existing_id: Optional[str] = None) -> TermEntry:
        src = str(payload.get("src", "") or "").strip()
        dst = str(payload.get("dst", "") or "").strip()
        notes = str(payload.get("notes", "") or "").strip()
        if not src or not dst:
            raise TermsValidationError("INVALID_TERM")
        if len(src) > 512 or len(dst) > 512:
            raise TermsValidationError("INVALID_TERM")
        entry_type = (payload.get("type") or "exact").lower()
        if entry_type not in {"exact", "regex"}:
            raise TermsValidationError("INVALID_TERM")
        priority = int(payload.get("priority", 100))
        active = bool(payload.get("active", True))
        entry_id = existing_id or payload.get("id") or str(uuid.uuid4())
        if entry_type == "regex":
            try:
                re.compile(src, re.UNICODE)
            except re.error as exc:
                raise TermsValidationError("BAD_REGEX") from exc
        return TermEntry(
            id=str(entry_id),
            src=src,
            dst=dst,
            type=entry_type,
            priority=priority,
            notes=notes,
            active=active,
        )

    def _ensure_limit(self, new_count: int) -> None:
        if new_count > self.max_entries:
            raise TermsLimitError("TERMS_LIMIT")

    def _entry_index(self, entry_id: str) -> int:
        for idx, entry in enumerate(self._data["entries"]):
            if entry["id"] == entry_id:
                return idx
        return -1

    def _record_history(self, action: str, info: Dict[str, Any]) -> None:
        self._history.appendleft({"ts": int(time.time()), "action": action, "info": info})

    def _normalize_src(self, src: str) -> str:
        return _strip_accents(src.strip().lower())

    def _regex_count(self) -> int:
        return sum(1 for entry in self._data["entries"] if entry.get("type") == "regex")

    def _atomic_write(self, payload: Dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    # endregion --------------------------------------------------------


_TERMS_STORE: Optional[TermsStore] = None
_STORE_LOCK = threading.Lock()


def get_terms_store() -> TermsStore:
    global _TERMS_STORE
    with _STORE_LOCK:
        if _TERMS_STORE is None:
            settings = get_settings()
            terms_path = Path(settings.terms_file).resolve()
            _TERMS_STORE = TermsStore(terms_path, settings.terms_max_entries)
        return _TERMS_STORE


def reset_terms_store() -> None:
    global _TERMS_STORE
    with _STORE_LOCK:
        _TERMS_STORE = None
