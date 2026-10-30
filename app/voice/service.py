"""Recognition service: shrink the output space instead of enlarging
the model.

Flow (all selection in deterministic code; the gateway's chat endpoint
is used only for a full-tier repair NOTE, never to pick a phrase):

1. Transcribe via the gateway (v0.1.0: stub simulator n-best from text).
2. Rerank every lexicon phrase against the whole n-best list:
   score = ASR-weighted mean of cosine(phrase, candidate), normalized
   by the total ASR weight so scores sit on a cosine-like scale, plus
   a small boost for phrases sharing words with recent selections.
   Lexicon embeddings are cached; candidates are embedded per call.
3. If the best phrase clears MATCH_THRESHOLD, select it (source
   "lexicon"). On the full tier, a low best score triggers a repair
   pass: re-score with the FULL conversation history and doubled
   context boost against REPAIR_THRESHOLD (source "repair").
4. Otherwise fall back to the recognizer's top candidate, flagged
   in_lexicon=false (source "raw_fallback"). The app never forces an
   utterance into the lexicon: a forced wrong match is worse than an
   honest miss, because someone may act on the phrase.

All thresholds are APP_DEFINED_UNVALIDATED simulator-era settings.
They have never been tuned on real speakers.
"""
from __future__ import annotations

from app import gateway
from app.voice.lexicon import Lexicon

MATCH_THRESHOLD = 0.50   # APP_DEFINED_UNVALIDATED. Set on the shipped
# synthetic fixtures (tests/) so that no out-of-lexicon fixture is
# force-matched into the lexicon; one severe in-lexicon fixture falls
# back instead. It must be re-derived on real speakers (roadmap #4).
REPAIR_THRESHOLD = 0.42  # APP_DEFINED_UNVALIDATED
CONTEXT_BOOST = 0.05     # per shared word with recent selections, capped
CONTEXT_CAP = 0.10


def _context_words(history: list[str], window: int) -> set[str]:
    items = history if window == 0 else history[-window:]
    words: set[str] = set()
    for h in items:
        words.update(h.lower().split())
    return words


def rank_phrases(lex: Lexicon, nbest: list[dict], history: list[str],
                 window: int, boost_scale: float = 1.0) -> list[dict]:
    if not nbest or len(lex) == 0:
        return []
    cand_vecs = [gateway.embed_text(c["text"]) for c in nbest]
    total_weight = sum(c["score"] for c in nbest) or 1.0
    ctx = _context_words(history, window)
    ranked: list[dict] = []
    for entry in lex.entries.values():
        sim = sum(c["score"] * gateway.cosine(entry["embedding"], cv)
                  for c, cv in zip(nbest, cand_vecs)) / total_weight
        shared = len(set(entry["phrase"].split()) & ctx)
        boost = min(CONTEXT_CAP, CONTEXT_BOOST * shared) * boost_scale
        ranked.append({"phrase": entry["phrase"],
                       "category": entry["category"],
                       "score": round(sim + boost, 4),
                       "similarity": round(sim, 4),
                       "context_boost": round(boost, 4)})
    ranked.sort(key=lambda r: -r["score"])
    return ranked


def recognize(lex: Lexicon, history: list[str], utterance_text: str,
              severity: str = "moderate", tier: str = "frugal") -> dict:
    profile = gateway.tier_profile(tier)
    tr = gateway.dispatch_transcription(utterance_text, severity,
                                        tier=tier)
    nbest = tr["nbest"]
    ranked = rank_phrases(lex, nbest, history, profile["context_window"])
    top = ranked[0] if ranked else None

    selected: str | None = None
    source = "raw_fallback"
    selected_score: float | None = None
    repair_note: str | None = None
    if top and top["score"] >= MATCH_THRESHOLD:
        selected, source = top["phrase"], "lexicon"
        selected_score = top["score"]
    elif top and profile["repair"]:
        repair_ranked = rank_phrases(lex, nbest, history, 0,
                                     boost_scale=2.0)
        rtop = repair_ranked[0] if repair_ranked else None
        chat = gateway.dispatch_chat(
            [{"role": "user", "content": (
                "Low-confidence utterance. n-best: "
                + "; ".join(f"{c['text']} ({c['score']})" for c in nbest)
                + f". Best lexicon candidate: "
                  f"{rtop['phrase'] if rtop else 'none'} "
                  f"score {rtop['score'] if rtop else 0}.")}], tier=tier)
        repair_note = chat["choices"][0]["message"]["content"]
        # The lower repair threshold may only be cleared by the repair
        # pass's extra evidence (context boost). A bare re-score with
        # no context adds no evidence and must not lower the bar: that
        # is how out-of-lexicon utterances get force-matched.
        if (rtop and rtop["score"] >= REPAIR_THRESHOLD
                and rtop["context_boost"] > 0):
            selected, source, ranked = rtop["phrase"], "repair", repair_ranked
            selected_score = rtop["score"]

    if selected is None:
        selected = nbest[0]["text"] if nbest else ""

    in_lexicon = lex.get(selected) is not None and source != "raw_fallback"
    confidence = selected_score if selected_score is not None else (
        nbest[0]["score"] if nbest else 0.0)
    return {
        "selected_phrase": selected,
        "source": source,  # lexicon | repair | raw_fallback
        "in_lexicon": in_lexicon,
        "confidence": confidence,
        "nbest": nbest,
        "ranked": ranked[:5],
        "tier": tier,
        "simulated": True,
        "repair_note": repair_note,
    }
