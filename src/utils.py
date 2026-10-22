import re

import pykakasi
from pyokaka import okaka

# building the converter loads its dictionaries, so only do it once
_kakasi = pykakasi.kakasi()

# punctuation and spacing that speech-to-text adds around a spoken answer
_spoken_japanese_punctuation = re.compile(r"[\s、。，．,.!?！？「」『』・…]")
_spoken_english_punctuation = re.compile(r"[^a-z0-9 '-]")


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


def spoken_to_hiragana(text: str) -> str:
    """Convert a Japanese transcript to the hiragana that reading answers are checked against.

    "帰ります。" -> "かえります"
    "コーヒー"   -> "こーひー"
    """
    hiragana = "".join(item["hira"] for item in _kakasi.convert(text))
    return _spoken_japanese_punctuation.sub("", hiragana)


def spoken_to_meaning(text: str) -> str:
    """Lowercase an English transcript and drop the punctuation speech-to-text adds.

    "To compare." -> "to compare"
    "Isn’t it?"   -> "isn't it"
    """
    cleaned = _spoken_english_punctuation.sub("", text.lower().replace("’", "'"))
    return " ".join(cleaned.split())
