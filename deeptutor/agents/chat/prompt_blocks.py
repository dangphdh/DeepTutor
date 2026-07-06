"""Structured prompt assembly for the chat agent loop."""

from __future__ import annotations

from typing import Any

from deeptutor.capabilities.protocol import PromptBlock
from deeptutor.core.context import UnifiedContext
from deeptutor.services.prompt.language import append_language_directive


def _kid_mode_directive() -> str:
    """The Kid Mode voice block.

    Sits AFTER capability playbooks (mastery, solve) and AFTER any custom
    persona in the block order, so it overrides their tone without touching
    their procedure. Like ``partner_turn_policy``, it overrides style only —
    never safety, tool-truthfulness, or runtime constraints. The mastery gate
    stays hard: Kid Mode changes the VOICE, never the bar.
    """
    return (
        "[Kid Mode — overrides tone, not safety, tool-truthfulness, or the "
        "mastery gate]\n"
        "You are talking to a 7-year-old child. Follow EVERY rule:\n"
        "- Use short, simple sentences. One idea per sentence. No abstract "
        "jargon, no long compound clauses.\n"
        "- Speak in a warm, playful, encouraging voice. Praise effort often "
        "(e.g. \"Giỏi quá!\", \"Cố lên nhé!\", \"Đúng rồi!\").\n"
        "- Use concrete examples from a child's world: fruits, animals, toys, "
        "family, school, friends. Avoid abstract adult analogies.\n"
        "- Give ONE hint, ONE step, or ONE sub-question at a time. Never dump "
        "the full answer. Wait for the child to respond before continuing.\n"
        "- After explaining a small idea, ask a tiny check question and wait.\n"
        "- When the child is wrong, be gentle first, then guide: \"Gần đúng "
        "rồi! Thử lại nào.\" Never say \"sai\" / \"wrong\" bluntly.\n"
        "- Use emoji to make it friendly (🍎 ⭐ 🎉 🐢), but never let emoji "
        "replace real words in a sentence.\n"
        "- Keep the mastery bar FIRM. Kid Mode changes the VOICE, never the "
        "gate. An objective only clears when the child truly demonstrates it — "
        "but you explain the gate's verdict in kind, simple words.\n"
        "- If the child seems frustrated or tired after 2-3 tries, suggest a "
        "small break or an easier sub-step. Never push past frustration."
    )


def _hint_mode_directive(max_hints: int) -> str:
    """The Hint Mode Socratic-coaching block.

    Sits AFTER capability playbooks (mastery, solve) AND after kid_mode so it
    stacks on top of both. This is the SOFT layer — the coaching voice. The
    HARD layer (deterministic hint-budget gate) lives in the tools:
    ``solve_finish_step`` returns a hint instruction until the budget is
    exhausted (mirrors ``solve_replan``), and ``mastery_grade`` keeps the
    pending question alive with a hint instruction on wrong answers. In plain
    chat there is no engine, so this directive is the only enforcement —
    explicit and strong, but not deterministic.
    """
    n = int(max_hints) if max_hints and max_hints > 0 else 3
    return (
        "[Hint Mode — Socratic coaching, overrides the default \"answer "
        "directly\" rule]\n"
        "You are coaching the learner to think, not solving for them. "
        f"Budget: {n} hint(s) before the answer may be revealed.\n"
        "Rules:\n"
        "- NEVER reveal the full answer on the first response to a question "
        "or problem.\n"
        "- Give the SMALLEST useful hint first — one hint per turn only.\n"
        "- After each hint, ask a guiding question and WAIT for the learner "
        "(use the ask_user tool if available, or end your turn with a "
        "question and wait for their reply).\n"
        "- Escalate gradually: hint 1 = a gentle nudge or reframe; hint 2 = a "
        "bigger clue (point at the relevant rule/method); hint 3 = a near-"
        "answer walkthrough of the method, stopping just short of the final "
        "value.\n"
        "- In deep_solve and mastery_path, the tool result will explicitly "
        "say when the budget is exhausted (\"reveal the full answer\") — only "
        "THEN write the complete step-by-step answer. Do not pre-empt it.\n"
        "- If the learner explicitly says they want the answer (\"I give up\", "
        "\"show me\", \"tell me the answer\"), you MAY reveal it — consent "
        "overrides the budget.\n"
        "- Praise the learner's thinking even when it's wrong; never say "
        "\"sai\"/\"wrong\" bluntly — say \"Gần đúng rồi, thử lại nào.\"\n"
        "- This overrides \"be concise\" and \"answer directly\". It does NOT "
        "override safety, tool-truthfulness, or the mastery gate."
    )


class ChatPromptAssembler:
    """Build system prompts from explicit, category-named blocks."""

    def __init__(self, *, prompts: dict[str, Any], language: str) -> None:
        self.prompts = prompts
        # Preserve the full language code so the right language directive is
        # appended below. Only zh is special-cased for the empty-tool-list
        # fallback string; every other code falls back to the English fallback
        # string but keeps its own directive (vi, ja, …).
        raw = (language or "en").strip().lower()
        if raw.startswith("zh"):
            self.language = "zh"
        elif raw.startswith("vi"):
            self.language = "vi"
        else:
            self.language = "en"

    def system_prompt(
        self,
        *,
        context: UnifiedContext,
        tool_manifest: str,
        kb_note: str = "",
        deferred_tools_manifest: str = "",
        notebook_manifest: str = "",
        workspace_note: str = "",
        capability_blocks: list[PromptBlock] | None = None,
        include_tool_manifest: bool = True,
    ) -> str:
        blocks = self.blocks(
            context=context,
            tool_manifest=tool_manifest,
            kb_note=kb_note,
            deferred_tools_manifest=deferred_tools_manifest,
            notebook_manifest=notebook_manifest,
            workspace_note=workspace_note,
            capability_blocks=capability_blocks,
            include_tool_manifest=include_tool_manifest,
        )
        joined = "\n\n---\n\n".join(
            f"## {block.name}\n{block.content.strip()}" for block in blocks if block.content.strip()
        )
        return append_language_directive(joined, self.language)

    def blocks(
        self,
        *,
        context: UnifiedContext,
        tool_manifest: str,
        kb_note: str = "",
        deferred_tools_manifest: str = "",
        notebook_manifest: str = "",
        workspace_note: str = "",
        capability_blocks: list[PromptBlock] | None = None,
        include_tool_manifest: bool = True,
    ) -> list[PromptBlock]:
        blocks: list[PromptBlock] = [
            PromptBlock("general", self._general_block(context)),
            PromptBlock("runtime_policy", self._t("runtime_policy")),
            PromptBlock("loop", self._t("loop.system")),
        ]
        # Capability playbooks sit high so they frame the whole turn when active;
        # empty blocks are omitted by ``system_prompt``'s join.
        blocks.extend(capability_blocks or [])
        if context.persona_context:
            blocks.append(PromptBlock("persona_style", context.persona_context))
        if context.kid_mode:
            # Sits after capability playbooks AND persona_style so it stacks
            # on top of both — softening tone for a young child without
            # rewriting any capability's procedure. See _kid_mode_directive.
            blocks.append(PromptBlock("kid_mode", _kid_mode_directive()))
        if context.hint_mode:
            # The soft coaching layer; the hard budget gate lives in the tools
            # (solve_finish_step / mastery_grade). See _hint_mode_directive.
            blocks.append(
                PromptBlock("hint_mode", _hint_mode_directive(context.max_hints))
            )
        partner_policy = self._partner_turn_policy(context)
        if partner_policy:
            blocks.append(PromptBlock("partner_turn_policy", partner_policy))
        if context.memory_context:
            blocks.append(PromptBlock("memory", context.memory_context))
        if include_tool_manifest:
            tools = tool_manifest or self._fallback_empty_tool_list()
            if kb_note:
                tools = f"{kb_note}\n\n{tools}"
            blocks.append(PromptBlock("tools", tools))
        elif kb_note:
            blocks.append(PromptBlock("knowledge_base_note", kb_note))
        if context.skills_manifest:
            blocks.append(PromptBlock("skills", context.skills_manifest))
        if context.source_manifest:
            blocks.append(PromptBlock("sources", context.source_manifest))
        if deferred_tools_manifest:
            blocks.append(PromptBlock("extended_tools", deferred_tools_manifest))
        if notebook_manifest:
            blocks.append(PromptBlock("notebooks", notebook_manifest))
        if workspace_note:
            blocks.append(PromptBlock("workspace", workspace_note))
        # Volatile content deliberately gets NO system block: the KB seed
        # rides in the trailing user message, so the system prompt stays
        # byte-stable for the whole turn (every loop round shares one prefix).
        return blocks

    def _general_block(self, context: UnifiedContext) -> str:
        """Product identity, or the partner identity when one is present.

        Partner turns carry ``metadata["agent_identity"]`` (user-given name +
        description); their identity comes from that and the Soul block, so
        the "You are DeepTutor" general is swapped for ``general_partner``.
        Chat turns carry no identity and render the general block unchanged.
        """
        identity = context.metadata.get("agent_identity")
        name = ""
        if isinstance(identity, dict):
            name = str(identity.get("name") or "").strip()
        if not name:
            return self._t("general")
        content = self._t(
            "general_partner",
            default='You are a companion created by the user. The name the user gave you is "{name}".',
        ).format(name=name)
        description = str(identity.get("description") or "").strip()
        if description:
            description_line = self._t(
                "general_partner_description",
                default="The user's description of you: {description}",
            ).format(description=description)
            content = f"{content}\n{description_line}"
        return content

    def _partner_turn_policy(self, context: UnifiedContext) -> str:
        identity = context.metadata.get("agent_identity")
        if not isinstance(identity, dict):
            return ""
        if not str(identity.get("name") or "").strip():
            return ""
        return self._t("partner_turn_policy", default="")

    def user_message(
        self,
        *,
        context: UnifiedContext,
        kb_seed: str = "",
    ) -> str:
        template = self._t("loop.user", default="{user_message}")
        try:
            content = template.format(user_message=context.user_message)
        except (KeyError, IndexError, ValueError):
            content = context.user_message
        if kb_seed:
            content = f"{content}\n\n{kb_seed}"
        return content

    def finish_exhausted_instruction(self) -> str:
        return self._t(
            "loop.finish_exhausted",
            default=(
                "The round budget ran out before every gap was closed. Stop "
                "calling tools and answer now with what you have, noting "
                "briefly what remains uncertain."
            ),
        )

    def _fallback_empty_tool_list(self) -> str:
        return "- 无" if self.language == "zh" else "- none"

    def _t(self, key: str, default: str = "") -> str:
        value: Any = self.prompts
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value if isinstance(value, str) else default


__all__ = ["ChatPromptAssembler", "PromptBlock"]
