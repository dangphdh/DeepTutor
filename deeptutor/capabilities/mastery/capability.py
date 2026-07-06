"""Mastery Path capability — mastery-based tutoring driven by the chat loop.

There is no bespoke state machine here anymore. The chat agent loop IS the
tutor: this capability only marks the turn as mastery mode and resolves the
active path id, then runs the standard agentic chat pipeline. The pipeline
mounts the mastery tools (``mastery_status`` / ``mastery_quiz`` /
``mastery_grade`` / ``mastery_assess`` / ``mastery_build``) and injects the
tutor playbook; the pure engine in :mod:`deeptutor.learning` owns the hard,
per-type mastery gate and the spaced-repetition arithmetic.

Design axiom (shared with chat): the intelligence lives at the loop's exit —
the model decides what to teach and how to question — while the gate that
decides *whether the learner may advance* is a deterministic engine call.

When the per-turn config names a curriculum (``--config curriculum=<id>``),
the path is pre-seeded deterministically *before* the loop starts: the model's
first ``mastery_status`` call sees a populated vetted map and never reaches the
"design a path" branch. This removes the model from authoring the
scope-and-sequence while keeping it in charge of teaching each objective.
"""

from __future__ import annotations

import logging
import re

from deeptutor.agents.chat.agentic_pipeline import AgenticChatPipeline
from deeptutor.capabilities.mastery.tools import MASTERY_TOOL_NAMES, _parse_modules
from deeptutor.core.capability_protocol import BaseCapability, CapabilityManifest
from deeptutor.core.context import UnifiedContext
from deeptutor.core.stream_bus import StreamBus

logger = logging.getLogger(__name__)

_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_path_id(raw: str) -> str:
    """Make *raw* a safe storage key (matches ``LearningStore`` path guard)."""
    cleaned = _UNSAFE_ID_CHARS.sub("_", raw).strip("_")
    return cleaned or "default"


def resolve_mastery_path_id(context: UnifiedContext) -> str:
    """Resolve which learner-path the turn operates on.

    Prefers an explicit ``mastery_path_id`` set by the frontend (so the tutor
    and the build wizard / dashboard agree on one storage key), then a book
    reference, then the session id for an ad-hoc path built inside a chat.
    """
    explicit = str(context.metadata.get("mastery_path_id") or "").strip()
    if explicit:
        return _sanitize_path_id(explicit)
    refs = (context.metadata or {}).get("book_references", [])
    if refs:
        ref = refs[0]
        if isinstance(ref, str) and ref.strip():
            return _sanitize_path_id(ref)
        if isinstance(ref, dict):
            candidate = str(ref.get("book_id") or ref.get("id") or "").strip()
            if candidate:
                return _sanitize_path_id(candidate)
    return _sanitize_path_id(str(context.session_id or "default"))


def _resolve_curriculum_id(context: UnifiedContext) -> str:
    """Read the curriculum id from per-turn config (``--config curriculum=...``)."""
    # Prefer config_overrides (the validated per-turn config), then metadata
    # (set by the frontend). Empty string = no curriculum requested.
    raw = ""
    overrides = getattr(context, "config_overrides", None)
    if isinstance(overrides, dict):
        raw = str(overrides.get("curriculum") or "").strip()
    if not raw:
        raw = str((context.metadata or {}).get("curriculum") or "").strip()
    return raw


def _seed_curriculum_if_needed(
    path_id: str, curriculum_id: str, language: str
) -> bool:
    """Pre-seed a mastery path from a bundled curriculum.

    Returns True if a path was seeded (or already seeded by a prior turn —
    the curriculum is in effect), False if no curriculum matched. Idempotent:
    a path that already has modules is left untouched so the learner's progress
    (mastery levels, spaced-repetition state) survives across turns. Failures
    (missing file, parse error) fall through gracefully to the model-authored
    "design a path" flow rather than crashing the turn.
    """
    curriculum_id = (curriculum_id or "").strip()
    if not curriculum_id:
        return False
    try:
        from deeptutor.learning.curricula import load_curriculum
        from deeptutor.learning.service import LearningService

        curriculum = load_curriculum(language, curriculum_id)
        if curriculum is None:
            logger.warning(
                "Curriculum %r not found for language %r; falling back to "
                "model-authored path.",
                curriculum_id,
                language,
            )
            return False
        service = LearningService()
        progress = service.get_or_create(path_id)
        if progress.modules:
            # Already seeded (resumed turn) — leave learner progress intact.
            return True
        modules, error = _parse_modules(curriculum.get("modules"), path_id, 0)
        if error or not modules:
            logger.warning("Curriculum %r produced no modules: %s", curriculum_id, error)
            return False
        service.replace_modules(progress, modules)
        if modules and modules[0].knowledge_points:
            progress.current_module_id = modules[0].id
            progress.current_kp_index = 0
        service.save(progress)
        logger.info(
            "Seeded mastery path %r from curriculum %r (%d modules).",
            path_id,
            curriculum_id,
            len(modules),
        )
        return True
    except Exception as exc:  # pragma: no cover - defensive, never crash the turn
        logger.warning(
            "Failed to seed curriculum %r for path %r: %s — falling back to "
            "model-authored path.",
            curriculum_id,
            path_id,
            exc,
        )
        return False


class MasteryPathCapability(BaseCapability):
    manifest = CapabilityManifest(
        name="mastery_path",
        description=(
            "Mastery-based tutoring: the chat agent loop drives an adaptive "
            "mastery path with a hard, per-type mastery gate and spaced review."
        ),
        stages=["responding"],
        tools_used=[*MASTERY_TOOL_NAMES, "rag", "read_source", "ask_user"],
        cli_aliases=["mastery"],
    )

    async def run(self, context: UnifiedContext, stream: StreamBus) -> None:
        context.metadata["mastery_mode"] = True
        path_id = resolve_mastery_path_id(context)
        # If the per-turn config names a curriculum, override the path id so the
        # vetted scope-and-sequence lives under a stable, resumable key and
        # never collides with book-derived or ad-hoc session paths. Then seed
        # the path (idempotently) before the loop sees it.
        curriculum_id = _resolve_curriculum_id(context)
        if curriculum_id:
            path_id = _sanitize_path_id(f"curriculum_{curriculum_id}")
            _seed_curriculum_if_needed(path_id, curriculum_id, context.language)
        context.metadata["mastery_path_id"] = path_id
        pipeline = AgenticChatPipeline(language=context.language)
        await pipeline.run(context, stream)


__all__ = ["MasteryPathCapability", "resolve_mastery_path_id"]
