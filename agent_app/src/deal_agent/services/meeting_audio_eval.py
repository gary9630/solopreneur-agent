from __future__ import annotations

from difflib import SequenceMatcher


def keyword_recall(transcript: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0

    normalized_transcript = transcript.casefold()
    matched = sum(1 for keyword in keywords if keyword.casefold() in normalized_transcript)
    return matched / len(keywords)


def normalized_error_rate(expected: str, actual: str) -> float:
    if not expected and not actual:
        return 0.0
    ratio = SequenceMatcher(None, expected, actual).ratio()
    return 1.0 - ratio
