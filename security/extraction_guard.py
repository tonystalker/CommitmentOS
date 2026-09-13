"""
CommitmentOS — Extraction guard (secondary belt-and-suspenders scanner).

PRIMARY defense is structural (fixed schema + untrusted-data framing in the prompt).
This scanner is a SECONDARY check that logs suspicious patterns.

It is NOT presented as the primary injection defense. A judge can always
craft a phrasing this scanner misses — the real defense is that even if they do,
there is no code path from message text to agent instruction.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Patterns that are suspicious in user-provided source text.
# These are not exhaustive — they are for logging/alerting only.
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?previous\s+instructions?", "classic ignore-previous-instructions pattern"),
    (r"you\s+are\s+now\s+(a\s+)?", "persona injection attempt"),
    (r"system\s*prompt", "system prompt reference in user content"),
    (r"disregard\s+(your\s+)?(previous\s+)?instructions?", "disregard instruction pattern"),
    (r"\bAI\b.*\bdo\s+not\b.*\bextract\b", "anti-extraction instruction"),
    (r"forget\s+(everything|all)\s+you", "memory wipe attempt"),
    (r"new\s+instruction[s:]?\s*:?\s*\n", "embedded instruction header"),
    (r"\[INST\]|\<\|im_start\|\>|\<s\>", "model-specific injection tokens"),
]

_COMPILED = [(re.compile(pat, re.IGNORECASE), desc) for pat, desc in _INJECTION_PATTERNS]


@dataclass
class GuardResult:
    flagged: bool
    reason: str = ""
    matched_patterns: list[str] = field(default_factory=list)


class ExtractionGuard:
    """
    Secondary belt-and-suspenders scanner for prompt injection patterns.

    IMPORTANT: This class logs and flags — it does NOT provide security.
    Security is provided by the structural defense in the extraction prompt:
      1. The LLM is explicitly told the source is untrusted data.
      2. Output is validated against a fixed typed schema.
      3. No path exists from source text to agent instruction.

    This guard is useful for:
      - Logging injection attempts for audit trail
      - Demo: showing "untrusted source content detected" in the trace viewer
    """

    def scan(self, text: str) -> GuardResult:
        if not text:
            return GuardResult(flagged=False)

        matched = []
        for pattern, description in _COMPILED:
            if pattern.search(text):
                matched.append(description)

        if matched:
            return GuardResult(
                flagged=True,
                reason=f"Secondary scanner detected {len(matched)} suspicious pattern(s): {'; '.join(matched)}",
                matched_patterns=matched,
            )

        return GuardResult(flagged=False)
