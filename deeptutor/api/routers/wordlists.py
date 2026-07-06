"""
Word Lists API Router
=====================

CRUD endpoints for spelling/vocabulary word lists. Surfaces two kinds:

- **Curated packs** — read-only, grade-appropriate packs shipped inside the
  package (animals, colors, family, school, sight words). Listed with
  ``curated: true`` and cannot be modified.
- **Custom lists** — dad-authored lists stored as JSON in the user's workspace
  (``workspace/learning/wordlists/``). Full CRUD.

A list is the dad-facing concept ("this week's words"); when the child practises
spelling via ``mastery_path``, a builder turns the active list into ``MEMORY``
knowledge points with ``question_type="spelling"``.

Mounted at ``/api/v1/wordlists``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deeptutor.learning.spelling_packs import list_packs, load_pack
from deeptutor.learning.wordlist_store import WordListStore

router = APIRouter()


def _store() -> WordListStore:
    return WordListStore()


class CreateWordListRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    language: str = "en"
    words: list[str] = Field(default_factory=list)


class AddWordsRequest(BaseModel):
    words: list[str] = Field(..., min_length=1)
    example_sentence: str = ""


@router.get("")
async def list_wordlists(language: str = "en") -> dict[str, list[dict[str, object]]]:
    """List curated packs + the user's custom word lists."""
    packs = list_packs(language)
    custom = [_summary(wl) for wl in _store().list_all()]
    return {"curated": packs, "custom": custom}


@router.get("/{list_id}")
async def get_wordlist(list_id: str, language: str = "en") -> dict[str, object]:
    """Get one word list (curated pack or custom) with its full word list."""
    # Try custom first (user-owned), then curated.
    custom = _store().load(list_id)
    if custom is not None:
        return {"list": custom.model_dump(mode="json"), "curated": False}
    pack = load_pack(language, list_id)
    if pack is not None:
        return {"list": pack, "curated": True}
    raise HTTPException(status_code=404, detail=f"Word list '{list_id}' not found")


@router.post("")
async def create_wordlist(req: CreateWordListRequest) -> dict[str, object]:
    """Create a custom word list."""
    wl = _store().create(req.name, language=req.language, words=req.words)
    return {"list": wl.model_dump(mode="json")}


@router.post("/{list_id}/words")
async def add_words(list_id: str, req: AddWordsRequest) -> dict[str, object]:
    """Add words to a custom word list (curated packs are read-only)."""
    wl = _store().add_words(list_id, req.words, example_sentence=req.example_sentence)
    if wl is None:
        raise HTTPException(status_code=404, detail=f"Custom word list '{list_id}' not found")
    return {"list": wl.model_dump(mode="json")}


@router.delete("/{list_id}/words/{word}")
async def remove_word(list_id: str, word: str) -> dict[str, object]:
    """Remove a word from a custom word list."""
    wl = _store().remove_word(list_id, word)
    if wl is None:
        raise HTTPException(status_code=404, detail=f"Custom word list '{list_id}' not found")
    return {"list": wl.model_dump(mode="json")}


@router.delete("/{list_id}")
async def delete_wordlist(list_id: str) -> dict[str, object]:
    """Delete a custom word list (curated packs cannot be deleted)."""
    deleted = _store().delete(list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Custom word list '{list_id}' not found")
    return {"deleted": True, "id": list_id}


def _summary(wl) -> dict[str, object]:
    """Lightweight metadata for list endpoints (no full word bodies)."""
    return {
        "id": wl.id,
        "name": wl.name,
        "language": wl.language,
        "word_count": len(wl.words),
        "curated": False,
        "created_at": wl.created_at,
        "updated_at": wl.updated_at,
    }


__all__ = ["router"]
