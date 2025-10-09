"""
Input sanitization and prompt injection protection.

Detects and blocks common prompt injection patterns.
"""

import re
from typing import Tuple, Optional

# Suspicious patterns that might indicate injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now",
    r"new\s+instructions?:",
    r"system\s*:",
    r"assistant\s*:",
    r"<\|system\|>",
    r"<\|assistant\|>",
    r"<\|user\|>",
    r"forget\s+(the\s+)?context",
    r"disregard\s+(the\s+)?rules",
    r"bypass\s+security",
    r"override\s+instructions",
    r"reveal\s+your\s+prompt",
    r"show\s+me\s+your\s+system\s+prompt",
    r"what\s+(are|is)\s+your\s+instructions",
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection_attempt(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect potential prompt injection attempts.

    Args:
        text: User input to check

    Returns:
        (is_suspicious, reason) tuple
        - is_suspicious: True if pattern detected
        - reason: Description of what was detected (or None)
    """
    text_lower = text.lower()

    for i, pattern in enumerate(COMPILED_PATTERNS):
        if pattern.search(text_lower):
            return True, f"Suspicious pattern detected: {INJECTION_PATTERNS[i]}"

    return False, None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by removing potentially harmful content.

    - Removes control characters
    - Normalizes whitespace
    - Trims to reasonable length

    Args:
        text: Raw user input

    Returns:
        Sanitized text
    """
    # Remove control characters (except newlines and tabs)
    text = "".join(char for char in text if ord(char) >= 32 or char in '\n\t')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def validate_question(question: str, allow_suspicious: bool = False) -> str:
    """
    Validate and sanitize a question.

    Args:
        question: User's question
        allow_suspicious: If False, raise ValueError on suspicious input

    Returns:
        Sanitized question

    Raises:
        ValueError: If question contains suspicious patterns
    """
    # Sanitize first
    clean_question = sanitize_input(question)

    # Check for injection attempts
    if not allow_suspicious:
        is_suspicious, reason = detect_injection_attempt(clean_question)
        if is_suspicious:
            raise ValueError(f"Invalid question: {reason}")

    return clean_question


def validate_document_text(text: str) -> str:
    """
    Validate and sanitize document text for upserting.

    Args:
        text: Document content

    Returns:
        Sanitized text

    Raises:
        ValueError: If text contains suspicious patterns
    """
    # Sanitize
    clean_text = sanitize_input(text)

    # Check for injection attempts (less strict for documents)
    # Only check for obvious system prompt leakage
    dangerous_patterns = [
        r"<\|system\|>",
        r"<\|assistant\|>",
        r"SYSTEM:",
        r"ASSISTANT:",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, clean_text, re.IGNORECASE):
            raise ValueError(f"Document contains suspicious pattern: {pattern}")

    return clean_text
