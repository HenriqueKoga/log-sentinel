from __future__ import annotations

import re
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


def normalize_message(message: str) -> str:
    """Normalize a log message replacing volatile parts with placeholders."""

    text = _UUID_RE.sub("<UUID>", message)
    text = _TIMESTAMP_RE.sub("<TIMESTAMP>", text)
    text = _EMAIL_RE.sub("<EMAIL>", text)
    text = _NUMBER_RE.sub("<NUMBER>", text)
    text = _PATH_RE.sub("<PATH>", text)
    return text


def normalize_stacktrace(stacktrace: str | None) -> str:
    """Normalize stacktrace keeping file/function and exception line, dropping line numbers."""
    if not stacktrace:
        return ""
    lines: list[str] = []
    for line in stacktrace.splitlines():
        line = re.sub(r":\d+", "", line)
        line = re.sub(r",\s*line\s+\d+\s*,", ",", line)
        lines.append(line.strip())
    return "\n".join(lines)


def compute_fingerprint(
    exception_type: str | None,
    stacktrace: str | None,
    message: str,
) -> str:
    """Compute deterministic fingerprint for an error cluster."""

    norm_msg = normalize_message(message)
    norm_stack = normalize_stacktrace(stacktrace)
    hasher = sha256()
    hasher.update((exception_type or "").encode("utf-8"))
    hasher.update(b"|")
    hasher.update(norm_stack.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(norm_msg.encode("utf-8"))
    return hasher.hexdigest()

