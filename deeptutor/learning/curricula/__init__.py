"""Bundled mastery-path curricula (vetted scope-and-sequence).

A curriculum is a structured module/KP tree that ``mastery_path`` pre-seeds
before the chat loop starts, so the model follows a vetted scope-and-sequence
instead of inventing objectives ad hoc. The dad picks one via per-turn config
(``--config curriculum=vn_g2_math``); ``MasteryPathCapability.run`` loads it,
overrides the path id to ``curriculum_<id>`` (stable, resumable), and seeds
the ``LearningProgress`` modules via the same ``replace_modules`` seam the
build tool uses.

The dict shape is exactly what ``_parse_modules`` (in
``deeptutor.capabilities.mastery.tools``) already consumes::

    {
      "id": "vn_g2_math",
      "name": "Toán lớp 2 (VN Grade 2 Math)",
      "language": "vi",
      "modules": [
        {"name": "Số đến 1000", "knowledge_points": [
          {"name": "Hàng đơn vị, chục, trăm", "type": "concept"},
          {"name": "So sánh số đến 1000", "type": "procedure"}
        ]}
      ]
    }

Loaded via ``importlib.resources`` (same mechanism as the mastery prompts and
the spelling packs) so files survive a packaged install.
"""

from __future__ import annotations

from importlib import resources
import json
from typing import Any


def _read_curriculum(lang: str, curriculum_id: str) -> dict[str, Any] | None:
    """Read one curriculum JSON. Returns None if it doesn't exist."""
    try:
        text = (
            resources.files(__package__)
            .joinpath(lang, f"{curriculum_id}.json")
            .read_text(encoding="utf-8")
        )
        return json.loads(text)
    except (FileNotFoundError, FileNotFoundError):
        return None
    except Exception:
        return None


def list_curricula(language: str = "en") -> list[dict[str, Any]]:
    """Return all bundled curricula for a language.

    Lightweight metadata only — call ``load_curriculum`` to get the full
    module/KP tree. Each item: ``{id, name, language, module_count, kp_count}``.
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
            modules = data.get("modules", [])
            kp_count = sum(len(m.get("knowledge_points", [])) for m in modules)
            out.append(
                {
                    "id": data.get("id", entry.name.removesuffix(".json")),
                    "name": data.get("name", entry.name.removesuffix(".json")),
                    "language": data.get("language", lang),
                    "module_count": len(modules),
                    "kp_count": kp_count,
                    "curated": True,
                }
            )
    except (FileNotFoundError, FileNotFoundError):
        return out
    return sorted(out, key=lambda c: c["name"])


def load_curriculum(language: str, curriculum_id: str) -> dict[str, Any] | None:
    """Load one curriculum with its full module/KP tree. None if not found.

    If ``language`` doesn't match the curriculum's own declared language, the
    loader still tries the requested language folder first, then falls back to
    the curriculum's declared language — so ``load_curriculum("vi", "esl_starter")``
    finds the English ESL curriculum even when asked under Vietnamese.
    """
    curriculum_id = (curriculum_id or "").strip()
    if not curriculum_id:
        return None
    lang = (language or "en").strip().lower()
    # Try the requested language folder first, then the curriculum's own.
    data = _read_curriculum(lang, curriculum_id)
    if data is None:
        declared = None
        # Probe the other language folders as a fallback (curricula are few).
        for probe in ("en", "vi", "zh"):
            if probe == lang:
                continue
            data = _read_curriculum(probe, curriculum_id)
            if data is not None:
                declared = probe
                break
        if data is None:
            return None
        lang = declared or lang
    data.setdefault("id", curriculum_id)
    data.setdefault("language", lang)
    data["curated"] = True
    return data


__all__ = ["list_curricula", "load_curriculum"]
