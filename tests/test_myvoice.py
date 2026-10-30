"""MyVoice Lexicon test suite.

The eval harness is the honesty core: IN-LEXICON and OUT-OF-LEXICON
phrase accuracy are measured on SEPARATE synthetic fixture sets and
asserted separately. A lexicon reranker is supposed to win in-lexicon
and behave honestly out-of-lexicon (fall back, never force a match).
All fixtures are synthetic text produced by the stub simulator. No
audio, no real speakers: these numbers prove pipeline behaviour only.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app import gateway, safety
from app.main import app
from app.voice import asr_sim, service, synth
from app.voice.lexicon import Lexicon

ROOT = pathlib.Path(__file__).resolve().parent.parent
client = TestClient(app)


def fresh_lexicon() -> Lexicon:
    lex = Lexicon()
    for phrase, category in synth.STARTER_LEXICON:
        lex.add(phrase, category)
    return lex


# ---------------------------------------------------------------- simulator

def test_simulator_deterministic():
    a = asr_sim.simulate_nbest("i need my medicine", "severe")
    b = asr_sim.simulate_nbest("i need my medicine", "severe")
    assert a == b and len(a) >= 1


def test_simulator_scores_descend():
    nb = asr_sim.simulate_nbest("please call the nurse", "moderate")
    scores = [c["score"] for c in nb]
    assert scores == sorted(scores, reverse=True)


def test_simulator_severe_garbles_more_than_mild():
    def edits(sev: str) -> int:
        total = 0
        for intended, _ in synth.IN_LEXICON_CASES:
            top = asr_sim.simulate_nbest(intended, sev)[0]["text"]
            total += sum(1 for a, b in zip(intended.split(), top.split()) if a != b)
        return total
    assert edits("severe") > edits("mild")


def test_simulator_empty_text():
    assert asr_sim.simulate_nbest("", "mild") == []


# ---------------------------------------------------------------- gateway

def test_models_list_aliases():
    ids = {m["id"] for m in gateway.list_models()["data"]}
    assert {"myvoice-frugal", "myvoice-full", "myvoice-asr-small",
            "myvoice-asr-large", "myvoice-tts-local"} <= ids


def test_embeddings_deterministic_and_normalized():
    v1 = gateway.embed_text("i need water")
    v2 = gateway.embed_text("i need water")
    assert v1 == v2
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-6


def test_embeddings_function_words_downweighted():
    # The distinctive word should dominate: "water" vs "daughter" differ
    # more than two phrases sharing only glue words.
    near = gateway.cosine(gateway.embed_text("i need water"),
                          gateway.embed_text("i need the water"))
    far = gateway.cosine(gateway.embed_text("i need water"),
                         gateway.embed_text("i need daughter"))
    assert near > far


def test_transcription_is_labelled_simulated():
    r = client.post("/v1/audio/transcriptions",
                    json={"simulate_text": "i need water",
                          "severity": "severe"})
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True and body["nbest"]


def test_speech_returns_wav_stub_tone():
    r = client.post("/v1/audio/speech", json={"input": "i need water"})
    assert r.status_code == 200
    assert r.content[:4] == b"RIFF"
    assert r.headers.get("x-myvoice-stub-tone") == "true"


def test_chat_rejects_audio_parts():
    r = client.post("/v1/chat/completions", json={"messages": [
        {"role": "user", "content": [{"type": "input_audio",
                                      "input_audio": {"data": "x"}}]}]})
    assert r.status_code == 400


def test_chat_empty_messages_rejected():
    r = client.post("/v1/chat/completions", json={"messages": []})
    assert r.status_code == 400


# ---------------------------------------------------------------- lexicon

def test_lexicon_add_and_dedupe():
    lex = Lexicon()
    lex.add("i need water", "needs")
    entry = lex.add("I need   water", "needs")
    assert len(lex) == 1 and entry["uses"] == 0


def test_lexicon_correction_grows_lexicon():
    lex = fresh_lexicon()
    before = len(lex)
    entry = lex.correct("i need my phone charger")
    assert len(lex) == before + 1 and entry["uses"] == 1
    again = lex.correct("i need my phone charger")
    assert len(lex) == before + 1 and again["uses"] == 2


def test_lexicon_embeddings_cached():
    gateway.reset_ledger()
    lex = fresh_lexicon()
    assert gateway.CALL_LEDGER["embeddings"] == len(synth.STARTER_LEXICON)
    service.recognize(lex, [], "i need water", "mild", "frugal")
    # Recognition embeds candidates locally; the lexicon is NOT re-embedded.
    assert gateway.CALL_LEDGER["embeddings"] == len(synth.STARTER_LEXICON)


def test_board_grouped_by_category():
    board = fresh_lexicon().board()
    assert "i need water" in board["needs"]
    assert "thank you" in board["social"]


# ---------------------------------------------------------------- rerank / service

def test_recognize_in_lexicon_mild():
    r = service.recognize(fresh_lexicon(), [], "i need water", "mild", "frugal")
    assert r["selected_phrase"] == "i need water"
    assert r["source"] == "lexicon" and r["in_lexicon"] is True


def test_recognize_severe_medicine_falls_back_without_context():
    # The honest miss: every simulated candidate garbles "medicine"
    # beyond the threshold, so the app shows the raw guess, flagged.
    r = service.recognize(fresh_lexicon(), [], "i need my medicine",
                          "severe", "frugal")
    assert r["source"] == "raw_fallback" and r["in_lexicon"] is False


def test_full_tier_repair_uses_context_evidence():
    hist = ["i need water", "i need my pillow"]
    r = service.recognize(fresh_lexicon(), hist, "i need my medicine",
                          "severe", "full")
    assert r["selected_phrase"] == "i need my medicine"
    assert r["source"] == "repair" and r["repair_note"]


def test_repair_without_context_does_not_force_match():
    # Regression guard: an early build let the repair pass lower the
    # threshold with no new evidence and force-matched out-of-lexicon
    # utterances. The repair bar may only be cleared by context boost.
    r = service.recognize(fresh_lexicon(), [], "i want to go outside",
                          "moderate", "full")
    assert r["source"] == "raw_fallback"


def test_context_boost_changes_ranking():
    lex = fresh_lexicon()
    nb = asr_sim.simulate_nbest("i need my medicine", "severe")
    plain = service.rank_phrases(lex, nb, [], 3)
    boosted = service.rank_phrases(lex, nb, ["i need water"], 3)
    p = next(x for x in plain if x["phrase"] == "i need my medicine")
    b = next(x for x in boosted if x["phrase"] == "i need my medicine")
    assert b["score"] > p["score"] and b["context_boost"] > 0


# ---------------------------------------------------------------- eval harness

def _run_eval(cases, tier):
    lex = fresh_lexicon()
    exact = forced_wrong = fallback = 0
    for intended, severity in cases:
        r = service.recognize(lex, [], intended, severity, tier)
        if r["selected_phrase"] == intended:
            exact += 1
        elif r["source"] != "raw_fallback":
            forced_wrong += 1
        else:
            fallback += 1
    return exact, forced_wrong, fallback


@pytest.mark.parametrize("tier", ["frugal", "full"])
def test_eval_in_lexicon_accuracy(tier):
    exact, forced_wrong, fallback = _run_eval(synth.IN_LEXICON_CASES, tier)
    n = len(synth.IN_LEXICON_CASES)
    # Measured on the shipped fixtures: 19/20 (the severe "medicine"
    # case falls back honestly). Bar set below the measured value.
    assert exact / n >= 0.90, f"in-lexicon {exact}/{n}"
    assert forced_wrong == 0


@pytest.mark.parametrize("tier", ["frugal", "full"])
def test_eval_out_of_lexicon_no_forced_matches(tier):
    exact, forced_wrong, fallback = _run_eval(synth.OUT_LEXICON_CASES, tier)
    n = len(synth.OUT_LEXICON_CASES)
    # The out-of-lexicon contract: never force a lexicon phrase the
    # speaker did not say. Exact recovery comes only from the honest
    # fallback carrying the recognizer's top candidate.
    assert forced_wrong == 0, f"forced {forced_wrong}/{n}"
    assert exact / n >= 0.50, f"out-lexicon exact {exact}/{n}"


def test_eval_sets_are_disjoint():
    in_phrases = {p for p, _ in synth.IN_LEXICON_CASES}
    out_phrases = {p for p, _ in synth.OUT_LEXICON_CASES}
    lex_phrases = {p for p, _ in synth.STARTER_LEXICON}
    assert in_phrases <= lex_phrases
    assert not (out_phrases & lex_phrases)
    assert not (in_phrases & out_phrases)


# ---------------------------------------------------------------- product API

def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_api_recognize_end_to_end():
    r = client.post("/api/recognize", json={"utterance_text": "i am in pain",
                                            "severity": "moderate"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_phrase"] == "i am in pain"
    assert body["simulated"] is True
    for frag in safety.REQUIRED_FRAGMENTS:
        assert frag in body["summary"].lower()
    assert not safety.check_language(body["summary"])


def test_api_demo_cases():
    for case in synth.DEMO_CASES:
        r = client.post(f"/api/demo/recognize?case={case}")
        assert r.status_code == 200, case
        assert r.json()["selected_phrase"]


def test_api_speak_board_phrase():
    r = client.post("/api/speak", json={"text": "thank you"})
    assert r.status_code == 200 and r.content[:4] == b"RIFF"


def test_api_add_phrase_then_recognize_it():
    r = client.post("/api/lexicon", json={"phrase": "i need my phone charger",
                                          "category": "needs"})
    assert r.status_code == 200
    r2 = client.post("/api/recognize",
                     json={"utterance_text": "i need my phone charger",
                           "severity": "moderate"})
    assert r2.json()["selected_phrase"] == "i need my phone charger"


def test_api_rejects_audio_shaped_payload():
    r = client.post("/api/recognize", json={"utterance_text": "i need water",
                                            "severity": "mild",
                                            "audio": "base64data"})
    assert r.status_code == 422


def test_api_bad_severity_rejected():
    r = client.post("/api/recognize", json={"utterance_text": "i need water",
                                            "severity": "extreme"})
    assert r.status_code == 400


def test_full_tier_verifier_ok():
    r = client.post("/api/recognize", headers={"X-Tier": "full"},
                    json={"utterance_text": "i need water",
                          "severity": "mild"})
    assert r.json()["verifier_ok"] is True


def test_ui_served_with_disclaimer():
    r = client.get("/")
    assert r.status_code == 200
    assert "PROOF OF CONCEPT" in r.text
    assert "text simulator" in r.text


# ---------------------------------------------------------------- safety

def test_redact_phi():
    out, found = safety.redact_phi("reach me at sam@example.com or 555-123-4567")
    assert "sam@example.com" not in out and found


def test_render_result_language_all_sources():
    for source in ("lexicon", "repair", "raw_fallback"):
        text = safety.render_result({"selected_phrase": "i need water",
                                     "source": source})
        assert not safety.check_language(text)
        for frag in safety.REQUIRED_FRAGMENTS:
            assert frag in text.lower()


# ---------------------------------------------------------------- repo checks

def test_readme_disclaimer_first_verbatim():
    lines = (ROOT / "README.md").read_text().splitlines()
    assert lines[0].startswith("> ## ⚠️ PROOF OF CONCEPT")
    head = "\n".join(lines[:12])
    assert "not been tested clinically" in head
    assert "dial 911 immediately" in head


def test_no_unverified_sap_figure_anywhere():
    for name in ("README.md", "EVIDENCE.md", "SECURITY.md"):
        text = (ROOT / name).read_text()
        assert "1,500" not in text and "~999" not in text, name


def test_evidence_md_carries_the_honest_limits():
    text = (ROOT / "EVIDENCE.md").read_text()
    for needle in ("13%", "1,530", "51%", "415", "524",
                   "target to be demonstrated"):
        assert needle in text, needle
    assert "aphasia" in text.lower() and "dysarthria" in text.lower()


def test_thresholds_labelled_app_defined():
    src = (ROOT / "app" / "voice" / "service.py").read_text()
    assert "APP_DEFINED_UNVALIDATED" in src
