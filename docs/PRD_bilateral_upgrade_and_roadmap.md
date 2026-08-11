# ASV — Product Requirements Document
## Bilateral 6-Electrode Upgrade & Path to a Pretrained, Transferable Model

| | |
|---|---|
| **Status** | Draft for review |
| **Version** | 1.0 |
| **Date** | 2026-08-11 |
| **Owner** | ASV project (subject S01 / repo maintainer) |
| **Repo state this PRD is written against** | Firmware v2.0.0-arduino (interrupt-paced, 860 SPS), `refined_model/` (utterance-level SVM, 100% leave-one-recording-out on 5 words, single subject, single channel) |

---

## 1. TL;DR

The project has a working single-channel proof of concept: real jaw EMG,
correctly filtered, correctly classified, with an honestly-measured
leave-one-recording-out accuracy of 100% on 5 words for one subject. That
result is real but narrow — one person, one electrode pair, one session, five
words. This PRD defines the next phase in two parts:

- **Part A/B — Hardware + ML:** add a second AD8232 front-end on the left
  side of the face (mirroring the existing right-side placement), bringing
  the system to **6 electrodes total** (3 per side: 2 signal + 1 bone
  reference) and **2 EMG channels**, and extend the ML pipeline to use both.
- **Part C — Roadmap:** turn the project from "one bespoke model per person"
  into something with a **reusable, pretrained component** — a base
  representation trained across subjects and sessions that a new user can
  adapt to with a handful of calibration reps, rather than fifty recordings
  and a from-scratch training run every time.

Nothing below claims results that don't exist yet. The bilateral hardware is
**not built**; every number in Part A/B is a target, not a measurement.

---

## 2. Where the project actually is today

| Layer | State |
|---|---|
| Firmware | Working. ADS1115 read at 860 SPS, hardware-paced via the `ALRT`/RDY interrupt, dual-core separation (sampler on core 1, BLE/OLED/UI on core 0), lock-free ring buffer. Compiles clean, self-test passes. |
| Acquisition | Working, tested. `collect_emg.py` implements a 3-2-1 countdown + 2 s capture protocol; produces the dataset the model was trained on. |
| Dataset | 50 recordings, subject **S01 only**, 5 classes (`hello`, `help`, `no`, `rest`, `yes`), 10 reps each, single session, single electrode pair (right masseter + bone reference). |
| ML — refined model | Utterance-level feature extraction (19 features/window) + SVM. **100% leave-one-recording-out**, **100% repeated 5-fold ×10**, **100% on a train-early/test-late temporal split in both directions**. Chance level is 20% (5 classes). |
| Live inference tools | `tools/plot_words.py` (GUI: waveform + word + OLED alert) and `tools/predict_live.py` (CLI). Both were found to have a capture-robustness bug (serial parsing coupled to GUI frame timing could silently truncate a capture, which the classifier then reads as "rest" at a deceptively plausible ~46% confidence) — **fixed** in this pass with a background-thread reader, pre-roll capture, and a live signal-health check (see §12, Appendix). |
| Frontend / backend | FastAPI backend serves the refined model over `/predict_utterance` and a real-recording replay endpoint; Next.js frontend has a working "Live Detection" screen wired to real predictions (replay mode verified end-to-end; live Web-Serial mode implemented, not yet hardware-verified). |

**The honest headline:** the ML approach is validated. The hardware and
dataset are not yet broad enough to claim anything beyond "this works for one
person, right now, with the electrodes exactly where they were during
training." That gap is what this PRD closes.

---

## 3. Problem statement

1. **One channel is a hard ceiling.** The stock AD8232 front-end is
   ECG-filtered (~0.5–40 Hz); real EMG energy lives at 20–450 Hz. What the
   system reads is an envelope, not the underlying muscle detail. A second,
   spatially-separated channel is the cheapest available way to add real
   information without waiting on a front-end redesign.
2. **One subject is not evidence of generalization.** EMG is famously
   subject- and placement-specific (this is already documented project
   wisdom, not new). Right now there is zero data on whether the model
   degrades across days, re-adhesion, or a second person — because none has
   been collected.
3. **No reusable asset exists.** Every new user currently means: mount
   electrodes, record 50 clips, retrain from scratch, hope it works. That
   does not scale to being useful for the actual target users (people who
   are mute or speech-impaired) or to anyone evaluating/extending the
   project. A pretrained base model that a new user *calibrates* rather than
   *creates* is the difference between a demo and a tool.
4. **The vocabulary is 5 words, one of which is "not speaking."** Any real
   use case needs more words. Vocabulary expansion is deliberately gated
   behind the items above — adding words on an unstable, single-subject,
   single-channel foundation would confound every failure mode at once.

---

## 4. Goals / Non-goals

**Goals**
- G1: Field a working 2-channel (bilateral, 6-electrode) capture system with
  the same timing guarantees the 1-channel system already has (860 SPS,
  interrupt-paced, sub-millisecond jitter).
- G2: Extend the refined feature/training pipeline to consume 2 channels
  without breaking the existing 1-channel path.
- G3: Establish, with actual measurements, whether bilateral placement
  improves accuracy, redundancy (tolerate one bad electrode), or both.
- G4: Produce a written, versioned protocol for multi-subject, multi-session
  data collection — the precondition for any "pretrained" claim.
- G5: Define and reach a first calibration-based transfer-learning
  milestone: a new subject reaches a stated accuracy bar with materially
  fewer reps than the 50 used to build the S01 model.

**Non-goals (explicitly out of scope for this phase)**
- Open-vocabulary / continuous silent speech recognition. Still a closed,
  small-vocabulary word classifier.
- On-device (ESP32) inference. Inference stays PC/backend-side.
- Any medical or clinical claim. This remains a research/hobby-grade system.
- A production mobile app. The Next.js frontend stays a demo/dev harness.

---

## 5. Users

- **Primary (eventual):** individuals who are mute or have severe speech
  impairment, for whom a small, personalizable silent-vocabulary device has
  real utility (yes/no/help/pain/bathroom-class words).
- **Primary (current phase):** the project's own developer(s) and subject
  S01, since the immediate work is hardware bring-up and data collection.
- **Secondary:** researchers/contributors extending the codebase — the ML
  pipeline and firmware should stay legible enough for someone else to pick
  up.

---

## 6. PART A — Hardware: Bilateral 6-Electrode Architecture

### 6.1 Electrode plan

Mirror the existing, already-debugged right-side placement onto the left
side. The project already learned the hard way (see `test.png`,
`clench_test.png` in project history) that the reference electrode must sit
on **bone**, not muscle — that lesson carries over directly.

| Side | Electrode | Role |
|---|---|---|
| Right (existing) | 2× signal | Differential pair over right masseter → AD8232 #1 `IN+`/`IN-` |
| Right (existing) | 1× reference | AD8232 #1 `RL`, placed on bone (mandible/mastoid) |
| Left (new) | 2× signal | Differential pair over left masseter → AD8232 #2 `IN+`/`IN-` |
| Left (new) | 1× reference | AD8232 #2 `RL`, placed on bone, mirrored position |

**Total: 6 electrodes, 2 independent references.** This is the primary plan
because it keeps each channel's common-mode rejection fully independent,
which is the safer default while the concept is unproven.

**Variant worth testing later:** a single shared reference electrode across
both AD8232 modules (5 electrodes total). This is common in multi-channel
EMG rigs and would reduce prep time and improve inter-channel comparability
(both channels referenced to the exact same point). Do not start here —
independent references are easier to debug in isolation if one channel
misbehaves. Revisit once the 6-electrode system is validated.

### 6.2 ADC architecture — the decision that actually matters

The ADS1115 is a single ADC behind a 4-input mux. It **cannot** convert two
channels simultaneously at full rate. This is the one place a naive
implementation would silently violate the project's own stated principle
("a sampling-rate mismatch silently destroys accuracy") — so it needs to be
an explicit decision, not an afterthought.

| Option | Description | Per-channel rate | New parts | Firmware complexity |
|---|---|---|---|---|
| **A — Dual ADS1115 (recommended)** | Second ADS1115 at I2C address `0x49` (`ADDR`→VDD), same dedicated I2C bus A, independent continuous-mode conversions, independent `ALRT` line | **860 SPS on both channels**, no compromise | 1× ADS1115 breakout (~$3–5) | Moderate — extend `AsvSample` to 2 channels, second ISR, sampler task reads both each cycle |
| B — Time-multiplexed single ADS1115 | Alternate the mux between `A0`/`A1` every conversion | ~430 SPS effective per channel (half) | None | Low |

**Recommendation: Option A.** The project's entire firmware design
philosophy (interrupt-paced, no silent rate loss, "the accuracy wire") argues
against accepting a rate cut when a $5 part avoids it. Option B is listed
only as a same-day bring-up fallback if a second ADS1115 isn't in hand yet —
if used even temporarily, `ml/config/settings.py: SAMPLING_RATE_HZ` **must**
be updated to match and the dataset re-collected at that rate; never mix
430 SPS and 860 SPS recordings in one training set.

### 6.3 Concrete pin plan

Chosen to respect the existing "pins to avoid" list in
`docs/GPIO_MAPPING.md` (flash pins 6–11, strapping pins 0/2/12/15) and the
existing bus separation principle (I2C bus A stays ADS1115-only; OLED stays
on bus B).

| Signal | GPIO | Notes |
|---|---|---|
| ADS1115 #2 `ALRT` | **GPIO 4** | Regular GPIO, supports internal pull-up (mirrors how `ALRT1` uses GPIO27 with `INPUT_PULLUP`) |
| AD8232 #2 `LO+` | **GPIO 32** | Input-only, no pull-up needed — AD8232 drives it (mirrors GPIO34 pattern) |
| AD8232 #2 `LO-` | **GPIO 33** | Input-only, same pattern (mirrors GPIO35) |
| ADS1115 #2 I2C | SDA 21 / SCL 22 (shared) | Same dedicated bus A as ADS1115 #1, different address |
| ADS1115 #2 address | `0x49` | `ADDR` pin tied to `VDD` |

I2C bus timing check: at 400 kHz, a single-register conversion read (the
existing "cached pointer register" trick) takes on the order of tens of
microseconds. Two sequential reads per sample period (1.16 ms at 860 SPS)
comfortably fit the timing budget — this was a real concern worth checking,
and it clears with margin.

### 6.4 Firmware work items

- `asv_config.h` — add `PIN_ADS_ALERT2`, `PIN_AD8232_LO_P2`,
  `PIN_AD8232_LO_N2`, `ADS1115_2_I2C_ADDR`, bump `ASV_NUM_CHANNELS` to 2.
- `asv_adc.cpp/h` — generalize `AsvSample` to carry `v[2]` and `flags` for
  both lead-off pairs; add a second `armReadyPin()`/`applyConfig()` pass for
  the second chip; extend the sampler task to service both ISRs and read
  both conversion registers per cycle; extend the ring buffer element size
  accordingly (`ASV_RING_SIZE` may need revisiting for memory headroom).
- `asv_diag.cpp` — extend the self-test to probe and register-verify **both**
  ADS1115 chips independently; report `RDY-INTERRUPT` mode per channel (one
  channel could legitimately fall back to polling if its ALRT wire is bad
  while the other is fine — the self-test should say so, not hide it).
- `ASV_Firmware.ino` — CSV stream header and per-sample line move to
  `timestamp_us,ch0,ch1` (schema v3); keep parsing backward-compatible where
  reasonable (or clearly version-gate it — the codebase already treats
  format drift seriously, e.g. `# ASV_STREAM v2` in the header line).

### 6.5 Acquisition / ML data-format changes

- `ml/config/settings.py`: `NUM_CHANNELS = 2`.
- `ml/acquisition/serial_reader.py`: parse N channel columns generically
  (much of this is already channel-count-driven via `settings.NUM_CHANNELS`
  — confirm and close any remaining 1-channel assumptions).
- `datasets/custom_silent_speech/raw/.../repNNN_*.csv`: new recordings carry
  `channel_0,channel_1`. Do not retrofit old S01 single-channel recordings
  with a fake second channel — keep them as a distinct, clearly-labelled
  single-channel dataset generation for historical comparison.

### 6.6 Bring-up acceptance criteria (mirrors the existing single-channel bar)

1. `.\tools\asv.ps1 build` — compiles clean.
2. Self-test reports `ALL CHECKS PASSED` for **both** ADS1115 chips, both in
   `RDY-INTERRUPT` mode.
3. Both channels show baseline ≈ 1635 mV at rest, peak-to-peak within the
   healthy band (this PRD's tooling now has a shared `signal_health()`
   helper — reuse it, don't reinvent the thresholds).
4. A captured stream shows `dt` std/mean well under 0.25 on **both**
   channels independently (the existing timing-jitter bar).
5. `python -m pytest tests/ -q` still passes (extend tests to cover 2-channel
   CSV parsing before declaring this done).

---

## 7. PART B — ML pipeline: multi-channel refined model

### 7.1 Feature extractor generalization

`ml/refined/utterance_features.py` is currently hardcoded for 1 channel.
Required changes:
- Per-channel features (the existing 19) computed independently for `ch0`
  and `ch1` → 38 base features.
- **New cross-channel features**, which is the actual point of going
  bilateral, not just doubling the feature count:
  - Inter-channel correlation coefficient over the utterance window.
  - Left/right amplitude ratio (RMS₀ / RMS₁) — captures asymmetric jaw
    activity if it exists.
  - Onset-time difference between channels (does one side's burst lead the
    other?).
- Keep `extract()`'s signature length-agnostic and channel-count-driven, the
  way `ml/utils/features.py` already is — that file's `(n_samples,
  n_channels)` vectorized design is the right shape to copy from.

### 7.2 Retraining plan & backward compatibility

- `ml/refined/train_refined.py` already discovers recordings generically and
  should keep working once `NUM_CHANNELS=2` recordings exist — verify rather
  than assume.
- Keep the existing 1-channel `refined_model/` around as a labelled baseline
  (`refined_model_1ch_s01/`) rather than overwriting it. The bilateral model
  becomes `refined_model/` once it's validated, not before.

### 7.3 Evaluation plan — go further than before

Repeat everything the 1-channel model was validated with (LOO,
repeated 5-fold, temporal split), **plus** a test the 1-channel system never
had the data to run:

- **Cross-session (different day) test on S01.** Re-mount the electrodes on
  a different day, record a small held-out set, and check accuracy without
  retraining. This is the single most important missing measurement in the
  project right now — it is the difference between "the model learned the
  words" and "the model memorized today's electrode placement."

---

## 8. PART C — Roadmap toward a pretrained, transferable model

This is the direct answer to "advance this project into the pretrained
dataset for future development." It's sequenced deliberately — each phase's
exit criterion gates the next, so a shaky foundation doesn't get papered
over by adding more data on top of it.

### Phase 1 — Within-subject robustness (S01, bilateral)
Collect the bilateral dataset across **multiple sessions on multiple days**,
not one sitting. Quantify placement-drift directly: train on day 1, test on
day 2+ without retraining.
*Exit criterion:* cross-day accuracy on S01 stays clearly above chance and
is documented honestly, whatever the number is.

### Phase 2 — Multi-subject corpus
Recruit additional subjects (target: 8–15, in line with the scale of
published EMG-speech corpora like EMG-UKA's 8 speakers — see §8.4). Freeze a
standardized protocol before starting: same vocabulary, same countdown
timing, same electrode placement instructions, informed consent for
biosignal data collection.
*Exit criterion:* a documented, versioned multi-subject dataset with
per-subject signal-health and quality metrics — not just raw file counts.

### Phase 3 — Calibration-based transfer learning
This is the actual "pretrained" milestone. Train a base
representation (shared feature space or shared model) on the pooled
multi-subject corpus from Phase 2. A **new** subject then *calibrates*
rather than trains from scratch: a small number of reps per word (target:
≤10, versus the 50 recordings used for the current from-scratch S01 model)
fine-tunes or re-references the base model to them.
*Exit criterion:* a new subject reaches a stated accuracy bar (e.g. ≥80% on
the core vocabulary) after calibration with ≤10 reps/word. This is the
number that actually matters for real-world usability — nobody using this
as an assistive device wants to record 50 clips per word before it works.

### Phase 4 — External corpus alignment (use with real caution)
Evaluate whether published facial/laryngeal EMG silent-speech corpora can
contribute to pretraining a shared feature encoder:

- **EMG-UKA** (Wand & Janke, Interspeech 2014) — 63 sessions, 8 speakers,
  ~7.5 hours, audible/whispered/silent facial EMG.
- **EMG-PIT** (used in Schultz & Wand, *Speech Communication* 52(4), 2010,
  "Modeling coarticulation in EMG-based continuous speech recognition") —
  multi-speaker silent/audible EMG.
- Gaddy & Klein's released facial-EMG dataset from **"Digital Voicing of
  Silent Speech"** (EMNLP 2020) and its follow-up **"An Improved Model for
  Voicing Silent Speech"** (ACL 2021, +25.8% absolute on open-vocabulary
  intelligibility over the prior state of the art) — an 8-electrode facial
  array, openly released.

**The explicit warning, stated because this project already made this exact
mistake once:** the earlier version of this project trained on NinaPro DB1,
a *forearm/hand-gesture* EMG dataset, and produced a model that could never
have worked — wrong muscle group entirely (documented in
`docs/CURRENT_SYSTEM_AUDIT.md`). Any external corpus considered here **must**
be facial/articulatory EMG, and even then, electrode count, montage, and
placement will differ from this project's hardware — treat this as a
representation-learning / transfer experiment, not a drop-in weights swap.
Validate against the project's own held-out data before trusting it.

### Phase 5 — Vocabulary scaling
Only after Phase 3's calibration milestone is real: grow the vocabulary in
stages (5 → ~15 → ~50 words), prioritizing AAC-relevant core vocabulary
(yes/no/help/water/pain/bathroom/stop/more/…) over arbitrary word lists.
Each stage re-runs the full evaluation protocol — a bigger vocabulary that
hasn't been re-validated is not progress.

### Data governance (applies from Phase 1 onward)
- **Verified vs. unverified split**, already established in this pass: only
  `ml/acquisition/collect_emg.py`'s ground-truth-labelled protocol writes to
  the trusted `datasets/custom_silent_speech/raw/` tree. Live-tool captures
  go to a separate `live_unverified/` tree and require manual review before
  promotion — this exists specifically so a wrong live prediction can never
  silently poison the training set.
- **Dataset and model versioning**: keep the existing convention
  (`ml/models/asv_model_<timestamp>/`, curated `refined_model/`) and extend
  it with a per-dataset manifest (subject, session date, electrode
  configuration, channel count) once multi-subject data exists.

---

## 9. Success metrics

| Phase | Metric | Target |
|---|---|---|
| Hardware bring-up | Dual self-test | Both ADS1115 chips `ALL CHECKS PASSED`, `RDY-INTERRUPT` |
| Hardware bring-up | Per-channel jitter | `dt` std/mean < 0.25, both channels |
| Bilateral ML | Same-session LOO (S01, 2ch) | Documented, whatever it is — compare honestly against the 1-channel 100% baseline |
| Phase 1 | Cross-day accuracy (S01) | > chance, documented; this is a measurement milestone, not a pass/fail gate |
| Phase 2 | Corpus size | 8–15 subjects, standardized protocol, informed consent on file |
| Phase 3 | Calibration accuracy | ≥80% on core vocabulary after ≤10 reps/word for a new subject |
| Phase 5 | Vocabulary | Staged growth only after Phase 3 gate is met |

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| EMG is highly subject/placement-specific — bilateral data may not transfer any better than 1-channel did | Phase 1's cross-day test measures this directly before any multi-subject investment |
| Dual-ADC I2C bus timing headroom | Checked in §6.2/6.3 — sequential register reads fit inside the 1.16 ms sample period with margin; verify empirically once built, not just on paper |
| 6 electrodes hurts wearability/comfort for the actual target users | Track as an explicit UX concern once bilateral is validated; the shared-reference 5-electrode variant (§6.1) is the first lever to pull |
| Biosignal data is sensitive | Informed consent required from Phase 2 onward; no data leaves the project without explicit subject consent; this is not a medical device and must not be marketed as one |
| "Pretrained" scope creep — trying to use mismatched external EMG data | §8.4's explicit warning, grounded in the project's own NinaPro mistake |
| Live-tool robustness bugs (like the capture-truncation issue found and fixed this pass) resurface as new capture paths are added | Any new live/streaming tool must reuse `signal_health()` and the background-thread capture pattern established in `tools/plot_words.py` — don't re-litigate this per tool |

---

## 11. Suggested milestone sequencing

Relative ordering, not calendar commitments — pace this against actual
hardware/part availability:

1. Order second AD8232 + ADS1115; verify Option A's I2C timing budget on the
   bench before committing pins in `asv_config.h`.
2. Firmware: dual-ADC bring-up, self-test extension, CSV schema v3.
3. Acquisition: `settings.py`/`serial_reader.py` 2-channel support;
   re-validate `tests/test_pipeline.py`.
4. Collect bilateral S01 dataset across ≥3 separate sessions/days.
5. Extend `ml/refined/utterance_features.py` to 2 channels + cross-channel
   features; retrain; run the full evaluation protocol including the new
   cross-day test.
6. Write up Phase 1 results honestly (whatever they are) before recruiting
   additional subjects — don't scale a foundation that hasn't been checked.
7. Begin Phase 2 (multi-subject) only after step 6's exit criterion is met.

---

## 12. Appendix — what changed in this pass (context for the above)

- Diagnosed and fixed a real bug in `tools/plot_words.py` /
  `tools/predict_live.py`: serial ingestion was coupled to GUI/loop timing,
  so a slow frame could silently truncate a capture; a truncated capture
  reliably misclassifies as "rest" at a plausible-looking ~46% confidence
  (reproduced offline against the real trained model). Fixed with a
  background-thread reader, timestamped ring buffer, pre-roll capture, and
  a shared `signal_health()` check — verified end-to-end against real
  recordings with simulated realistic reaction lag (5/5 correct).
- This is the same class of problem the bilateral upgrade must not repeat:
  any new capture path should be built on the same decoupled-reader pattern
  from day one, not discovered as a bug later.

---

## 13. Open questions for the team

- Shared vs. independent reference electrodes (§6.1) — worth a quick bench
  comparison before committing to 6 electrodes permanently?
- Target subject count for Phase 2 — does 8–15 match what's actually
  recruitable, or should the plan start smaller?
- Is on-device (ESP32) inference ever in scope, or does the roadmap commit
  to PC/backend inference indefinitely? (Affects how much the calibration
  step in Phase 3 needs to be lightweight.)
