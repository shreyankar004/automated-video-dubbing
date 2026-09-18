from __future__ import annotations

import re

_FILLER_PATTERNS = [
    re.compile(r"\b(um+|uh+|erm+|you know|like,)\b", re.IGNORECASE),
]
_MULTI_SPACE = re.compile(r"\s+")
_MULTI_PUNCT = re.compile(r"[!?.]{2,}")


def normalize_for_speech(text: str) -> str:
    if not text:
        return text
    cleaned = text.strip()
    for pattern in _FILLER_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = _MULTI_PUNCT.sub(lambda m: m.group()[0], cleaned)
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned
