"""MyVoice Lexicon — FastAPI application.

Routes:
  /v1/*    Embedded OpenAI-compatible gateway: chat completions (repair
           notes only), embeddings, audio transcriptions (TEXT SIMULATOR
           in v0.1.0, no audio is recognized), audio speech (stub tone).
  /api/*   Product API: one speaker profile, lexicon builder, recognize,
           one-tap correction, phrase board, speech playback, demos.
  /        Static single-page demo UI.
  /healthz Health check.

Storage is in-memory in v0.1.0. There is no audio input type and no
stored recording anywhere in this version.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app import gateway, safety
from app.voice import models, service, synth
from app.voice.lexicon import Lexicon

logger = logging.getLogger("myvoice")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(
    title="MyVoice Lexicon",
    description="Communication aid for hard-to-recognize speech: a "
                "personal phrase lexicon reranks recognizer n-best lists. "
                "Proof of concept. Not a medical device. v0.1.0 "
                "recognizes no audio: the recognizer is a text simulator.",
    version="0.1.0",
)

LEXICON = Lexicon()
HISTORY: list[str] = []
RESULTS: list[dict] = []


def seed_lexicon() -> None:
    if len(LEXICON) == 0:
        for phrase, category in synth.STARTER_LEXICON:
            LEXICON.add(phrase, category)


seed_lexicon()


def _recognize(utterance_text: str, severity: str, tier: str,
               speaker_id: str = "anonymous") -> dict:
    speaker_id, _ = safety.redact_phi(speaker_id)
    result = service.recognize(LEXICON, HISTORY, utterance_text,
                               severity, tier)
    result["speaker_id"] = speaker_id
    result["summary"] = safety.render_result(result)
    # Full-tier verifier: the rendered summary must carry the selected
    # phrase verbatim, and the safety scan must be clean. It adds no new
    # recognition; it checks the phrasing against the selection.
    result["verifier_ok"] = (
        result["selected_phrase"] in result["summary"]
        and not safety.check_language(result["summary"]))
    HISTORY.append(result["selected_phrase"])
    RESULTS.append(result)
    return result


# ---------------------------------------------------------------- gateway

@app.get("/v1/models")
def v1_models():
    return gateway.list_models()


@app.post("/v1/chat/completions")
def v1_chat_completions(req: models.ChatRequest,
                        x_tier: str | None = Header(default=None)):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    tier = gateway.resolve_tier(req.model, x_tier)
    return gateway.dispatch_chat(req.messages, model=req.model,
                                 temperature=req.temperature,
                                 max_tokens=req.max_tokens,
                                 response_format=req.response_format,
                                 tier=tier)


@app.post("/v1/embeddings")
def v1_embeddings(req: models.EmbeddingsRequest):
    return gateway.dispatch_embeddings(req.input, model=req.model)


@app.post("/v1/audio/transcriptions")
def v1_transcriptions(req: models.TranscriptionRequest,
                      x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(req.model, x_tier)
    return gateway.dispatch_transcription(req.simulate_text, req.severity,
                                          model=req.model, tier=tier)


@app.post("/v1/audio/speech")
def v1_speech(req: models.SpeechRequest,
              x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(req.model, x_tier)
    wav, meta = gateway.dispatch_speech(req.input, model=req.model, tier=tier)
    return Response(content=wav, media_type="audio/wav",
                    headers={"X-MyVoice-Stub-Tone": "true",
                             "X-MyVoice-Model": meta["model"]})


# ---------------------------------------------------------------- product API

@app.get("/healthz")
def healthz():
    return {"status": "ok", "backend": gateway.get_backend(),
            "tier_default": gateway.resolve_tier(),
            "lexicon_size": len(LEXICON), "recognitions": len(RESULTS)}


@app.get("/api/lexicon")
def api_lexicon():
    return {"phrases": LEXICON.public(), "size": len(LEXICON)}


@app.post("/api/lexicon")
def api_lexicon_add(req: models.LexiconAddRequest):
    try:
        entry = LEXICON.add(req.phrase, req.category)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"phrase": entry["phrase"], "category": entry["category"],
            "uses": entry["uses"], "size": len(LEXICON)}


@app.post("/api/lexicon/correct")
def api_lexicon_correct(req: models.CorrectRequest):
    """One-tap correction: record the phrase the speaker actually meant.
    Grows the lexicon when the phrase is new."""
    entry = LEXICON.correct(req.phrase, req.category)
    if HISTORY:
        HISTORY[-1] = entry["phrase"]
    return {"phrase": entry["phrase"], "category": entry["category"],
            "uses": entry["uses"], "size": len(LEXICON)}


@app.get("/api/board")
def api_board():
    return {"board": LEXICON.board()}


@app.post("/api/recognize")
def api_recognize(req: models.RecognizeRequest,
                  x_tier: str | None = Header(default=None)):
    if req.severity not in models.SEVERITIES:
        raise HTTPException(status_code=400,
                            detail=f"unknown severity: {req.severity}")
    tier = gateway.resolve_tier(None, x_tier)
    return _recognize(req.utterance_text, req.severity, tier,
                      req.speaker_id)


@app.post("/api/demo/recognize")
def api_demo_recognize(case: str = "needs_water_severe",
                       x_tier: str | None = Header(default=None)):
    cases = synth.DEMO_CASES
    if case not in cases:
        raise HTTPException(status_code=400, detail=f"unknown demo case: {case}")
    tier = gateway.resolve_tier(None, x_tier)
    c = cases[case]
    return _recognize(c["utterance_text"], c["severity"], tier, "demo")


@app.post("/api/speak")
def api_speak(req: models.SpeakRequest,
              x_tier: str | None = Header(default=None)):
    tier = gateway.resolve_tier(None, x_tier)
    wav, meta = gateway.dispatch_speech(req.text, tier=tier)
    return Response(content=wav, media_type="audio/wav",
                    headers={"X-MyVoice-Stub-Tone": "true",
                             "X-MyVoice-Model": meta["model"]})


@app.get("/api/history")
def api_history():
    return {"history": HISTORY,
            "results": [{"selected_phrase": r["selected_phrase"],
                         "source": r["source"],
                         "in_lexicon": r["in_lexicon"],
                         "tier": r["tier"]} for r in RESULTS]}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
