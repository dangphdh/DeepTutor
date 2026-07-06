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
        question_type: One of "choice", "short", "open", "spelling",
            "pronunciation".

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

    if question_type == "pronunciation":
        # Lenient phonetic match for spoken-word practice. STT transcripts are
        # approximations — "school" may come back as "skool" even when said
        # well. Correct if exact-equal OR a close char-level match (ratio
        # >= 0.8), after normalizing punctuation and common filler words.
        return _pronunciation_match(user, expected)

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


# Common English filler/determiner words STT often prepends/appends ("a cat",
# "the dog", "it is red"). Stripped before pronunciation comparison so they
# don't penalize a learner who said just the target word correctly.
_PRONUNCIATION_FILLERS = frozenset({"a", "an", "the", "it", "is", "was", "i"})
# A spoken attempt passes if its normalized edit distance from the target is
# at most this fraction of the target's length. E.g. threshold 0.34 on a
# 6-letter word ("school") allows up to 2 edits (insert/delete/substitute),
# so "skool" (1 edit: insert 'h') passes but "dog"→"cat" (3 edits) fails.
_PRONUNCIATION_MAX_EDIT_RATIO = 0.34


def _normalize_pronunciation(text: str) -> str:
    """Normalize a word/phrase for lenient pronunciation comparison.

    Lowercase, strip punctuation, drop common filler words, collapse spaces.
    """
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in cleaned.split() if w and w not in _PRONUNCIATION_FILLERS]
    return " ".join(words)


def _levenshtein(a: str, b: str) -> int:
    """Classic iterative Levenshtein edit distance (insert/delete/substitute)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(
                min(
                    prev[j] + 1,        # deletion
                    curr[j - 1] + 1,    # insertion
                    prev[j - 1] + (0 if ca == cb else 1),  # substitution/match
                )
            )
        prev = curr
    return prev[-1]


def _pronunciation_similarity(user: str, expected: str) -> float:
    """Return a 0..1 similarity score for two spoken-word strings.

    Based on normalized Levenshtein distance: 1.0 = identical, 0.0 = totally
    different. Handles insertions/deletions (which SequenceMatcher.ratio
    underweights for short words — "skool" vs "school" is one insertion).
    """
    if not expected:
        return 0.0
    if not user:
        return 0.0
    if user == expected:
        return 1.0
    dist = _levenshtein(user, expected)
    max_len = max(len(user), len(expected))
    return 1.0 - (dist / max_len)


def _pronunciation_match(user: str, expected: str) -> bool:
    """Lenient phonetic match for spoken-word practice.

    Passes if the normalized transcript equals the target OR the edit distance
    is small relative to the word length (so "skool"→"school" passes — one
    insertion — but "dog"→"cat" fails — three substitutions).
    """
    u = _normalize_pronunciation(user)
    e = _normalize_pronunciation(expected)
    if not e:
        return False
    if u == e:
        return True
    if not u:
        return False
    # Substring check: "school" in "i said school" (after filler strip) —
    # and the target itself may be the transcript minus a leading word.
    if e in u or u in e:
        return True
    dist = _levenshtein(u, e)
    allowed = max(1, int(len(e) * _PRONUNCIATION_MAX_EDIT_RATIO))
    return dist <= allowed


def pronunciation_diff(transcript: str, expected_answer: str) -> dict:
    """Produce a pronunciation feedback hint for a spoken-word attempt.

    Used by the pronunciation trainer to give encouraging, specific feedback
    instead of just "wrong". Returns::

        {"status": "correct"|"close"|"off",
         "transcript": <normalized heard text>,
         "expected": <normalized target word>,
         "similarity": <0..1 score>,
         "hint": <ready-to-show sentence>}

    The ``hint`` is a kind, actionable sentence (the model adapts it to the
    active language in feedback). ``status`` is "correct" on a passing match,
    "close" when the attempt was near but still wrong, and "off" when far.
    """
    u = _normalize_pronunciation(transcript)
    e = _normalize_pronunciation(expected_answer)
    sim = _pronunciation_similarity(u, e)
    if not e:
        return {"status": "off", "transcript": u, "expected": "", "similarity": sim, "hint": "Listen and try again."}
    if _pronunciation_match(transcript, expected_answer):
        return {
            "status": "correct",
            "transcript": u,
            "expected": e,
            "similarity": sim,
            "hint": "Perfect pronunciation!",
        }
    if not u:
        return {
            "status": "off",
            "transcript": "",
            "expected": e,
            "similarity": 0.0,
            "hint": f"I didn't hear you clearly. The word is '{e}'. Try saying it again.",
        }
    if sim >= 0.5:
        return {
            "status": "close",
            "transcript": u,
            "expected": e,
            "similarity": sim,
            "hint": (
                f"You said '{u}' — that's very close! The word is '{e}'. "
                f"Listen and try once more."
            ),
        }
    return {
        "status": "off",
        "transcript": u,
        "expected": e,
        "similarity": sim,
        "hint": (
            f"I heard '{u}', but the word is '{e}'. "
            f"Listen carefully and try again."
        ),
    }


def classify_error(user_answer: str) -> ErrorType:
    """Coarse error classification for a wrong answer.

    A blank answer signals the student did not know (metacognitive); anything
    else is treated as a wrong application. The richer four-type taxonomy is
    assigned later by the LLM in the error-diagnosis stage.
    """
    from deeptutor.learning.models import ErrorType

    return ErrorType.METACOGNITIVE if not user_answer.strip() else ErrorType.APPLICATION_ERROR


__all__ = [
    "classify_error",
    "grade_answer",
    "pronunciation_diff",
    "spelling_diff",
]
