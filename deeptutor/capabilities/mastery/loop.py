"""Mastery path loop-capability hooks."""

from __future__ import annotations

from importlib import resources
from typing import Any

from deeptutor.capabilities.mastery.tools import MASTERY_TOOL_NAMES
from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.context import UnifiedContext


class MasteryLoopCapability:
    """Turn-scoped integration for mastery-path tutoring.

    Reuses the full chat tool surface (rag / read_source / ask_user / … under
    the same user toggles as chat) and adds the mastery engine tools on top.
    """

    name = "mastery"
    owned_tools = MASTERY_TOOL_NAMES

    def is_active(self, context: UnifiedContext) -> bool:
        return bool(context.metadata.get("mastery_mode"))

    def system_block(
        self,
        context: UnifiedContext,
        *,
        language: str,
        prompts: dict[str, Any],
    ) -> PromptBlock | None:
        if not self.is_active(context):
            return None
        override = _prompt_text(prompts, ("mastery", "system"))
        content = override or _load_system_prompt(language)
        return PromptBlock("mastery_tutor", content)

    def augment_kwargs(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        context: UnifiedContext,
    ) -> dict[str, Any]:
        if self.is_active(context) and tool_name in MASTERY_TOOL_NAMES:
            updated = dict(kwargs)
            updated["_mastery_path_id"] = str(context.metadata.get("mastery_path_id") or "").strip()
            updated["_session_id"] = str(context.session_id or "").strip()
            updated["_turn_id"] = str(context.metadata.get("turn_id") or "").strip()
            # Surface Hint Mode state so mastery_grade can gate its feedback
            # without re-reading context (mirrors solve loop's _hint_mode).
            updated["_hint_mode"] = bool(getattr(context, "hint_mode", False))
            updated["_max_hints"] = int(getattr(context, "max_hints", 3) or 3)
            return updated
        return kwargs

    def pre_loop_seed(self, context: UnifiedContext) -> str:
        _ = context
        return ""


def _prompt_text(prompts: dict[str, Any], path: tuple[str, ...]) -> str:
    value: Any = prompts
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return value if isinstance(value, str) and value else ""


def _load_system_prompt(language: str) -> str:
    raw = (language or "en").lower().strip()
    if raw.startswith("zh"):
        lang = "zh"
    elif raw.startswith("vi"):
        lang = "vi"
    else:
        lang = "en"
    prompt = resources.files(__package__).joinpath("prompts", lang, "system.md")
    try:
        return prompt.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        # Missing translation file — fall back to English rather than crash.
        prompt = resources.files(__package__).joinpath("prompts", "en", "system.md")
        return prompt.read_text(encoding="utf-8").strip()


__all__ = ["MasteryLoopCapability"]
