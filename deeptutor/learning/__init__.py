"""Mastery Path — structured mastery-based learning engine.

Modules:
    models          — Pydantic data models
    storage         — JSON persistence
    wordlist_store  — JSON persistence for spelling/vocabulary word lists
    scheduler       — Spaced repetition
    mastery         — Mastery scoring policy (swappable)
    grading         — Deterministic answer grading
    service         — Business logic
    prompts         — LLM prompt templates
"""

from deeptutor.learning.models import (
    DiagnosticResult,
    ErrorRecord,
    ErrorType,
    KnowledgePoint,
    KnowledgeType,
    LearningModule,
    LearningProgress,
    LearningStage,
    QuizAttempt,
    RepetitionState,
    RetryAttempt,
    ReviewTask,
)

# NOTE: WordListStore / WordList / WordEntry are intentionally NOT re-exported
# from this package __init__. Importing wordlist_store eagerly here pulls in
# path_service at package-load time, which creates a circular import when
# mastery.tools (imported early during registry bootstrap) touches this
# package. Import them directly:
#   from deeptutor.learning.wordlist_store import WordList, WordListStore

__all__ = [
    "DiagnosticResult",
    "ErrorRecord",
    "ErrorType",
    "KnowledgePoint",
    "KnowledgeType",
    "LearningModule",
    "LearningProgress",
    "LearningStage",
    "QuizAttempt",
    "RepetitionState",
    "RetryAttempt",
    "ReviewTask",
]
