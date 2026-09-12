"""
security/sanitizer.py — Prompt injection detection and input sanitization.
"""

import re
from typing import Tuple
from security.exceptions import PromptInjectionError

# Known prompt injection signatures
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|commands|rules)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions|prompts)", re.I),
    re.compile(r"system\s+prompt\s*(override|leak|reveal|show)", re.I),
    re.compile(r"(you\s+are\s+now|act\s+as)\s+dan\b", re.I),
    re.compile(r"developer\s+mode\s+(enabled|activated|on)", re.I),
    re.compile(r"override\s+(system|safety|security)\s+protocols?", re.I),
    re.compile(r"bypass\s+(all\s+)?(guardrails|filters|rules)", re.I),
    re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]", re.I),
]

_MAX_PROMPT_LENGTH = 4000


def check_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    Scans a prompt for known injection patterns.
    Returns (is_injection, reason).
    """
    if not text:
        return False, ""

    if len(text) > _MAX_PROMPT_LENGTH:
        return True, f"Input exceeds maximum allowed length of {_MAX_PROMPT_LENGTH} characters"

    if "\x00" in text:
        return True, "Null byte detected in input"

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True, f"Pattern matched prompt injection rule: '{pattern.pattern}'"

    return False, ""


def sanitize_prompt(text: str) -> str:
    """
    Sanitizes user input prompt. Raises PromptInjectionError if an injection signature is detected.
    """
    if not text or not text.strip():
        raise ValueError("Prompt cannot be empty")

    is_inj, reason = check_prompt_injection(text)
    if is_inj:
        raise PromptInjectionError(f"Rejected untrusted prompt input: {reason}")

    # Strip control characters, keep standard printable and whitespace
    sanitized = "".join(ch for ch in text if ch.isprintable() or ch in "\n\r\t")
    # Normalize multiple consecutive spaces
    sanitized = re.sub(r"[ \t]+", " ", sanitized).strip()
    return sanitized
