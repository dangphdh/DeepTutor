"""WordListStore — JSON-backed spelling/vocabulary word lists.

A word list is a dad-managed content unit ("this week's words: school, teacher,
friend"). When the child practices spelling, a thin builder turns the active
list into ``MEMORY`` knowledge points (one KP per word, ``question_type=
"spelling"``). The list is the dad-facing concept; the KPs are the
engine-facing concept — decoupling them lets the dad edit the list without
touching mastery progress, and lets one list feed multiple practice sessions.

Persistence mirrors ``LearningStore``: one JSON file per list under
``workspace/learning/wordlists/``, atomic writes, a module-level CAS lock so
concurrent writes don't corrupt each other.
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from typing import Any
import uuid

from pydantic import BaseModel, Field

from deeptutor.services.path_service import get_path_service

# Module-level lock so CAS semantics hold across all store instances.
_cas_lock = threading.Lock()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex}")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class WordEntry(BaseModel):
    """One word in a spelling/vocabulary list."""

    word: str
    example_sentence: str = ""
    added_at: float = Field(default_factory=time.time)


class WordList(BaseModel):
    """A named list of spelling words."""

    id: str
    name: str
    language: str = "en"
    words: list[WordEntry] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def add_words(self, words: list[str], example_sentence: str = "") -> None:
        """Append words that aren't already present (case-insensitive dedup)."""
        existing = {w.word.lower() for w in self.words}
        for raw in words:
            w = raw.strip()
            if not w or w.lower() in existing:
                continue
            self.words.append(WordEntry(word=w, example_sentence=example_sentence))
            existing.add(w.lower())
        self.updated_at = time.time()

    def remove_word(self, word: str) -> bool:
        before = len(self.words)
        target = word.strip().lower()
        self.words = [w for w in self.words if w.word.lower() != target]
        removed = len(self.words) < before
        if removed:
            self.updated_at = time.time()
        return removed


def _safe_id(raw: str) -> str:
    """Sanitize a list id/name into a filesystem-safe, stable id."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (raw or "").strip().lower())
    return safe or f"list_{uuid.uuid4().hex[:8]}"


class WordListStore:
    """CRUD store for spelling/vocabulary word lists.

    Each list is persisted as ``<root>/<id>.json``. The store is process-local
    but multi-session safe via the CAS lock; concurrent turns that touch
    different lists never block each other on read.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (get_path_service().get_workspace_dir() / "learning" / "wordlists")
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, list_id: str) -> Path:
        if "/" in list_id or "\\" in list_id or ".." in list_id:
            raise ValueError(f"Invalid list id: {list_id!r}")
        return self._root / f"{list_id}.json"

    def create(self, name: str, *, language: str = "en", words: list[str] | None = None) -> WordList:
        """Create a new word list. Generates a stable id from the name."""
        list_id = _safe_id(name)
        # Avoid collision with an existing list of the same name.
        if self._path(list_id).exists():
            list_id = f"{list_id}_{uuid.uuid4().hex[:6]}"
        word_list = WordList(id=list_id, name=name.strip() or list_id, language=language)
        if words:
            word_list.add_words(words)
        self.save(word_list)
        return word_list

    def save(self, word_list: WordList) -> None:
        with _cas_lock:
            word_list.updated_at = time.time()
            text = json.dumps(word_list.model_dump(mode="json"), ensure_ascii=False, indent=2)
            _atomic_write_text(self._path(word_list.id), text)

    def load(self, list_id: str) -> WordList | None:
        path = self._path(list_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return WordList.model_validate(data)

    def delete(self, list_id: str) -> bool:
        with _cas_lock:
            path = self._path(list_id)
            if path.exists():
                path.unlink()
                return True
            return False

    def exists(self, list_id: str) -> bool:
        return self._path(list_id).exists()

    def list_all(self) -> list[WordList]:
        """Return all custom word lists (curated packs are surfaced separately)."""
        out: list[WordList] = []
        for p in sorted(self._root.glob("*.json")):
            if p.name.startswith("."):
                continue
            try:
                out.append(WordList.model_validate(json.loads(p.read_text(encoding="utf-8"))))
            except Exception:
                # Skip corrupt files rather than crashing the listing.
                continue
        return out

    def add_words(self, list_id: str, words: list[str], example_sentence: str = "") -> WordList | None:
        word_list = self.load(list_id)
        if word_list is None:
            return None
        word_list.add_words(words, example_sentence=example_sentence)
        self.save(word_list)
        return word_list

    def remove_word(self, list_id: str, word: str) -> WordList | None:
        word_list = self.load(list_id)
        if word_list is None:
            return None
        word_list.remove_word(word)
        self.save(word_list)
        return word_list

    def to_dict(self, word_list: WordList) -> dict[str, Any]:
        return word_list.model_dump(mode="json")


__all__ = ["WordEntry", "WordList", "WordListStore"]
