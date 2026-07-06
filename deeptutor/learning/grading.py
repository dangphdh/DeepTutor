"""Deterministic answer grading + coarse error classification for Mastery Path."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deeptutor.learning.models import ErrorType


def grade_answer(user_answer: str, expected_answer: str, question_type: str = "short") -> bool:
    """Grade user answer against expected answer.

    Args:
        user_answer: The user's submitted answer.
        expected_answer: The stored expected answer.
        question_type: One of "choice", "short", "open", "spelling".

    Returns:
        True if answer is correct.
    """
    user = user_answer.strip().lower()
    expected = expected_answer.strip().lower()

    if not expected:
        return False

    if question_type == "choice":
        user_norm = user.replace(" ", "")
        expected_norm = expected.replace(" ", "")
        return user_norm == expected_norm

    if question_type == "spelling":
        # Spelling is exact-match only (case-insensitive, whitespace-stripped).
        # A 1-char-off spelling is WRONG — unlike "short", which fuzzily accepts
        # 85%-similar answers (e.g. "schoo" vs "school" would wrongly pass).
        # Spelling demands precision: every letter must be right.
        return user == expected

    if question_type == "short":
        if user == expected:
            return True
        if len(expected) <= 30:
            return SequenceMatcher(None, user, expected).ratio() >= 0.85
        return False

    if question_type == "open":
        keywords = [k.strip() for k in re.split(r"[,;，；。\n]+", expected) if k.strip()]
        if not keywords:
            return False
        matched = sum(1 for kw in keywords if kw in user)
        return matched / len(keywords) >= 0.6

    return False


def spelling_diff(user_answer: str, expected_answer: str) -> dict:
    """Produce a character-level diff hint for a misspelled answer.

    Used by the spelling trainer to give a targeted, encouraging hint instead
    of just "wrong". Returns a dict describing the first substantive edit:
      {"status": "missing"|"extra"|"wrong"|"swapped", "detail": str, "hint": str}

    The ``hint`` field is a ready-to-show sentence (English; the model adapts
    it to the active language in feedback). Returns ``{"status": "correct"}``
    when the inputs already match (caller should check grade_answer first).
    """
    user = user_answer.strip().lower()
    expected = expected_answer.strip().lower()
    if user == expected:
        return {"status": "correct", "detail": "", "hint": ""}

    # Empty answer — metacognitive miss, no char-level hint meaningful.
    if not user:
        return {
            "status": "missing",
            "detail": "blank answer",
            "hint": "Listen to the word again and try to spell it.",
        }

    matcher = SequenceMatcher(None, user, expected)
    opcodes = matcher.get_opcodes()

    # Walk the opcodes for the first non-"equal" edit and classify it. We don't
    # try to detect transpositions specially: SequenceMatcher has no "swap"
    # opcode and the insert/delete pairs it emits for swaps are interleaved with
    # "equal" runs in a way that makes reliable detection fiddly. Reporting the
    # first concrete difference (a missing/extra/wrong letter) is still a useful,
    # pointing hint for a young learner — it directs their attention to the area.
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        if tag == "delete":
            # Letters in `user` not in `expected` → extra letters typed.
            extra = user[i1:i2]
            return {
                "status": "extra",
                "detail": f"extra letter(s) '{extra}' at position {i1 + 1}",
                "hint": f"You typed an extra letter '{extra}'. Try removing it.",
            }
        if tag == "insert":
            # Letters in `expected` not in `user` → missing letters.
            missing = expected[j1:j2]
            return {
                "status": "missing",
                "detail": f"missing letter(s) '{missing}' at position {j1 + 1}",
                "hint": f"You're missing the letter '{missing}'. Add it and try again.",
            }
        if tag == "replace":
            user_chars = user[i1:i2]
            expected_chars = expected[j1:j2]
            return {
                "status": "wrong",
                "detail": f"wrong letter(s): you wrote '{user_chars}', should be '{expected_chars}' at position {i1 + 1}",
                "hint": (
                    f"Look at letter {i1 + 1}: you wrote '{user_chars}', "
                    f"but it should be '{expected_chars}'."
                ),
            }

    # Should be unreachable if user != expected, but guard anyway.
    return {
        "status": "wrong",
        "detail": "small difference",
        "hint": "Almost! Check each letter carefully.",
    }


def classify_error(user_answer: str) -> ErrorType:
    """Coarse error classification for a wrong answer.

    A blank answer signals the student did not know (metacognitive); anything
    else is treated as a wrong application. The richer four-type taxonomy is
    assigned later by the LLM in the error-diagnosis stage.
    """
    from deeptutor.learning.models import ErrorType

    return ErrorType.METACOGNITIVE if not user_answer.strip() else ErrorType.APPLICATION_ERROR


__all__ = ["grade_answer", "classify_error", "spelling_diff"]
