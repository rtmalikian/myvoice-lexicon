> ## ⚠️ PROOF OF CONCEPT — NOT CLINICALLY TESTED
>
> **This tool has not been tested clinically and is a proof-of-concept for
> research and software demonstration only. It is not a medical device, it
> does not diagnose, treat, or rule out any condition, and its outputs may
> be wrong — including false positives and false negatives.**
>
> **Do not use it to make decisions about your health.**
> For any medical issue or concern, seek a licensed healthcare professional.
> **In an emergency, go to your nearest emergency room or dial 911 immediately.**

---

# MyVoice Lexicon

**Open-source communication aid for speech that recognizers get wrong.
Instead of a bigger model, it shrinks the output space: a personal lexicon
of the 50–300 phrases a speaker actually uses reranks the recognizer's
n-best list, one-tap corrections grow the lexicon, and anything outside
the lexicon falls back honestly instead of being forced into a match.**

Plain statement about v0.1.0: **the recognizer is a text simulator.** You
type the words the speaker tried to say; the simulator produces the kind
of garbled n-best list a small recognizer produces on dysarthric speech;
the lexicon reranker works on that list. No audio is recorded or
recognized in this version, and speech playback is a placeholder tone,
not a voice. Real audio ASR is roadmap issue #1. What ships here is the
lexicon, the reranking, the fallback behaviour, the phrase board, and
the eval harness, all measurable.

## The measurable failure, and what moves it

| Metric | Current workflow | With MyVoice Lexicon |
| --- | --- | --- |
| Generic ASR on severe dysarthric speech | Every commercial system tested in a 2025 zero-shot TORGO benchmark exceeded 51% word error rate on severe dysarthria (best 51.8%); the literature Green et al. cite puts commercial systems at 78–89% for severe speech | A personal phrase set turns open recognition into closed-set selection. Eval harness on synthetic text fixtures: **19 of 20 in-lexicon cases selected the intended phrase** |
| Saying something the person never said | An open recognizer's best guess is presented as the utterance, wrong words and all | Out-of-lexicon contract: **0 of 10 out-of-lexicon fixtures were forced into a lexicon phrase**. 8 of 10 were recovered exactly through the flagged fallback; the other 2 came back as the recognizer's garbled top guess, labelled not-in-lexicon |
| A communication aid that cannot learn | Fixed phrase boards say only what was printed on day one | One-tap correction adds the phrase the speaker actually meant; its embedding is cached once and it joins the rerank set immediately |

The target these numbers point at, stated as a target: **phrase accuracy
of 80% or better on in-lexicon phrases, demonstrated on real speakers.**
That has not been demonstrated. Not here, not anywhere for this design.
See EVIDENCE.md for what the published literature does and does not
support: personalised models reached a 13% median WER for severe
speakers in Green et al. 2021, but with a fine-tuned RNN-T trained on a
median 1,530 utterances per speaker, which is a different and much
heavier method than a phrase lexicon.

Honest note on the fixture numbers: the fixtures are synthetic text
built by code in this repo (`app/voice/synth.py`, garbling by
`app/voice/asr_sim.py`). They prove the reranking and fallback logic
behave as designed on simulated input. They prove nothing about real
microphones, real rooms, or real speakers. Real-world accuracy is
unproven, and a real-speaker validation set is roadmap issue #4.

## How it works

```
Speaker tries a phrase
        │
        ▼
Recognizer n-best list ──► (v0.1.0: stub TEXT SIMULATOR, no audio.
  (4 garbled candidates     Real ASR behind the same endpoint is
   with simulated scores)   roadmap issue #1)
        │
        ▼
Rerank: every lexicon phrase scored against the whole n-best list
  (ASR-weighted embedding similarity, embeddings cached once)
  + boost from recent conversation context
        │
        ├── best score clears threshold ──► select lexicon phrase
        │
        ├── full tier + context evidence ──► repair pass, lower bar,
        │                                    only on the context boost
        │
        └── otherwise ──► HONEST FALLBACK: recognizer's top guess,
                          flagged "not in your lexicon"
        │
        ▼
Selected phrase displayed / voiced from the phrase board
One-tap correction: "it was this one" grows the lexicon
```

Design rules that do the safety work:

1. **Never force a match.** A wrong lexicon phrase is worse than an
   honest miss, because someone may act on it ("i need my suction"
   heard as "i am comfortable" is a safety failure, not an accuracy
   statistic). The eval harness fails the build if any out-of-lexicon
   fixture is force-matched.
2. **Selection happens in code, never in a model.** The gateway's chat
   endpoint is used only for a full-tier repair note. The stub chat
   backend cannot pick a phrase, and neither tier's selection depends
   on generated text.
3. **The repair bar needs new evidence.** The full tier's repair pass
   may clear a lower threshold only when conversation context actually
   boosts the winning phrase. An earlier build let a bare re-score
   lower the bar and force-matched out-of-lexicon utterances; a
   regression test now guards that path.
4. **Aphasia mode is a phrase board, not recognition.** Aphasia is a
   language disorder; dysarthria is a speech-motor disorder. Board
   selections are voiced by TTS (a stub tone in v0.1.0) and never pass
   through the recognizer or the reranker.
5. **One speaker in v0.1.0.** Multi-speaker profiles are roadmap
   issue #2. The lexicon belongs to one person; do not share one
   profile across speakers.

## Two tiers, one gateway

Tier is a routing profile on the same gateway, chosen by the `model`
name (`myvoice-frugal` / `myvoice-full`), an `X-Tier` header, or one
env var. Same endpoints, same JSON schema, same UI, same eval harness.
Reranking is identical in both tiers by design.

|  | Frugal (default) | Full / commercial |
| --- | --- | --- |
| Recognizer | Local small ASR (simulator in v0.1.0) | Larger ASR behind the same endpoint (integration path) |
| Context | Last 3 selections | Full history |
| Repair | None: below threshold means fallback | Repair pass on low confidence, only on context evidence, plus a number-and-phrase verifier on the rendered result |
| Playback | Local TTS alias, 8 kHz stub tone | Higher-quality TTS alias, 16 kHz stub tone; banked-voice playback is roadmap issue #3, consent-gated |

What the full tier buys is the out-of-lexicon long tail and naturalness,
not better in-lexicon selection: on the shipped fixtures both tiers
score identically (19/20 in-lexicon, 0 forced out-of-lexicon), and the
one case full recovers that frugal misses needs real conversation
context to do it.

## The architecture: the product ships its own AI gateway

MyVoice Lexicon serves OpenAI-compatible endpoints from inside the app
(`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`,
`/v1/audio/transcriptions`, `/v1/audio/speech`), and every AI feature
calls those endpoints. Nothing talks to a vendor API directly. One
environment variable picks the backend:

- `stub` (default): deterministic, no model, no keys. Transcription is
  the text simulator, speech is a placeholder tone, embeddings are a
  hashed bag-of-words. This is what CI and the demo run.
- `local`: an OpenAI-compatible server on your own hardware for the
  chat/embedding slots today; real local ASR/TTS wiring is the roadmap
  #1 integration path. The self-hosted deployment is the point: a
  speaker's phrases and voice never need to leave the home.
- `upstream`: any OpenAI-compatible provider, for teams that accept
  that trade-off.

This gateway is the shared platform skeleton across this weekly product
series. Weeks 3–6 (WoundDelta, PillTray, Pose-Not-Pixels, FaceFlag)
shipped the vision side on the same skeleton; Week 7 is the first voice
product and swaps in the lexicon domain module. See
docs/ARCHITECTURE.md.

## Quickstart

```
git clone https://github.com/rtmalikian/myvoice-lexicon
cd myvoice-lexicon
cp .env.example .env
docker compose up --build
# open http://localhost:8000
```

Or without Docker:

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

Try the demo cases in the UI, or:

```
curl -X POST "http://localhost:8000/api/demo/recognize?case=needs_water_severe" \
  -H "X-Tier: frugal"
```

## API sketch

| Route | What it does |
| --- | --- |
| `GET /v1/models` | Lists `myvoice-frugal`, `myvoice-full`, the stub model, and the ASR/TTS aliases per tier |
| `POST /v1/audio/transcriptions` | OpenAI-shaped transcription. v0.1.0: text simulator in, n-best out, `simulated: true` |
| `POST /v1/embeddings` | OpenAI-shaped embeddings (hashed bag-of-words stub embedder) |
| `POST /v1/audio/speech` | OpenAI-shaped speech. v0.1.0: placeholder tone WAV, `X-MyVoice-Stub-Tone: true` |
| `POST /v1/chat/completions` | OpenAI-shaped chat, repair notes only; audio parts rejected (400) |
| `GET /api/lexicon` / `POST /api/lexicon` | Read the lexicon; add a phrase (embedded once, cached) |
| `POST /api/lexicon/correct` | One-tap correction: records the intended phrase, grows the lexicon |
| `GET /api/board` | The phrase board (aphasia mode), grouped by category |
| `POST /api/recognize` | Typed utterance + severity → simulated n-best → rerank → selected phrase |
| `POST /api/demo/recognize?case=...` | Synthetic demo case with known ground truth |
| `POST /api/speak` | Voice a board phrase (stub tone in v0.1.0) |
| `GET /api/history` | Selection history for this session |

## Tests

```
.venv/bin/python -m pytest -q
```

The suite covers the simulator (determinism, severity ordering), the
gateway (models, embeddings, simulated transcription labelling, stub
speech, audio-part rejection), the lexicon (dedupe, correction growth,
embedding cache), the reranker (in-lexicon recovery, the honest severe
miss, context repair, the no-forced-match regression guard), the eval
harness (in-lexicon and out-of-lexicon accuracy asserted separately),
the API end to end, the PHI redaction gate, and repo-level checks
(disclaimer first in README, no unverified corpus figure, EVIDENCE.md
carries the honest limits, thresholds labelled app-defined).

## Roadmap

Issues #1 to #5 are open as collaboration magnets: real audio ASR
behind the transcription endpoint, multi-speaker profiles, voice
banking and cloned-voice playback with documented consent, a
real-speaker validation set with in-lexicon and out-of-lexicon accuracy
reported separately, and persistence plus auth. Contributions welcome,
especially from speech-language pathologists and AAC users willing to
say where the phrase set and the fallback behaviour are wrong.

## License

MIT. Built by Raphael Malikian (https://github.com/rtmalikian) as Week 7
of a weekly open-source clinical AI series.
