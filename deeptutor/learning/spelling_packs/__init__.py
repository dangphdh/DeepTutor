"""Curated spelling/vocabulary packs shipped with the package.

These are small, grade-appropriate English word lists (animals, colors, family,
school, sight words) bundled inside ``deeptutor.learning.spelling_packs`` so a
family can start practising spelling immediately without authoring a list.
The dad can also add custom lists via the WordListStore / the Spelling settings
page; curated packs and custom lists are surfaced together by the wordlists
API router.

Packs are read-only JSON loaded via ``importlib.resources`` (the same mechanism
the mastery prompts use), so they survive a packaged install. Each pack file
has the shape::

    {"name": str, "language": str, "words": [{"word": str, "example_sentence": str}]}
"""

from __future__ import annotations

from importlib import resources
import json
from typing import Any


def _read_pack(lang: str, pack_id: str) -> dict[str, Any] | None:
    """Read one pack JSON. Returns None if it doesn't exist."""
    try:
        text = resources.files(__package__).joinpath(lang, f"{pack_id}.json").read_text(encoding="utf-8")
        return json.loads(text)
    except (FileNotFoundError, FileNotFoundError):
        return None
    except Exception:
        return None


def list_packs(language: str = "en") -> list[dict[str, Any]]:
    """Return all curated packs for a language as ``[{id, name, language, word_count}]``.

    Lightweight metadata only — call ``load_pack`` to get the full word list.
    """
    lang = (language or "en").strip().lower()
    out: list[dict[str, Any]] = []
    try:
        for entry in resources.files(__package__).joinpath(lang).iterdir():
            if not entry.name.endswith(".json"):
                continue
            try:
                data = json.loads(entry.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append(
                {
                    "id": entry.name.removesuffix(".json"),
                    "name": data.get("name", entry.name.removesuffix(".json")),
                    "language": data.get("language", lang),
                    "word_count": len(data.get("words", [])),
                    "curated": True,
                }
            )
    except (FileNotFoundError, FileNotFoundError):
        # No packs for this language yet — return empty, callers fall back.
        return out
    return sorted(out, key=lambda p: p["name"])


def load_pack(language: str, pack_id: str) -> dict[str, Any] | None:
    """Load one curated pack with its full word list. None if not found."""
    lang = (language or "en").strip().lower()
    pack = _read_pack(lang, pack_id)
    if pack is None:
        return None
    pack.setdefault("id", pack_id)
    pack.setdefault("language", lang)
    pack["curated"] = True
    return pack


__all__ = ["list_packs", "load_pack"]
