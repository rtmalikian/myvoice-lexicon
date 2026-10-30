"""Stub ASR simulator for MyVoice Lexicon v0.1.0.

There is NO real audio recognition in v0.1.0. This module takes the text
a speaker intended to say and produces a simulated ASR n-best list: the
kind of garbled candidate list a small recognizer produces on dysarthric
speech, modelled with a fixed word-confusability table and per-severity
substitution / deletion rates. It exists so the lexicon reranker, the
fallback behaviour, and the eval harness can be built and measured
honestly. Real audio ASR is roadmap issue #1.

Everything is deterministic: the same (text, severity) always produces
the same n-best list, so CI numbers are reproducible.
"""
from __future__ import annotations

import hashlib
import random

# Words a small recognizer plausibly confuses on disordered speech.
# Deliberately NOT tuned per eval case: one fixed table for the product.
CONFUSABLES: dict[str, list[str]] = {
    "water": ["daughter", "order"],
    "pain": ["train", "pane"],
    "bathroom": ["bedroom"],
    "medicine": ["madison"],
    "nurse": ["purse", "worse"],
    "hungry": ["angry"],
    "thirsty": ["thursday"],
    "cold": ["called"],
    "hot": ["hat"],
    "blanket": ["banquet"],
    "pillow": ["hello"],
    "tired": ["wired"],
    "scared": ["stairs"],
    "wife": ["knife"],
    "son": ["sun"],
    "doctor": ["daughter"],
    "suction": ["section"],
    "glasses": ["classes"],
    "back": ["bag"],
    "head": ["bed"],
    "light": ["right"],
    "bright": ["bride"],
    "sit": ["set"],
    "up": ["cup"],
    "please": ["peas"],
    "thank": ["tank"],
    "love": ["glove"],
    "hurts": ["hearts"],
    "call": ["tall"],
    "see": ["sea"],
    "watch": ["wash"],
    "window": ["widow"],
    "phone": ["bone"],
    "soup": ["soap"],
    "outside": ["upside"],
    "read": ["red"],
    "news": ["nose"],
    "leg": ["egg"],
    "pen": ["ten"],
    "lunch": ["bunch"],
    "dog": ["log"],
    "open": ["oven"],
    "time": ["dime"],
    "what": ["wet"],
    "need": ["neat"],
}

SEVERITY_RATES: dict[str, dict[str, float]] = {
    # substitution probability per confusable word, deletion probability
    # per word. APP_DEFINED simulator settings, not measured error rates.
    "mild": {"sub": 0.18, "drop": 0.00},
    "moderate": {"sub": 0.38, "drop": 0.04},
    "severe": {"sub": 0.58, "drop": 0.10},
}

N_BEST = 4


def _seed(text: str, severity: str, k: int) -> int:
    digest = hashlib.sha256(f"{text}|{severity}|{k}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _garble(words: list[str], severity: str, k: int, rng: random.Random) -> list[str]:
    rates = SEVERITY_RATES[severity]
    # Later n-best candidates are garbled more than earlier ones, the
    # way a real recognizer's lower-ranked hypotheses drift further.
    sub_p = min(0.9, rates["sub"] * (0.6 + 0.35 * k))
    drop_p = rates["drop"] * (0.5 + 0.4 * k)
    out: list[str] = []
    for w in words:
        low = w.lower()
        if low in CONFUSABLES and rng.random() < sub_p:
            out.append(rng.choice(CONFUSABLES[low]))
        elif rng.random() < drop_p and len(words) > 2:
            continue
        else:
            out.append(w)
    return out or words[:1]


def simulate_nbest(intended_text: str, severity: str = "moderate") -> list[dict]:
    """Return a simulated ASR n-best list: [{text, score}, ...].

    Scores are simulated recognizer confidences, APP_DEFINED, decreasing
    with rank. They are not measured probabilities.
    """
    if severity not in SEVERITY_RATES:
        severity = "moderate"
    words = (intended_text or "").strip().split()
    if not words:
        return []
    seen: set[str] = set()
    nbest: list[dict] = []
    for k in range(N_BEST):
        rng = random.Random(_seed(intended_text, severity, k))
        cand_words = _garble(words, severity, k, rng)
        cand = " ".join(cand_words)
        if cand in seen:
            continue
        seen.add(cand)
        score = round(max(0.05, 0.88 - 0.13 * k - 0.05 * len(nbest)), 3)
        nbest.append({"text": cand, "score": score})
    return nbest
