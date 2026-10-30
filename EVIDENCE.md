# EVIDENCE.md — MyVoice Lexicon

Every claim below follows the weekly-series evidence standard: Claim | Source
(full citation + link) | Tier | What it proves | What it does NOT prove.
Tier 1 = systematic review / meta-analysis / guideline / authoritative
compendium. Tier 2 = RCT / large cohort / validated real-patient measurement
study. Tier 3 = small observational / pilot. Tier 4 = vendor / press /
synthetic results, labelled as such, never dressed as evidence.

Sources marked **[S]** were search-identified in the 2026-10-23 evidence
audit of this product concept and were not re-opened in full at build time.
Green et al. 2021 was opened in full during that audit.

## (a) The problem is real and large

| Claim | Source | Tier | Proves | Does NOT prove |
|---|---|---|---|---|
| About 2 million people in the US live with aphasia (ASHA gives a wider range of 2–4 million) and nearly 180,000 acquire it each year | National Institute on Deafness and Other Communication Disorders (NIDCD), "Quick Statistics About Voice, Speech, Language", citing the National Aphasia Association. https://www.nidcd.nih.gov/health/statistics/quick-statistics-voice-speech-language ; ASHA Aphasia page https://www.asha.org/practice-portal/clinical-topics/aphasia/ **[S]** | Tier 1 (authoritative summary; underlying estimate is association-derived, not a peer-reviewed prevalence study) | The standard US figures for aphasia, the population the phrase-board (aphasia) mode serves | Anything about dysarthria. Aphasia is a language disorder; dysarthria is a speech-motor disorder. They are different populations with different failure modes, and this repo does not cite aphasia prevalence as evidence for a speech-recognition need, or dysarthria error rates as evidence for a phrase-board need |
| 80–95% of people with ALS eventually reach a point where natural speech no longer meets their daily communication needs | Management of Dysarthria in ALS (review). https://pmc.ncbi.nlm.nih.gov/articles/PMC12293193/ ; corroborated by Communicative Participation in ALS. https://pmc.ncbi.nlm.nih.gov/articles/PMC7949226/ **[S]** | Tier 1 (review synthesis) | The scale of speech loss in one dysarthria population over the disease course | That loss is total in all cases, that it happens early, or that ASR is the right aid at late stage: many late-stage users need AAC or eye-gaze, not speech recognition |
| Generic ASR fails severe dysarthria badly | See Green et al. 2021 and the TORGO benchmark in section (b): speaker-independent median WER 31% in Green's study, commercial systems at 78–89% WER for severe dysarthria in the literature Green cites, and every system above 51% WER on severe dysarthria in the 2025 zero-shot TORGO benchmark | Tier 2 | That "just use a normal speech recognizer" is not a working answer for severe dysarthric speech | That this app's approach fixes it. See section (b) for exactly where the evidence stops |

## (b) The solution method works in principle (and where it stops)

| Claim | Source | Tier | Proves | Does NOT prove |
|---|---|---|---|---|
| Personalised ASR dramatically beats generic ASR on short read phrases: personalised median WER 4.6% overall and 13% for the severe group, vs a speaker-independent median of 31% | Green et al., "Automatic Speech Recognition of Disordered Speech: Personalized Models Outperforming Human Listeners on Short Phrases," Interspeech 2021, pp. 4778–4782. https://www.isca-archive.org/interspeech_2021/green21_interspeech.pdf (opened in full in the 2026-10-23 audit). 432 speakers, each contributing at least 300 short phrases (median 1,530 training utterances per speaker) | Tier 2 (large measurement study, read short phrases, home recordings) | Personalisation is the right direction: adapting to one speaker's speech beats scaling a generic model, on short phrases | That MyVoice Lexicon achieves anything like 13% WER. Green used a fine-tuned RNN-T trained on a median 1,530 utterances per speaker. MyVoice uses a 50–300 phrase lexicon and reranks a small recognizer's n-best list. Different method, far less per-speaker data, no WER measurement at all in v0.1.0 (the recognizer is a text simulator). The 13% figure is evidence for personalisation in principle, never a claim about this app |
| Conversational speech is much harder than read phrases, even personalised: conversational median WER 36.1 vs read 14.6 in the same study; personalisation cut the severe group's conversational median from about 90% to 28% | Tobin et al., "Automatic Speech Recognition of Conversational Speech in Individuals With Disordered Speech," J Speech Lang Hear Res 2024;67(11):4176–4185. https://pubs.asha.org/doi/10.1044/2024_JSLHR-24-00045 **[S]** | Tier 2 | Why this product is scoped to a fixed personal phrase set instead of open conversation: the fixed-phrase design is a deliberate scope restriction, not a conversational ASR claim. Even 28% WER is roughly one word in four wrong | That a lexicon approach reaches conversational usability. It sidesteps conversation by design, at the cost of only ever saying what is in the lexicon |
| Modern commercial systems still fail severe dysarthria zero-shot: every system tested exceeded 51% WER (best: AssemblyAI 51.8%, Whisper 52.9%) | Benchmarking Commercial Speech Recognition and Multimodal Systems on the TORGO corpus (8 systems: 4 conventional ASR + 4 multimodal LLM). https://onlinelibrary.wiley.com/doi/full/10.1155/int/6065038 **[S]** | Tier 2/3 (validated measurement on TORGO; small severe-speaker set; zero-shot/default settings) | A current severity-stratified baseline: mild dysarthria is nearly solved (about 1–5% WER), severe is not | A head-to-head comparison with Green's 13%. Different corpus (TORGO vs Green's home phrases), different systems, different settings, personalised vs zero-shot. This repo never presents "51% vs 13%" as one comparison |
| Research corpora for disordered speech exist at usable scale: the Speech Accessibility Project's Interspeech 2025 challenge set comprised about 415 hours from 524 participants (PD/Down syndrome/ALS/CP/stroke); by early 2025 the project had passed 1,000 hours with more than 1,400 contributors | Zheng et al., SAP Challenge paper, Interspeech 2025. https://www.isca-archive.org/interspeech_2025/zheng25_interspeech.pdf **[S]** ; Zwilling et al., SAP best-practices paper, Interspeech 2025. https://www.isca-archive.org/interspeech_2025/zwilling25_interspeech.pdf **[S]** | Tier 2 (dataset papers) | A labelled real-speaker validation path exists (roadmap issue #4). These are the citable figures for the challenge release; totals move with each release, so cite the release, not a floating number | Cross-etiology generalisation: early SAP releases were Parkinson's-heavy, so the corpus does not by itself prove performance for ALS or post-stroke speakers. An earlier draft of this product's research notes carried a larger SAP size figure that could not be verified in any returned source; it is not used anywhere in this repo |

## The target, stated as a target

Phrase accuracy of 80% or better on in-lexicon phrases is a
**target to be demonstrated**, not a result. It has not been demonstrated on real speakers,
real audio, or any system of this design. The eval harness in `tests/`
measures the shipped synthetic fixtures only (Tier 4): on those fixtures the
reranker selects the intended phrase in 19 of 20 in-lexicon cases and never
force-matches an out-of-lexicon utterance. Those numbers prove the pipeline
behaves as designed on simulated text. Out-of-lexicon performance is reported
separately in the README and the tests, never blended into the in-lexicon
figure.

## What this app has NOT proven

- Its accuracy on real speakers is unproven. v0.1.0 recognizes no audio at
  all: the recognizer is a text simulator that garbles typed phrases with a
  fixed confusability table. Nothing in this repo measures word error rate.
- The lexicon-rerank method itself (small ASR + personal phrase lexicon +
  embedding rerank) has no published validation for dysarthric or aphasic
  speech. Green et al. validate per-speaker model fine-tuning, a different
  and much heavier method. The enrolment question (how few phrases and
  utterances suffice) is open; closing it needs within-speaker validation on
  dysarthric and aphasic speakers separately (roadmap issue #4).
- Every threshold in the code (match, repair, context boost, severity
  garbling rates) is APP_DEFINED_UNVALIDATED, set on the synthetic fixtures,
  never tuned on a real speaker.
- No communication-participation outcome (the outcome that actually matters
  to users) has been measured for this design.
