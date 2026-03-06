from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
_TIMESTAMP_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_NUMBER_RE = re.compile(r"\b\d+\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PATH_RE = re.compile(r"(/[^\s]+)+")


@dataclass(slots=True)
class NormalizedLog:
    """Result of log normalization and fingerprinting."""

    normalized_message: str
    fingerprint: str


def normalize_message(message: str) -> str:
    """Normalize a log message by replacing volatile values with placeholders."""

    text = _UUID_RE.sub("<UUID>", message)
    text = _TIMESTAMP_RE.sub("<TIMESTAMP>", text)
    text = _EMAIL_RE.sub("<EMAIL>", text)
    text = _NUMBER_RE.sub("<NUMBER>", text)
    text = _PATH_RE.sub("<PATH>", text)
    return text


def compute_fingerprint(
    normalized_message: str,
    exception_type: str | None,
    stack_frames: Sequence[str] | None,
) -> str:
    """Compute a stable fingerprint from normalized message and stack information."""

    hasher = sha256()
    hasher.update(normalized_message.encode("utf-8"))
    if exception_type:
        hasher.update(b"|exc:")
        hasher.update(exception_type.encode("utf-8"))
    if stack_frames:
        top = "|".join(stack_frames[:5])
        hasher.update(b"|stack:")
        hasher.update(top.encode("utf-8"))
    return hasher.hexdigest()
