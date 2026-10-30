"""Safety language for MyVoice Lexicon: PHI redaction, banned-language
lint, and the required-language fragments every recognition result must
carry.

Banned phrases are claim strings: anything that would turn a
communication aid into a medical claim, or a synthetic-fixture number
into a real-world accuracy claim. Tests scan every generated result
text against this list. Note what is deliberately NOT banned: "not a
medical device" and "can be wrong" are required honest language.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("myvoice.safety")

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\d)(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}(?!\d)")),
    ("NAME", re.compile(r"\b(?:Patient(?: Name)?|Pt\.?|Name)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})")),
]

BANNED_PHRASES = [
    "clinically proven",
    "clinically validated",
    "clinically tested",
    "diagnoses",
    "diagnosed with",
    "medical device that",
    "fda approved",
    "fda cleared",
    "guaranteed accurate",
    "80% accurate",
    " HIPAA compliant",
    "hipaa certified",
]

REQUIRED_FRAGMENTS = [
    "communication aid only",
    "not a medical device",
    "can be wrong",
    "confirm",
]


def redact_phi(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    out = text or ""
    for kind, pat in _PATTERNS:
        def _sub(m: re.Match, kind: str = kind) -> str:
            found.append(kind)
            return f"[REDACTED-{kind}]"
        out = pat.sub(_sub, out)
    return out, found


def check_language(text: str) -> list[str]:
    low = (text or "").lower()
    return [p for p in BANNED_PHRASES if p.strip().lower() in low]


def render_result(result: dict) -> str:
    """The text shown with every recognition result. Asserts the banned
    scan is clean and the required fragments are present."""
    sel = result["selected_phrase"]
    src = {"lexicon": "matched your personal lexicon",
           "repair": "matched your personal lexicon after a repair pass",
           "raw_fallback": "no lexicon match cleared the threshold, so the "
                           "recognizer's top guess is shown unedited"}[result["source"]]
    text = (
        f"Selected phrase: \"{sel}\" ({src}).\n"
        "MyVoice Lexicon is a communication aid only. It is not a medical "
        "device, and a selected phrase can be wrong: confirm the phrase "
        "with the speaker before acting on it. In v0.1.0 the recognizer "
        "is a text simulator, so this result came from typed text, not "
        "from recorded speech."
    )
    banned = check_language(text)
    assert not banned, f"banned language in result: {banned}"
    for frag in REQUIRED_FRAGMENTS:
        assert frag in text.lower(), f"required fragment missing: {frag}"
    return text
