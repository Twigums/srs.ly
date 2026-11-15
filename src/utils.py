import re

from pyokaka import okaka
from rapidfuzz import fuzz

# meanings this short must be typed exactly: one typo in a short word often spells
# a different word that still scores high on fuzzy matching (e.g. "son" for "soon")
STRICT_MATCH_MAX_LENGTH = 5


def romaji_to_kana(string: str) -> str:
    """Convert romaji to kana, handling double-n as ん."""
    processed = ""
    prev = ""
    for char in string.lower():
        if char + prev == "nn":
            prev = ""
            processed += "n'"
        else:
            prev = char
            processed += char
    return okaka.convert(processed)


def _split_top_level(s: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def _expand_segment(segment: str) -> list[str]:
    segment = segment.strip()
    trailing = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", segment)
    if trailing:
        base = trailing.group(1).strip()
        options = [opt.strip() for opt in trailing.group(2).split(",")]
        results: list[str] = []
        if base:
            results.append(base)
        for opt in options:
            results.append(f"{base} {opt}".strip() if base else opt)
        return results

    leading = re.match(r"^\(([^)]+)\)\s+(.+)$", segment)
    if leading:
        options = [opt.strip() for opt in leading.group(1).split(",")]
        suffix = leading.group(2).strip()
        results = [f"{opt} {suffix}" for opt in options]
        results.append(suffix)
        return results

    return [segment]


def expand_meanings(meanings_str: str) -> list[str]:
    """Expand a comma-separated meanings string, respecting parenthesised option groups.

    "riding (a car, a train)" -> ["riding", "riding a car", "riding a train"]
    "a (b, c), d"             -> ["a", "a b", "a c", "d"]
    """
    if not meanings_str.strip():
        return []
    result: list[str] = []
    for segment in _split_top_level(meanings_str):
        result.extend(_expand_segment(segment))
    return result


def meaning_match_score(answer: str, meanings: list[str]) -> float:
    """Score an answer against its closest valid meaning, from 0 to 100.

    Case and surrounding whitespace are ignored. Meanings of up to
    STRICT_MATCH_MAX_LENGTH characters score 100 on an exact match and 0
    otherwise; longer meanings are fuzzy matched so small typos still pass.
    """
    answer = answer.strip().lower()

    # a blank answer never matches, same as fuzz.QRatio
    if not answer:
        return 0.0

    best_score = 0.0
    for meaning in meanings:
        meaning = meaning.strip().lower()
        if len(meaning) <= STRICT_MATCH_MAX_LENGTH:
            score = 100.0 if answer == meaning else 0.0
        else:
            score = fuzz.QRatio(answer, meaning)
        best_score = max(best_score, score)
    return best_score
