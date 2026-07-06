"""
Curricula API Router
====================

Read-only listing of bundled mastery-path curricula. A curriculum is a vetted
scope-and-sequence (module/KP tree) that ``mastery_path`` pre-seeds before the
chat loop starts when the per-turn config names one
(``--config curriculum=vn_g2_math``).

Curricula ship inside the package (read-only, like the spelling packs); this
router surfaces them so the UI can render a picker. Use the curriculum ``id``
as the ``curriculum`` config value.

Mounted at ``/api/v1/curricula``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from deeptutor.learning.curricula import list_curricula, load_curriculum

router = APIRouter()


@router.get("")
async def list_all_curricula(language: str = "en") -> dict[str, list[dict[str, object]]]:
    """List bundled curricula for a language (lightweight metadata only)."""
    return {"curricula": list_curricula(language)}


@router.get("/{curriculum_id}")
async def get_curriculum(curriculum_id: str, language: str = "en") -> dict[str, object]:
    """Get one curriculum with its full module/KP tree."""
    curriculum = load_curriculum(language, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail=f"Curriculum '{curriculum_id}' not found")
    return {"curriculum": curriculum}


__all__ = ["router"]
