# ARCHITECTURE.md — MyVoice Lexicon

## Layers

- `app/main.py` — FastAPI routes. Product API (`/api/*`) and the embedded
  gateway (`/v1/*`) share one process. Storage is in-memory in v0.1.0:
  one speaker profile, one lexicon, one session history.
- `app/voice/asr_sim.py` — the stub recognizer. Takes intended text and
  produces a simulated n-best list with a fixed word-confusability table
  and per-severity substitution/deletion rates. Deterministic per
  (text, severity). There is no audio path in v0.1.0.
- `app/voice/lexicon.py` — the personal lexicon. Phrases are embedded
  once, through the gateway's embeddings dispatch, and cached on the
  entry. One-tap corrections add or count phrases.
- `app/voice/service.py` — the reranker and selection logic: ASR-weighted
  embedding similarity against the whole n-best list, context boost,
  match threshold, full-tier repair pass (lower bar only on context
  evidence), honest fallback. All thresholds APP_DEFINED_UNVALIDATED.
- `app/voice/synth.py` — starter lexicon (28 phrases), demo cases, and
  the eval fixture sets (20 in-lexicon, 10 out-of-lexicon).
- `app/voice/models.py` — Pydantic models. Extra fields are forbidden,
  so an audio-shaped payload is rejected (422) before processing.
- `app/gateway.py` — embedded OpenAI-compatible gateway: chat
  (repair notes only), embeddings (hashed bag-of-words stub embedder,
  function words down-weighted), audio transcriptions (simulator),
  audio speech (placeholder tone WAV). Ledger records kinds, tiers,
  backends and counts only.
- `app/safety.py` — PHI redaction, banned-language list, required-language
  list, and the result renderer. Rendering asserts both scans pass.

## What v0.1.0 does NOT ship

Real audio ASR. The transcription endpoint accepts a text simulation
request and answers with a labelled simulated n-best list
(`simulated: true`). A real deployment wires a real recognizer (local
small Whisper-class model on the frugal tier, a larger model on full)
behind the same endpoint and request/response schema; the reranker,
lexicon, fallback, and eval design do not change. Until that integration
lands, do not describe MyVoice Lexicon as a speech-recognition app: it
is a lexicon-reranking engine with a documented audio path. The same
applies to speech: playback is a stub tone WAV behind the speech
endpoint, with real TTS (and, later, consented banked voices) as the
integration path.

## Tier design

Frugal and full share the lexicon, the embeddings, and the rerank math.
Full widens the context window from the last 3 selections to the full
history, enables the repair pass (which may clear a lower threshold
only when the context boost is what clears it), uses the
higher-sample-rate TTS alias, and runs the verifier that checks the
rendered summary carries the selected phrase verbatim. Neither tier
changes an embedding or a similarity score.
