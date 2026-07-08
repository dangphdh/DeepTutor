# DeepTutor — Agent-Native Architecture

## Overview

DeepTutor is an **agent-native** intelligent learning companion organized
around a two-layer plugin model — single-shot **Tools** invoked by the
LLM, and multi-stage **Capabilities** that take over a turn — exposed
through three entry points: CLI, WebSocket API, and Python SDK.

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /api/v1/ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │              ChatOrchestrator                    │
              │   routes UnifiedContext → selected Capability    │
              │   (defaults to `chat`)                           │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

All capabilities emit on a shared `StreamBus`; the orchestrator fans
events out to consumers. Runtime settings live in
`data/user/settings/*.json` — project-root `.env` files are intentionally
ignored.

### Level 1 — Tools

Single-function tools the LLM picks on demand. Four user-toggleable tools
surface in `/settings/tools`:

| Tool           | Description                                   |
| -------------- | --------------------------------------------- |
| `brainstorm`   | Breadth-first idea exploration with rationale |
| `web_search`   | Web search with citations                     |
| `paper_search` | arXiv preprint search                         |
| `reason`       | Dedicated deep-reasoning LLM call             |

The rest are **context-gated**: the chat capability auto-mounts them from
`ToolMountFlags` (presence of a KB, attachments, sandbox availability, …), and
any of them can also be force-enabled via `--tool`. Auto-mounted set: `rag`,
`read_source`, `read_memory`, `write_memory`, `read_skill`, `load_tools`,
`exec`, `code_execution` (sandboxed Python: NL intent → code → run),
`list_notebook`, `write_note`, `web_fetch`, `github`, `cron`,
`ask_user` (pauses the turn and resumes with the user's reply), plus the
mastery-path tools. `geogebra_analysis` is parked under
`COMING_SOON_TOOL_TYPES`.

### Level 2 — Capabilities

Multi-stage pipelines that own the turn:

| Capability       | Stages                                                |
| ---------------- | ----------------------------------------------------- |
| `chat`           | exploring → responding (single agentic loop, default) |
| `mastery_path`   | responding (Guided Learning — chat loop + mastery tools, gated per topic type) |
| `deep_solve`     | planning → reasoning → writing                        |
| `deep_question`  | ideation → generation                                 |
| `deep_research`  | rephrasing → decomposing → researching → reporting    |
| `visualize`      | analyzing → generating → reviewing (SVG / Chart.js / Mermaid / HTML; or routes to Manim sub-stages via `render_type`) |
| `math_animator`  | concept_analysis → concept_design → code_generation → code_retry → summary → render_output |

All capabilities converge on `emit_capability_result()` in
`deeptutor/capabilities/_shared.py` so every turn emits the same envelope
(response payload + `cost_summary` from `UsageTracker`). Status copy and
prompts are i18n'd via `capabilities/prompts/{en,zh}/<name>.yaml`.

## CLI Usage

```bash
# Install
pip install deeptutor      # Full app (CLI + Web/API + packaged Web assets)
pip install deeptutor-cli  # CLI-only

# Run any capability
deeptutor run chat "Explain Fourier transform"
deeptutor run deep_solve "Solve x^2=4" -t rag --kb my-kb
deeptutor run visualize "Animate sine wave" --config render_mode=manim_video

# Interactive REPL
deeptutor chat
# (inside the REPL: /regenerate or /retry re-runs the last user message)

# Partners (IM-connected companions)
deeptutor partner list

# Knowledge bases, memory, server
deeptutor kb list
deeptutor kb create my-kb --doc textbook.pdf
deeptutor memory show
deeptutor serve --port 8001       # API server only
deeptutor start                   # backend + frontend together
```

## Key Files

| Path                                       | Purpose                              |
| ------------------------------------------ | ------------------------------------ |
| `deeptutor/runtime/orchestrator.py`        | `ChatOrchestrator` — unified entry   |
| `deeptutor/runtime/launcher.py`            | Backend + frontend lifecycle / port discovery |
| `deeptutor/runtime/registry/`              | Tool + Capability registries         |
| `deeptutor/runtime/bootstrap/builtin_capabilities.py` | Built-in capability class paths |
| `deeptutor/services/config/runtime_settings.py` | JSON settings + process-env overrides |
| `deeptutor/core/stream.py`, `stream_bus.py` | StreamEvent protocol + async fan-out |
| `deeptutor/core/tool_protocol.py`          | `BaseTool` + `ToolDefinition`         |
| `deeptutor/core/capability_protocol.py`    | `BaseCapability` + `CapabilityManifest` |
| `deeptutor/core/context.py`                | `UnifiedContext` dataclass            |
| `deeptutor/tools/builtin/__init__.py`      | All built-in tool wrappers           |
| `deeptutor/capabilities/`                  | Built-in capability implementations  |
| `deeptutor/app.py`                         | `DeepTutorApp` — Python SDK facade    |
| `deeptutor_cli/main.py`                    | Typer CLI entry point                |
| `deeptutor/api/routers/unified_ws.py`      | Unified WebSocket endpoint           |

## Dependency Layers

Public install paths and source extras are defined in `pyproject.toml`.
Requirements files mirror the same dependency groups for Docker/CI installs.

```
pip install deeptutor      — Full app (CLI + Web/API + packaged Web assets)
pip install deeptutor-cli  — CLI-only (LLM + RAG + providers + document parsing)
pip install -e .           — Source install for development

Source extras (.[ extra ], defined in pyproject.toml):
.[cli]            — CLI-only dependency set
.[server]         — Web/API server dependencies
.[partners]       — Partner channel SDKs + MCP client  (legacy alias: .[tutorbot])
.[matrix]         — Matrix channel for Partners (matrix-nio; needs libolm)
.[matrix-e2e]     — Matrix with end-to-end encryption (matrix-nio[e2e])
.[math-animator]  — Manim addon (powers `visualize` Manim renders + `deeptutor run math_animator`)
.[dev]            — Test / lint tooling
.[all]            — Everything above
```

## Young-Learner Subsystem

Five first-class features that work together to make DeepTutor a daily
companion for a young child (e.g. a 7-year-old learning math + ESL). They are
all *additive* — none rewrites an existing seam, and each composes with the
mastery gate, spaced repetition, and the chat agent loop.

| Feature | Mechanism | Key files |
| ------- | --------- | --------- |
| **Vietnamese (`vi`)** | First-class language code: `parse_language()` recognizes `vi`, the prompt manager falls back `vi → en`, the language directive forces Vietnamese output. (Pre-existing bug: unknown codes defaulted to `zh` — fixed to `en`.) | `services/config/loader.py`, `services/prompt/{language,manager}.py`, `agents/chat/prompts/vi/`, `capabilities/{mastery,solve}/prompts/vi/`, `web/locales/vi/` |
| **Kid Mode** | Per-user toggle persisted in `interface.json`. `UnifiedContext.kid_mode` → a `kid_mode` prompt block injected in `ChatPromptAssembler.blocks()` *after* capability playbooks, so it overrides tone without touching procedure. The mastery gate stays hard — Kid Mode changes the VOICE, never the bar. | `core/context.py`, `services/session/turn_runtime.py`, `agents/chat/prompt_blocks.py`, `api/routers/settings.py` (`PUT /kid-mode`) |
| **Hint Mode** | Two-layer, matching the codebase axiom "intelligence at the loop's exit; deterministic spine through tools". Soft: a `hint_mode` prompt block. Hard: `SolveSession.hints_given/max_hints/give_hint()` mirrors `solve_replan`'s budget, gating `solve_finish_step`'s "write the final answer" instruction; `PendingQuestion.hints_given` gates `mastery_grade`'s reveal. | `capabilities/solve/{session,tools,loop}.py`, `capabilities/mastery/{tools,loop}.py`, `learning/models.py`, `agents/chat/prompt_blocks.py`, `api/routers/settings.py` (`PUT /hint-mode`) |
| **Spelling Trainer** | New `question_type="spelling"` in `grade_answer()` — exact char-match (a 1-char-off spelling is wrong). A `spelling_diff()` helper produces targeted hints via `SequenceMatcher.get_opcodes()` ("you're missing the letter 'l'"). Bundled curated packs + `WordListStore` (JSON-backed, mirrors `LearningStore`) for custom lists. | `learning/{grading,wordlist_store}.py`, `learning/spelling_packs/`, `capabilities/mastery/tools.py`, `api/routers/wordlists.py` (`/api/v1/wordlists`) |
| **Pronunciation Check** | New `question_type="pronunciation"` with lenient grading via normalized Levenshtein distance ("skool"→"school" passes; "dog"→"cat" fails). A `pronunciation_diff()` helper surfaces "you said 'skool', the word is 'school'". The frontend 🔊/🎤 buttons reuse `useTTSPlayback` + `useVoiceRecorder` (the recorder now forwards the UI language to STT). | `learning/grading.py`, `capabilities/mastery/tools.py`, `web/hooks/useVoiceRecorder.ts`, `web/components/chat/home/AskUserOptions.tsx` |
| **Curriculum YAML** | Vetted scope-and-sequence JSON under `learning/curricula/{en,vi}/`, loaded via `importlib.resources`. `MasteryPathCapability.run()` *pre-seeds* the path before the loop starts (path_id `curriculum_<id>`), so the model's first `mastery_status` returns `active` and it never enters the "design a path" branch. Idempotent + resumable. Picked via `MasteryRequestConfig.curriculum` (per-turn config: `--config curriculum=...`). | `learning/curricula/`, `capabilities/mastery/capability.py`, `runtime/request_contracts.py`, `api/routers/curricula.py` (`/api/v1/curricula`) |

**Design axioms in play** (consistent with the rest of the architecture):

- *Intelligence lives at the loop's exit; the deterministic spine is engine
  state read/written through tools.* Hint Mode's budget and the mastery gate
  both embody this — the model teaches/questions, the engine decides
  advancement and answer-reveal.
- *Kid Mode changes the voice, never the bar.* A `PromptBlock` stacked above
  capability playbooks reshapes tone; it cannot override safety, tool
  truthfulness, or the mastery gate.
- *Spelling/pronunciation ride on mastery_path, not a new capability.* They
  are question types on `MEMORY` knowledge points, reusing `PendingQuestion`,
  `grade_and_record`, and the `SpacedRepetitionScheduler`
  (`[0,1,3,7,14,30,60]` day ladder for `MEMORY`).
- *Curricula remove the model from authoring the scope-and-sequence.* The
  pre-seed runs deterministically in `capability.run()`; the model teaches in
  order, the engine drives progression.

