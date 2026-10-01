# ASV — A Silent Voice: A Low-Cost, Interrupt-Paced sEMG System for
# Utterance-Level Silent-Speech Word Classification

**A feasibility study and system report**

*[Author Name(s)] — affiliation placeholder*
*Draft — 2026-08-11. Formatting is plain Markdown; adapt to target venue
(LaTeX/ACL/IEEE template, arXiv, workshop submission) before submission.*

---

## Abstract

We present ASV, an open, low-cost surface electromyography (sEMG) system for
recognizing silently articulated words from jaw muscle activity, and report a
feasibility study on the first dataset collected with it. The hardware chain
(Ag/AgCl electrodes → AD8232 analog front-end → ADS1115 ADC → ESP32) samples
a single channel at a measured 860.93 Hz with interrupt-paced timing (mean
jitter σ = 2.8 µs across 50 recordings), driven by direct register control of
the ADS1115's conversion-ready interrupt rather than a polling library. We
show that reframing classification from the conventional sliding-window
approach (each 256 ms window independently labelled with its utterance's
class) to an **utterance-level** approach (one ~2 s recording = one feature
vector, describing the whole articulation's energy, envelope shape, and
spectral content) raises honestly cross-validated accuracy from 47.7%
(sliding-window, majority-overfits-to-rest) to **100%** leave-one-recording-out
accuracy on a 5-class vocabulary (`hello`, `help`, `no`, `rest`, `yes`; chance
level 20%), for one subject, one session, one electrode pair. We report this
result with its actual scope: single-subject, single-channel, small
closed vocabulary, controlled recording protocol. We describe the complete
system — firmware architecture, signal processing, feature engineering, and
evaluation methodology — in enough detail to reproduce it, document every
limitation we are aware of, and lay out a concrete extension (a bilateral,
6-electrode, 2-channel upgrade) and a roadmap toward a pretrained,
subject-transferable model, informed directly by a domain-mismatch mistake
made and corrected earlier in this project's own history.

**Keywords:** surface electromyography, silent speech interface, assistive
technology, embedded signal acquisition, ESP32, wearable sensing

---

## 1. Introduction

Silent speech interfaces aim to recognize what a person is saying from
articulatory muscle activity alone, without an audible signal — of particular
interest for individuals who are mute or have severe speech impairment, and
for communication in contexts where vocalizing is undesirable or impossible.
Surface electromyography (sEMG) over the facial and jaw muscles is one of the
more accessible sensing modalities for this: unlike ultrasound or
electromagnetic articulography, it requires only skin-contact electrodes and
commodity analog front-end hardware.

This paper documents ASV ("A Silent Voice"), a project built from
off-the-shelf hobbyist-grade parts — a SparkFun AD8232 (an ECG front-end
repurposed for EMG), a Texas Instruments ADS1115 16-bit ADC, and an ESP32
microcontroller — with two contributions:

1. **A firmware and acquisition system** that gets genuinely clean,
   correctly-timed signal off this hardware, which is a nontrivial part of
   the problem in itself (§3, §7).
2. **An utterance-level classification reframing** that substantially
   outperforms the naive sliding-window baseline on the same data, which we
   believe is a useful, generalizable lesson for anyone building a small
   silent-speech word classifier on similarly modest hardware (§4, §5).

We are explicit throughout about what this result does and does not show.
The honest scope is: one subject, one recording session, one channel, five
words. Section 6 lists every limitation we are aware of without softening
them. Section 7 describes a concrete, not-yet-built hardware extension
(bilateral 6-electrode capture) and Section 8 lays out a roadmap toward a
pretrained, cross-subject model — including a direct account of an earlier
mistake in this same project (training on a wrong-domain public dataset) that
now shapes how we think about using external data going forward.

---

## 2. Related work

Surface EMG for silent/silent-adjacent speech recognition has an established
research line, distinct from limb/gesture EMG (e.g. forearm EMG for hand
gesture recognition, as in the NinaPro database family — a distinction that
matters directly to this project; see §8.4).

- **Schultz & Wand (2010)**, *"Modeling coarticulation in EMG-based
  continuous speech recognition,"* Speech Communication 52(4):341–353,
  report on the EMG-PIT corpus, a multi-speaker database of silent and
  audible facial EMG, and address coarticulation modeling for continuous
  (not isolated-word) EMG speech recognition.
- **Wand & Janke (2014)**, *"The EMG-UKA Corpus for Electromyographic Speech
  Processing,"* Interspeech 2014, describe a corpus of 63 sessions across 8
  speakers (~7.5 hours) recorded in audible, whispered, and silent speaking
  modes with synchronous acoustic reference.
- **Janke & Diener (2017)**, *"EMG-to-Speech: Direct Generation of Speech
  From Facial Electromyographic Signals,"* IEEE/ACM TASLP 25(12), generate
  audible speech waveforms directly from facial EMG.
- **Gaddy & Klein (2020)**, *"Digital Voicing of Silent Speech,"* EMNLP 2020,
  introduce an 8-electrode facial EMG dataset (silent and vocalized) and a
  model voicing silently articulated speech from it; **Gaddy & Klein (2021)**,
  *"An Improved Model for Voicing Silent Speech,"* ACL 2021, improve
  open-vocabulary intelligibility by a reported 25.8 absolute points over
  their prior model.

These systems use purpose-built multi-electrode facial EMG arrays (typically
5–8 channels) and, in several cases, large multi-speaker corpora collected
specifically for this purpose. ASV differs in scale and intent: it is a
single-channel, single-subject feasibility study built on consumer hobbyist
hardware (total analog front-end + ADC + MCU cost under \$25), aimed at
establishing whether a minimal, reproducible hardware/software stack can
reach a small isolated-vocabulary classification task reliably before
investing in a larger multi-channel, multi-subject data collection effort —
the roadmap described in §8 explicitly aims to close the gap toward the
scale of the corpora above.

---

## 3. System description

### 3.1 Signal chain

```
jaw electrodes (Ag/AgCl) → AD8232 (analog front-end) → ADS1115 (16-bit ADC, A0)
    → ESP32 (sampling + framing) → USB serial (CSV, 921600 baud) → PC
```

The AD8232 is an ECG-oriented instrumentation amplifier (stock passband
approximately 0.5–40 Hz), used here off-label for EMG. This is a known,
acknowledged limitation (§6): true EMG spectral content spans roughly
20–450 Hz, so what this system captures is the low-frequency envelope of
muscle activity rather than its full spectral detail. It still carries
enough information to separate the vocabulary used in this study (§5), but
the front-end is a stated ceiling on how much finer distinctions the system
could ever make without hardware revision.

### 3.2 Firmware architecture

The firmware (ESP32, Arduino core) makes several deliberate design choices,
each addressing a specific measured problem rather than a hypothetical one:

1. **Interrupt-paced sampling, not polling.** The ADS1115 is configured for
   continuous conversion at its maximum rate (860 SPS) with the comparator
   queue set to assert after every conversion, turning its `ALRT` pin into a
   sample-ready strobe. A falling-edge interrupt on this pin notifies a
   dedicated sampler task via a FreeRTOS task notification — this avoids the
   timing jitter of a fixed-delay polling loop and lets the firmware fall
   back cleanly (auto-detected at boot) to a 500 SPS software-polled mode if
   the interrupt wire is absent.
2. **Dual-core separation.** The sampler task runs pinned to core 1 at
   elevated priority; `loop()` (BLE, OLED, serial command handling) runs on
   core 0 and only drains a lock-free ring buffer. This is why BLE and the
   OLED display can stay active without stealing ADC samples.
3. **Direct register control of the ADS1115**, rather than a vendor
   convenience library, because the conversion-ready interrupt trick
   requires exact control of the threshold registers (`lo_thresh` MSB = 0,
   `hi_thresh` MSB = 1 turns `ALRT` into a strobe per the datasheet), and the
   library API in question changed incompatibly between versions.
4. **A cached I2C pointer register.** Because the ADS1115 retains its
   internal register pointer between transactions, a steady-state sample
   read is a single I2C read transaction rather than a write-then-read,
   halving bus traffic in the sampling path.
5. **The OLED display lives on a second I2C peripheral (`Wire1`)**, not the
   ADC's bus. A full 1 KB SSD1306 framebuffer push blocks I2C for roughly
   25 ms; on a shared bus that costs on the order of 21 EMG samples per
   refresh. Physical isolation removes this contention entirely.
6. **Microsecond, not millisecond, timestamps.** At 860 Hz the sample period
   is 1.16 ms; millisecond resolution cannot represent inter-sample timing
   at that rate.
7. **BLE carries a 20 Hz status/preview packet, not the raw stream** — BLE
   throughput cannot sustain 860 SPS, and forcing it would back up and
   distort timing. The raw stream goes over USB serial at 921600 baud, sized
   to keep up with the CSV line rate at 860 Hz.

### 3.3 Measured timing quality

Across all 50 recordings in the dataset used for this study (Table 1), the
firmware sustained a mean sampling rate of 860.93 Hz (configured target: 860)
with a mean inter-sample jitter (σ of Δt) of **2.8 µs**, ranging 1.6–4.7 µs
across recordings. All recordings ran in hardware-interrupt-paced mode
(`rdy_irq`), not the polling fallback.

**Table 1. Acquisition timing, aggregated over 50 recordings (5 words × 10
reps, subject S01).**

| Metric | Value |
|---|---|
| Configured sampling rate | 860 Hz |
| Measured mean sampling rate | 860.93 Hz |
| Mean inter-sample jitter (σ of Δt) | 2.8 µs (range 1.6–4.7 µs) |
| Samples per 2.0 s recording | 1722.7 mean (range 1722–1725) |
| Sampling mode | 100% hardware interrupt-paced (`rdy_irq`) |

### 3.4 Data acquisition protocol

Recordings were collected with `collect_emg.py`, which implements a fixed
protocol per trial: a 3-2-1 second countdown ("Prepare in 3… 2… 1…"),
immediately followed by a cue ("RECORDING — articulate now!") coincident with
the start of a 2.0 s capture window. Five classes were recorded — four words
(`hello`, `help`, `no`, `yes`) and an explicit `rest` class (the subject
remains still/silent) — 10 repetitions each, all from a single subject (S01)
in a single session, yielding 50 total recordings. A `rest` class was
included deliberately: without one, a classifier has no way to represent "no
word was spoken" and will confidently mislabel idle activity.

### 3.5 Signal processing

Each recording is processed with a fixed filter chain, applied identically
at training and inference time via a single shared code path
(`ml.refined.utterance_features.preprocess`):

1. DC-offset removal (subtract the recording's own mean).
2. A 50 Hz IIR notch filter (Q = 30) for powerline interference.
3. A 4th-order Butterworth bandpass, 10–200 Hz, zero-phase (`filtfilt`).
4. A linear envelope: full-wave rectification followed by a 2nd-order,
   8 Hz Butterworth low-pass.

### 3.6 Feature engineering — utterance-level, not window-level

The central methodological choice in this work is treating **one recording
as one classification sample**, rather than the more conventional approach
of sliding a fixed window across the recording and labelling every window
with the recording's class (§4 shows why this choice matters empirically). A
19-dimensional feature vector is computed per utterance:

**Table 2. Utterance-level feature set (19 features, single channel).**

| Group | Features | Rationale |
|---|---|---|
| Time-domain amplitude | RMS, MAV, waveform length, ZCR, SSC | Standard EMG amplitude/complexity descriptors |
| Envelope amplitude | mean, max, std, peakiness (max/p90), integrated EMG | Overall energy and how "spiky" vs. "sustained" the activity is |
| Envelope shape / dynamics | active fraction, active duration, burst count, temporal centroid, peak time, skew | Capture the *shape* of articulation over time — e.g. burst count acts as a rough syllable-count proxy |
| Spectral | mean frequency, median frequency, spectral entropy | Computed on the active portion of the signal where possible |

Burst detection uses a robust threshold (median + 3×MAD of the envelope),
with bursts closer than 30 ms merged to avoid over-counting noise as
separate events.

### 3.7 Classification and model selection

Three candidate classifiers were compared under identical evaluation
conditions (§4): a linear discriminant analysis model, a support-vector
machine (RBF kernel, C = 5) on standardized features, and a random forest
(400 trees). Model selection used leave-one-recording-out cross-validated
accuracy as the selection criterion; the SVM was retained as the reported
model, though all three reached the same accuracy on this dataset (§5).

---

## 4. Why utterance-level, not sliding-window: an ablation

An earlier version of this system's pipeline used the conventional
sliding-window approach: 256 ms windows, 50% overlap, each window inheriting
its parent recording's label. Cross-validated (grouped by recording, so no
window from a given utterance appeared in both train and test folds)
accuracy for that pipeline was **47.7%** (random forest; SVM was worse, at
37%) on the same 5-class vocabulary, against a chance level of 20%.

The reason is straightforward in hindsight: most windows inside a 2 s
recording are silence — before and after the actual articulation — so the
sliding-window classifier is trained on a large fraction of mislabelled data
(windows genuinely indistinguishable from `rest` but labelled with whatever
word the recording happened to be). We further verified this directly: taking
a real, correctly-classified `yes` recording and truncating it to increasingly
short prefixes, the trained utterance-level classifier's prediction flips
from `yes` (79% confidence, full 2.0 s) to `rest` (46–49% confidence) once
the available signal drops to roughly half a second or less — a
plausible-looking but wrong answer, not an obviously-broken one. This
finding directly informed a defensive fix in the live-inference tooling
(§7.3): capture robustness (not silently truncating a window) matters as much
as the classifier itself.

Reframing the problem so that **one utterance is one sample**, and describing
that whole utterance with shape/energy/spectral features rather than
classifying arbitrary sub-windows of it, removes this mislabelling entirely
by construction. This is the single largest driver of the accuracy
difference reported in §5 — larger than any of the three classifiers'
individual differences from one another.

---

## 5. Experimental evaluation

### 5.1 Protocol

All reported metrics are **out-of-fold**: no recording is ever scored by a
model that trained on it. Two independent checks were run:

1. **Leave-one-recording-out (LOO):** each of the 50 recordings held out in
   turn, model trained on the remaining 49, predicted, aggregated into a
   single out-of-fold confusion matrix.
2. **Repeated stratified 5-fold cross-validation, 10 repeats** (different
   random fold assignments each repeat) — a check against a favorable LOO
   split.

We additionally ran a **temporal split** as a targeted check against a
specific confound: the 10 repetitions of each word were recorded in blocks
(all `hello` reps together, then all `help` reps, etc.), so a model could in
principle be learning session-time drift (electrode impedance change, subject
fatigue) rather than the words themselves. We trained on repetitions 1–6 and
tested on repetitions 7–10 (and the reverse), which is a strictly harder,
more adversarial split with respect to that specific confound than random
K-fold.

### 5.2 Results

**Table 3. Classification accuracy, all values out-of-fold. 5 classes,
chance level 20%.**

| Evaluation | SVM (RBF) | Random Forest | LDA |
|---|---|---|---|
| Leave-one-recording-out | **100.0%** | 100.0% | 100.0% |
| Repeated 5-fold × 10 | **100.0% ± 0.0%** | 100.0% ± 0.0% | 100.0% ± 0.0% |
| Temporal split (train reps 1–6 → test reps 7–10) | 100.0% | — | — |
| Temporal split (reverse) | 100.0% | — | — |

For reference, the earlier sliding-window pipeline on the same underlying
recordings reached 47.7% (grouped cross-validation, random forest) — see §4.

The LOO confusion matrix is a perfect diagonal (50/50): every recording,
held out, is classified correctly by a model that never saw it. The temporal
split holding at 100% in both directions is evidence against the accuracy
being an artifact of session-time drift correlating with recording order,
though it cannot rule out subtler within-session confounds.

### 5.3 Qualitative analysis

Inspecting the amplitude envelopes directly (Figure 1, described here since
this is a plain-text draft — see `refined_model/envelopes.png` in the
project repository) shows why the classes separate so cleanly: each word
produces a visually distinct, repeatable envelope shape across all 10
repetitions. `hello` shows two temporally separated bumps (consistent with
its two syllables); `help` shows one broad, internally-structured sustained
hump; `no` shows one medium hump arriving comparatively late in the window;
`yes` shows one tall, narrow spike; `rest` is flat. This is consistent with
burst count and envelope-shape features (Table 2) carrying much of the
discriminative signal, rather than fine spectral detail — which is expected
given the front-end's ECG-band filtering (§3.1, §6).

### 5.4 Live inference verification

Beyond offline cross-validation, the trained model was verified through a
FastAPI backend serving real (not synthetic) recordings end-to-end through
the same feature-extraction code path used in training, confirmed correct
on representative examples from each class with realistic (73–82%, not
saturated) confidence scores — consistent with genuine model uncertainty
rather than an evaluation artifact.

---

## 6. Limitations

Stated plainly, without softening:

- **Single subject.** All data is from one individual (S01), one session.
  Zero evidence exists yet on cross-subject generalization.
- **Single session, single day.** No evidence on within-subject robustness
  to electrode re-adhesion or day-to-day physiological/impedance variation.
  This is arguably the most important open gap and is the first thing the
  roadmap (§8, Phase 1) addresses.
- **Single channel.** No spatial information; cannot capture any
  left/right or multi-site articulation pattern.
- **Small, closed vocabulary (5 classes, one of which is silence).** Not
  open-vocabulary, not continuous speech.
- **ECG-band front-end.** The AD8232's stock filtering attenuates the
  20–450 Hz band where EMG carries most of its information; what this system
  reads is envelope-dominated, not full-spectrum EMG.
- **Controlled recording protocol.** Fixed countdown, fixed 2.0 s window,
  single sitting. A perfect separability result under these conditions is a
  real, honestly-measured signal that the approach works in principle — it
  is not evidence of robustness to uncontrolled, real-world conditions.
- **Live/streaming inference has different failure modes than offline
  classification.** During this work we found and fixed a capture-robustness
  bug where slow GUI rendering could silently truncate a live capture,
  producing a plausible-but-wrong "rest" prediction (§4, §7.3). This is now
  mitigated but underscores that offline accuracy numbers do not
  automatically transfer to a live system without separate engineering care.

We report the 100% LOO figure because it is real and correctly measured, not
because it should be read as "solved." It is best read as: *the
utterance-level approach is sound and the hardware chain is clean enough
that, under controlled single-subject conditions, a small vocabulary is
essentially perfectly separable* — a strong feasibility result, and a
foundation to build the harder cross-subject, cross-session evaluation on
top of, not a substitute for it.

---

## 7. Proposed extension: bilateral 6-electrode architecture

Not yet built; described here as a concrete, engineered next step (full
detail in the project's PRD, `docs/PRD_bilateral_upgrade_and_roadmap.md`).

The plan mirrors the existing (already-debugged) right-side electrode
placement onto the left side of the face: a second AD8232 front-end reading
the left masseter, bringing the system to 6 electrodes total (2 signal + 1
bone-placed reference, per side) and 2 EMG channels. A key engineering
decision is documented explicitly because a naive implementation would
silently violate this project's own stated acquisition principle (that a
sampling-rate mismatch destroys accuracy invisibly): the ADS1115 is a single
ADC behind a multiplexer and cannot sample two channels simultaneously at
full rate. Time-multiplexing a single ADS1115 between two inputs would halve
the effective per-channel rate to ~430 SPS; the recommended path instead adds
a second ADS1115 at I2C address `0x49` on the same dedicated bus, preserving
860 SPS on both channels independently, at a marginal hardware cost of one
additional \$3–5 ADC breakout.

Expected (not yet measured) benefits: genuine spatial/bilateral information
if jaw articulation is measurably asymmetric for some words; redundancy
against a single bad electrode; a larger, richer feature space including
cross-channel features (inter-channel correlation, left/right amplitude
ratio, inter-channel onset-time difference). None of this is claimed as
result — it is stated as hypothesis, to be tested once built.

---

## 8. Roadmap: toward a pretrained, transferable model

### 8.1 The gap
The current model is retrained from scratch per subject from 50 recordings.
That does not scale to being a usable tool, and it is the direct target of
this roadmap.

### 8.2 Staged plan
1. **Within-subject, multi-session robustness** — quantify (not assume)
   day-to-day/re-adhesion drift on the existing subject before adding
   complexity.
2. **Multi-subject corpus construction** — targeting a scale comparable to
   published EMG-speech corpora (e.g. EMG-UKA's 8 speakers; §2), under a
   standardized, consented protocol.
3. **Calibration-based transfer learning** — train a base representation on
   the pooled corpus; a new subject adapts to it with a small number of
   calibration repetitions (target ≤10/word) rather than a full from-scratch
   training run, with a stated accuracy bar (≥80% on the core vocabulary)
   as the milestone that actually defines "pretrained" success.
4. **Cautious external-corpus alignment** — evaluate whether corpora such as
   EMG-UKA, EMG-PIT, or the Gaddy & Klein facial-EMG release could
   contribute to pretraining a shared representation, given they use
   different electrode montages and channel counts than this system.

### 8.3 A lesson already learned, applied forward
This roadmap's caution around external data is not abstract. An earlier
iteration of this project trained a classifier on NinaPro DB1 — a
forearm/hand-gesture EMG dataset — under the assumption that "EMG is EMG."
It is not: NinaPro's electrodes sit on the forearm and its labels are hand
movements, a different muscle group and a different signal entirely from
jaw articulation, and a model trained on it could never have recognized a
silently spoken word (documented in the project's own
`docs/CURRENT_SYSTEM_AUDIT.md`). Any future use of external EMG data for
pretraining is scoped, in this roadmap, to facial/articulatory EMG corpora
specifically, and is treated as a transfer-learning experiment to be
validated against this project's own held-out data — not assumed to work
because the sensor modality name matches.

---

## 9. Ethical considerations

This system targets, as an eventual use case, individuals who are mute or
have severe speech impairment — a population for whom communication
technology has real stakes. Accordingly: any future data collection beyond
the current single-consenting-subject dataset requires informed consent
specific to biosignal data; the project makes no medical or clinical claims
and is not a certified medical device; recorded EMG data is treated as
sensitive personal data and is not to be shared or published without
explicit subject consent (this includes the current S01 dataset).

---

## 10. Conclusion

We built and characterized a complete, low-cost sEMG acquisition and
classification pipeline for silent-speech word recognition, with firmware
timing verified to 860.93 Hz mean rate and 2.8 µs mean jitter across 50
recordings, and showed that reframing classification at the utterance level
rather than the sliding-window level is the primary lever that took honest
cross-validated accuracy from 47.7% to 100% on a 5-word, single-subject
vocabulary. We reported every limitation of that result alongside it, and
laid out a concrete hardware extension (bilateral 6-electrode capture) and a
staged roadmap toward a genuinely subject-transferable, pretrained model —
informed directly by a domain-mismatch mistake this same project made and
corrected earlier in its history. The next reported number that matters is
not another single-subject accuracy figure, but the first cross-day and
cross-subject measurements this roadmap is designed to produce.

---

## References

1. Schultz, T., & Wand, M. (2010). Modeling coarticulation in EMG-based
   continuous speech recognition. *Speech Communication*, 52(4), 341–353.
2. Wand, M., & Janke, M. (2014). The EMG-UKA Corpus for Electromyographic
   Speech Processing. *Proc. Interspeech 2014*.
3. Janke, M., & Diener, L. (2017). EMG-to-Speech: Direct Generation of
   Speech From Facial Electromyographic Signals. *IEEE/ACM Transactions on
   Audio, Speech, and Language Processing*, 25(12).
4. Gaddy, D., & Klein, D. (2020). Digital Voicing of Silent Speech. *Proc.
   EMNLP 2020*. https://aclanthology.org/2020.emnlp-main.445/
5. Gaddy, D., & Klein, D. (2021). An Improved Model for Voicing Silent
   Speech. *Proc. ACL 2021 (Short Papers)*.
   https://aclanthology.org/2021.acl-short.23/

---

## Appendix A — Reproducibility

**Hardware:** ESP32 DevKit V1; ADS1115 (I2C `0x48`); AD8232 (SparkFun,
stock ECG filtering); SSD1306 128×64 OLED (`0x3C`, secondary I2C bus).
Signal chain gain: PGA index 1 (±4.096 V, 125.0 µV/LSB).

**Software / versions:** Python 3.13, numpy 2.3.3, scipy 1.17.1,
scikit-learn 1.9.0, pandas 3.0.5. Firmware: Arduino core for ESP32,
`esp32:esp32:esp32` FQBN with `PartitionScheme=min_spiffs` (required — the
default 1.2 MB app partition cannot fit BLE + display libraries together).

**Exact commands:**
```bash
# firmware
.\tools\asv.ps1 build
.\tools\asv.ps1 flash -Port COM3
python tools/asv_serial.py --port COM3 --cmd t --seconds 10   # self-test

# data collection (the protocol described in §3.4)
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 10 --port COM3
python ml/acquisition/validate_dataset.py

# training + evaluation (produces the numbers in Table 3)
python ml/refined/train_refined.py --data-dir datasets/custom_silent_speech/raw --out refined_model

# unit tests
python -m pytest tests/ -q
```

**Repository structure** (abridged): `firmware_arduino/ASV_Firmware/` —
firmware; `ml/acquisition/` — capture + QA; `ml/refined/` — utterance-level
feature extraction and training (this paper's pipeline);
`ml/refined/utterance_features.py` — the 19-feature extractor (Table 2);
`refined_model/` — trained artifacts + evaluation JSON with the exact
numbers in Table 3; `datasets/custom_silent_speech/raw/S01/` — the dataset
described in §3.4; `docs/PRD_bilateral_upgrade_and_roadmap.md` — the
extension and roadmap described in §7–8.

**Data availability:** The S01 dataset used in this study contains
biosignal data from a single consenting individual and is not publicly
released with this draft; see §9.
