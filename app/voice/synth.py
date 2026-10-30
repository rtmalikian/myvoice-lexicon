"""Synthetic fixtures for MyVoice Lexicon: starter lexicon, demo cases,
and the eval sets.

The eval sets are the honesty core of this repo. IN-LEXICON cases have
their intended phrase in the starter lexicon; OUT-OF-LEXICON cases do
not. The harness in tests/ reports the two accuracies SEPARATELY and
never blends them: a lexicon reranker is supposed to win on the first
set and behave honestly (fall back, do not force a match) on the
second. All fixtures are synthetic text. No audio, no real speakers.
"""
from __future__ import annotations

STARTER_LEXICON: list[tuple[str, str]] = [
    ("i need my suction", "needs"),
    ("i need water", "needs"),
    ("i am in pain", "needs"),
    ("i need the bathroom", "needs"),
    ("i need my medicine", "needs"),
    ("please call the nurse", "needs"),
    ("i am hungry", "needs"),
    ("i am thirsty", "needs"),
    ("i need my glasses", "needs"),
    ("i need to sit up", "needs"),
    ("i am cold", "comfort"),
    ("i am hot", "comfort"),
    ("i need a blanket", "comfort"),
    ("i need my pillow", "comfort"),
    ("the light is too bright", "comfort"),
    ("i am tired", "comfort"),
    ("my back hurts", "comfort"),
    ("my head hurts", "comfort"),
    ("please call my wife", "people"),
    ("please call my son", "people"),
    ("please call my daughter", "people"),
    ("i want to see the doctor", "people"),
    ("thank you", "social"),
    ("i am scared", "social"),
    ("i am comfortable", "social"),
    ("i love you", "social"),
    ("yes please", "social"),
    ("no thank you", "social"),
]

# (intended phrase, severity) — intended IS in the starter lexicon.
IN_LEXICON_CASES: list[tuple[str, str]] = [
    ("i need water", "mild"),
    ("i need water", "severe"),
    ("i am in pain", "moderate"),
    ("i need the bathroom", "moderate"),
    ("i need my medicine", "severe"),
    ("please call the nurse", "moderate"),
    ("i am hungry", "mild"),
    ("i am thirsty", "moderate"),
    ("i need my suction", "severe"),
    ("i am cold", "mild"),
    ("i need a blanket", "moderate"),
    ("my back hurts", "moderate"),
    ("my head hurts", "severe"),
    ("please call my wife", "moderate"),
    ("please call my son", "mild"),
    ("i want to see the doctor", "moderate"),
    ("i am scared", "moderate"),
    ("i need my pillow", "severe"),
    ("i need to sit up", "moderate"),
    ("the light is too bright", "mild"),
]

# (intended phrase, severity) — intended is NOT in the starter lexicon.
# Correct behaviour: recover the words if the simulated n-best allows,
# or fall back honestly. Never force a lexicon phrase the speaker did
# not say.
OUT_LEXICON_CASES: list[tuple[str, str]] = [
    ("i want to watch television", "moderate"),
    ("please open the window", "mild"),
    ("i need my phone charger", "moderate"),
    ("the soup is too salty", "mild"),
    ("i want to go outside", "moderate"),
    ("please read me the news", "moderate"),
    ("my leg is asleep", "mild"),
    ("i need a pen and paper", "moderate"),
    ("what time is lunch", "mild"),
    ("i miss my dog", "moderate"),
]

DEMO_CASES: dict[str, dict] = {
    "needs_water_severe": {
        "label": "Severe garbling, phrase in lexicon",
        "utterance_text": "i need water", "severity": "severe"},
    "pain_moderate": {
        "label": "Moderate garbling, phrase in lexicon",
        "utterance_text": "i am in pain", "severity": "moderate"},
    "off_lexicon": {
        "label": "Phrase NOT in the lexicon (honest fallback)",
        "utterance_text": "i want to watch television",
        "severity": "moderate"},
    "call_wife": {
        "label": "Moderate garbling, person phrase",
        "utterance_text": "please call my wife", "severity": "moderate"},
}
