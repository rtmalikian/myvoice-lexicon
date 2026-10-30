# SECURITY.md — MyVoice Lexicon

## The limits, plainly

- MyVoice Lexicon is a proof of concept. It has not been tested
  clinically, it is not a medical device, and it is a communication aid
  only. It does not diagnose, treat, or rule out any condition.
- A selected phrase can be wrong. The recognizer's output on dysarthric
  speech is unreliable by the published evidence (every commercial
  system tested exceeded 51% WER on severe dysarthria in a 2025
  zero-shot benchmark; see EVIDENCE.md), and this app's reranker has
  never been measured on a real speaker. Confirm every phrase with the
  speaker before acting on it. A wrong "i am comfortable" in place of
  "i need my suction" is a safety failure, not a rounding error.
- v0.1.0 recognizes no audio. The recognizer is a text simulator and
  playback is a placeholder tone. Do not describe this version as a
  working speech product.
- No threshold in this repo is a validated cut-off. Match, repair, and
  context-boost settings are APP_DEFINED_UNVALIDATED, set on synthetic
  fixtures.
- Regulatory status: none claimed. No FDA clearance, CE marking, or
  medical-device validation is implied anywhere in this repo.

## Voice data, consent, and privacy

Voice is sensitive data. A person's voice identifies them, and a
recording of disordered speech also reveals a health condition. Treat
both as private by default.

- **v0.1.0 stores no audio at all.** There is no recording feature, no
  audio input type, and nothing to leak. The lexicon is text: phrases a
  speaker and their family chose to write down. Storage is in-memory;
  restarting the app forgets everything.
- **Consent before enrolment.** When real ASR lands (roadmap issue
  #1), enrolling a speaker means recording their voice. That requires
  the speaker's own informed consent wherever they can give it, a clear
  statement of what is recorded, where it is stored, and how to delete
  it, and a working deletion path. Family members and clinicians do not
  consent on a speaker's behalf by default.
- **Voice banking and cloning are consent-gated** (roadmap issue #3).
  A banked or cloned voice is the speaker's voice. It is recorded only
  with documented consent, used only to voice that speaker's own
  phrases, and deleted on request. Never clone a voice from recordings
  made for another purpose.
- **Self-hosting is the privacy design.** The gateway exists so a real
  deployment can run every model on hardware in the speaker's home.
  Sending a disabled speaker's voice and phrase history to a third-party
  API is a decision for the speaker and their family, not a default.
- **Logs carry kinds and counts only**: never phrase text, never
  utterances, never recordings. Speaker labels pass through a PHI
  redaction gate before storage.
- There is no authentication in v0.1.0 and storage is in-memory. Do not
  deploy this version for a real speaker outside a local demo.

## Reporting a safety problem

If you find output language that presents a selected phrase as certain,
claims clinical validation, or a code path that force-matches an
out-of-lexicon utterance into the lexicon, open an issue with the exact
output text and the demo case. Those are treated as safety bugs, not
cosmetic bugs.
