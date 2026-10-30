"""Embedded OpenAI-compatible gateway for MyVoice Lexicon.

Same skeleton as faceflag / pose-not-pixels / pill-tray / wound-delta.
The product's own features call these endpoints; nothing talks to a
vendor API directly. One environment variable picks the backend:

- stub (default): deterministic, no model, no keys. Transcription is a
  TEXT SIMULATOR (see app/voice/asr_sim.py): v0.1.0 recognizes no audio.
  Speech is a placeholder tone WAV, not synthesized speech. Chat returns
  a deterministic repair note. This is what CI and the demo run.
- local / upstream: an OpenAI-compatible server you run or choose. The
  dispatch functions keep the same schema; a real deployment wires real
  ASR/TTS/chat backends behind these endpoints (roadmap issue #1).

Embeddings are a deterministic hashed bag-of-words (token-hash, 256
dims, common function words down-weighted). They are a local stub
embedder: good enough to rank lexicon phrases by token overlap, not a
semantic model. The call ledger records
kinds, tiers, backends and counts only: never phrase text, never
utterances.
"""
from __future__ import annotations

import hashlib
import io
import math
import os
import struct
import wave

from fastapi import HTTPException

from app.voice import asr_sim

STUB_MODEL_ID = "myvoice-stub-1"
FRUGAL_MODEL_ID = "myvoice-frugal"
FULL_MODEL_ID = "myvoice-full"
EMBED_DIM = 256

# Grammatical glue words carry almost no phrase identity ("i need my
# ..." is half the lexicon), so the stub embedder down-weights them and
# lets the distinctive words dominate the similarity. APP_DEFINED.
FUNCTION_WORDS = {"i", "my", "the", "a", "an", "am", "is", "to",
                  "please", "me", "you", "it", "of", "and", "in"}
FUNCTION_WEIGHT = 0.3

TIERS: dict[str, dict] = {
    # context_window 0 = full history. APP_DEFINED routing profiles.
    "frugal": {"model_alias": FRUGAL_MODEL_ID, "asr_alias": "myvoice-asr-small",
               "tts_alias": "myvoice-tts-local", "context_window": 3,
               "repair": False, "tts_sample_rate": 8000},
    "full": {"model_alias": FULL_MODEL_ID, "asr_alias": "myvoice-asr-large",
             "tts_alias": "myvoice-tts-hq", "context_window": 0,
             "repair": True, "tts_sample_rate": 16000},
}

_FORBIDDEN_PART_TYPES = {"input_audio", "audio_url", "file"}
_FORBIDDEN_KEYS = {"audio", "audio_url", "file_id", "data"}

CALL_LEDGER: dict[str, int] = {"chat": 0, "embeddings": 0,
                               "transcriptions": 0, "speech": 0}
CALL_LOG: list[dict] = []


def reset_ledger() -> None:
    for k in CALL_LEDGER:
        CALL_LEDGER[k] = 0
    CALL_LOG.clear()


def get_backend() -> str:
    return (os.environ.get("AI_BACKEND", "stub") or "stub").strip().lower()


def resolve_tier(model: str | None = None, x_tier: str | None = None) -> str:
    if x_tier and x_tier.strip().lower() in TIERS:
        return x_tier.strip().lower()
    if model:
        m = model.strip().lower()
        if m.endswith("-full") or m == FULL_MODEL_ID:
            return "full"
        if m.endswith("-frugal") or m == FRUGAL_MODEL_ID:
            return "frugal"
    env = (os.environ.get("MYVOICE_TIER", "frugal") or "frugal").strip().lower()
    return env if env in TIERS else "frugal"


def tier_profile(tier: str) -> dict:
    return dict(TIERS[tier])


def estimate_text_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


# ---------------------------------------------------------------- embeddings

def embed_text(text: str) -> list[float]:
    """Deterministic hashed bag-of-words embedding (stub embedder).

    Each token votes for one dimension with a hashed sign, so cosine
    similarity tracks token overlap between short phrases. That is the
    property the lexicon reranker needs. It is not semantic similarity.
    """
    vec = [0.0] * EMBED_DIM
    for tok in (text or "").lower().split():
        digest = hashlib.sha256(tok.encode()).digest()
        idx = int.from_bytes(digest[:2], "big") % EMBED_DIM
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[idx] += sign * (FUNCTION_WEIGHT if tok in FUNCTION_WORDS else 1.0)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def dispatch_embeddings(text_input, model: str | None = None) -> dict:
    items = text_input if isinstance(text_input, list) else [text_input]
    CALL_LEDGER["embeddings"] += len(items)
    CALL_LOG.append({"kind": "embeddings", "backend": get_backend(),
                     "count": len(items)})
    data = [{"object": "embedding", "index": i, "embedding": embed_text(str(x))}
            for i, x in enumerate(items)]
    return {"object": "list", "data": data, "model": model or STUB_MODEL_ID,
            "usage": {"prompt_tokens": sum(estimate_text_tokens(str(x)) for x in items),
                      "total_tokens": sum(estimate_text_tokens(str(x)) for x in items)}}


# ---------------------------------------------------------------- transcription

def dispatch_transcription(simulate_text: str, severity: str = "moderate",
                           model: str | None = None, tier: str = "frugal") -> dict:
    """OpenAI-shaped transcription response from the stub simulator.

    v0.1.0 accepts TEXT ONLY. There is no audio input type yet: a real
    deployment posts audio to a real ASR backend behind this endpoint
    (roadmap issue #1). The response says `simulated: true` so no caller
    can mistake it for recognized audio.
    """
    nbest = asr_sim.simulate_nbest(simulate_text, severity)
    CALL_LEDGER["transcriptions"] += 1
    CALL_LOG.append({"kind": "transcriptions", "tier": tier,
                     "backend": get_backend(), "nbest": len(nbest)})
    return {
        "text": nbest[0]["text"] if nbest else "",
        "nbest": nbest,
        "model": model or TIERS[tier]["asr_alias"],
        "simulated": True,
        "note": "Stub simulator: n-best generated from text. No audio was recognized.",
    }


# ---------------------------------------------------------------- speech

def dispatch_speech(text: str, model: str | None = None,
                    tier: str = "frugal") -> tuple[bytes, dict]:
    """OpenAI-shaped speech response: WAV bytes plus metadata.

    The stub backend returns a placeholder TONE (a sine wave whose
    length scales with the phrase). It is not synthesized speech and is
    labelled as such in the metadata and the demo UI. A real deployment
    wires a real TTS voice behind this endpoint.
    """
    profile = TIERS[tier]
    rate = profile["tts_sample_rate"]
    words = max(1, len((text or "").split()))
    seconds = 0.4 + 0.14 * words
    frames = int(rate * seconds)
    freq = 440.0 if tier == "frugal" else 392.0
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        samples = b"".join(
            struct.pack("<h", int(9000 * math.sin(2 * math.pi * freq * i / rate)))
            for i in range(frames))
        wf.writeframes(samples)
    CALL_LEDGER["speech"] += 1
    CALL_LOG.append({"kind": "speech", "tier": tier, "backend": get_backend()})
    meta = {"model": model or profile["tts_alias"], "stub_tone": True,
            "sample_rate": rate,
            "note": "Stub placeholder tone, not synthesized speech."}
    return buf.getvalue(), meta


# ---------------------------------------------------------------- chat (repair only)

def assert_no_audio(messages: list[dict]) -> None:
    for m in messages or []:
        content = m.get("content", "")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in _FORBIDDEN_PART_TYPES:
                    raise HTTPException(status_code=400, detail="gateway chat takes text JSON only; audio parts rejected")
                if _FORBIDDEN_KEYS & set(part.keys()):
                    raise HTTPException(status_code=400, detail="gateway chat takes text JSON only; audio keys rejected")


def dispatch_chat(messages: list[dict], model: str | None = None,
                  temperature: float = 0.2, max_tokens: int = 2000,
                  response_format: dict | None = None, tier: str = "frugal") -> dict:
    """Chat endpoint. In this product it is used ONLY for low-confidence
    repair notes on the full tier. Selection itself stays in code
    (app/voice/service.py); the stub backend phrases a deterministic
    note and never picks the phrase."""
    assert_no_audio(messages)
    text = "\n".join(
        m.get("content", "") for m in messages or []
        if isinstance(m.get("content"), str))
    CALL_LEDGER["chat"] += 1
    CALL_LOG.append({"kind": "chat", "tier": tier, "backend": get_backend(),
                     "tokens_est": estimate_text_tokens(text)})
    note = ("MyVoice repair note (stub backend, deterministic): low-confidence "
            "utterance re-scored against the lexicon with full conversation "
            "history. Selection was made in code, not by a model.")
    return {
        "id": "chatcmpl-myvoice-stub",
        "object": "chat.completion",
        "model": model or TIERS[tier]["model_alias"],
        "choices": [{"index": 0, "message": {"role": "assistant", "content": note},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": estimate_text_tokens(text),
                  "completion_tokens": estimate_text_tokens(note),
                  "total_tokens": estimate_text_tokens(text) + estimate_text_tokens(note)},
    }


def list_models() -> dict:
    return {"object": "list", "data": [
        {"id": FRUGAL_MODEL_ID, "object": "model"},
        {"id": FULL_MODEL_ID, "object": "model"},
        {"id": STUB_MODEL_ID, "object": "model"},
        {"id": TIERS["frugal"]["asr_alias"], "object": "model"},
        {"id": TIERS["full"]["asr_alias"], "object": "model"},
        {"id": TIERS["frugal"]["tts_alias"], "object": "model"},
        {"id": TIERS["full"]["tts_alias"], "object": "model"},
    ]}
