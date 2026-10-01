# ASV — "A Silent Voice"
## Project Explanation for Guide Presentation

---

## What is this project?

**ASV (A Silent Voice)** is a low-cost system that reads the electrical
signals from your jaw muscles when you silently mouth a word — without
making any sound — and classifies which word you said.

It is an **assistive technology** project. The eventual goal is to let
people who cannot speak (mute, ALS, post-laryngectomy) communicate by
silently mouthing words, which the system converts to text or speech.

---

## The One-Line Summary

> Stick two electrodes on your jaw → ESP32 reads the muscle signals →
> Python extracts features → ML model predicts the word → word shown on
> OLED display and in the GUI.

---

## Step-by-Step: How It Actually Works

---

### STEP 1 — Hardware: Sensing the Muscle Signal

```
[JAW MUSCLES]
     |
     | (tiny ~mV electrical signal when you mouth a word)
     ↓
[Ag/AgCl Electrodes] — two skin-contact electrodes on the jaw (masseter muscle)
     |
     ↓
[AD8232 Analog Front-End] — amplifies and filters the raw signal
     |                      (originally an ECG chip, reused for EMG)
     ↓
[ADS1115 — 16-bit ADC] — converts analog voltage to a digital number
     |                    samples at exactly 860 times per second (860 Hz)
     ↓
[ESP32 Microcontroller] — collects samples, timestamps each one,
                          sends them over USB serial to the PC
```

**Key hardware choices and WHY:**

| Component | Why this one |
|-----------|-------------|
| AD8232 | Costs ~₹200. Originally for ECG heart monitors. Has built-in amplifier & filter. Off-label use for jaw EMG. |
| ADS1115 | 16-bit resolution. Has an interrupt pin — crucial for timing accuracy. |
| ESP32 | Dual-core. Can run the sampler on one core and Bluetooth/OLED on the other simultaneously. |
| Ag/AgCl electrodes | Standard biomedical electrodes. Low contact impedance. |

**Total hardware cost: under ₹2,000 (~$25 USD)**

---

### STEP 2 — Firmware: Getting Clean, Accurate Timing

The ESP32 runs custom firmware (`ASV_Firmware.ino`) with several deliberate
engineering decisions:

#### Problem: Timing jitter ruins the signal
At 860 Hz, each sample is only **1.16 ms** apart. If the microcontroller
reads samples even 5 ms late, the signal gets distorted. A naive polling
loop (`delay(1)`) cannot achieve this.

#### Solution: Interrupt-paced sampling
The ADS1115 chip has an `ALRT` (alert) pin that goes LOW the instant a new
sample is ready. The firmware wires this to the ESP32 and uses a **hardware
interrupt** — the CPU instantly wakes up and reads the sample the moment
it's ready.

**Measured result:** Mean timing jitter = **2.8 microseconds** across 50
recordings. This is 400× more precise than millisecond-level polling.

#### Other firmware decisions:

| Decision | Problem it solves |
|----------|-------------------|
| **Dual-core split** | Sampler runs on Core 1 (high priority). Bluetooth/OLED on Core 0. Neither blocks the other. |
| **Second I2C bus for OLED** | OLED refresh takes 25 ms and would drop ~21 samples if on the same bus as the ADC. Physical isolation removes this. |
| **Microsecond timestamps** | At 860 Hz, millisecond timestamps cannot distinguish samples. |
| **USB serial at 921600 baud** | Fast enough to keep up with 860 samples/second as CSV lines. |
| **BLE for status only (20 Hz)** | Bluetooth cannot sustain 860 Hz raw data. Only sends health/preview packets. |

---

### STEP 3 — Data Collection: Recording Words

Script: `ml/acquisition/collect_emg.py`

The protocol for every single recording is fixed and identical:

```
"Prepare in 3..."  →  "2..."  →  "1..."  →  "RECORDING — articulate now!"
                                                    │
                                              [2.0 second capture window]
                                              [~1722 samples at 860 Hz]
```

**Dataset collected:**
- 5 classes: `hello`, `help`, `no`, `yes`, `rest` (silence)
- 10 repetitions each = **50 total recordings**
- 1 subject (S01), 1 session, 1 channel
- Each recording saved as a CSV: `timestamp_us, channel_0`

**Why include a `rest` class?**
Without it, when the person is idle, the classifier has no bucket to put
the signal in and will hallucinate a word. A `rest` class gives the model
a "nothing is happening" category.

---

### STEP 4 — Signal Processing: Cleaning the Raw Signal

Script: `ml/refined/utterance_features.py` → `preprocess()`

The raw ADC values are filtered with this exact chain (same at training and
at inference — this is important):

```
Raw ADC counts (integers)
        ↓
[1] DC offset removal    — subtract the recording's own mean (removes baseline drift)
        ↓
[2] 50 Hz IIR notch      — removes powerline interference (mains hum)
        ↓
[3] 10–200 Hz bandpass   — removes very slow drift & very high frequency noise
   (4th-order Butterworth, zero-phase)
        ↓
[4] Linear envelope       — full-wave rectification + 8 Hz low-pass
                           (shows the "shape" of muscle activation over time)
```

The result is a smooth **envelope** that shows *when* and *how much* the
jaw muscles activated during the 2 seconds.

---

### STEP 5 — Feature Extraction: 19 Numbers per Word

Script: `ml/refined/utterance_features.py` → `extract()`

The key insight of this project:

> **One recording = one sample = one 19-dimensional feature vector.**

This is different from the conventional approach (explained below in
"The Big Lesson"). A full 2-second recording is described by **19 numbers**:

| Feature Group | Features | What they capture |
|---------------|----------|-------------------|
| **Time-domain** | RMS, MAV, Waveform Length, ZCR, SSC | Overall amplitude and complexity of the raw signal |
| **Envelope amplitude** | Mean, Max, Std, Peakiness, Integrated EMG | How strong and how "spiky" was the activation |
| **Envelope shape** | Active fraction, Active duration, Burst count, Temporal centroid, Peak time, Skew | The *shape* of articulation over time |
| **Spectral** | Mean frequency, Median frequency, Spectral entropy | Frequency content of the active portion |

**Example intuition for each word:**
- `hello` → 2 bumps in the envelope (2 syllables: "hel-lo")
- `yes` → 1 tall narrow spike
- `no` → 1 medium bump, arriving late in the window
- `rest` → flat — near zero activity
- `help` → 1 broad sustained hump

These shapes are visually distinct and repeatable across all 10 repetitions.

---

### STEP 6 — Machine Learning: Training the Classifier

Script: `ml/refined/train_refined.py`

Three classifiers were compared:
1. **SVM** (Support Vector Machine, RBF kernel, C=5) on standardized features
2. **Random Forest** (400 trees)
3. **LDA** (Linear Discriminant Analysis)

All three achieved identical accuracy on this dataset. The SVM was kept as
the primary model.

**Evaluation method:**
- **Leave-One-Recording-Out (LOO):** Each of the 50 recordings is held out
  one at a time. The model trains on 49, predicts the 1 held-out.
  This is the strictest possible test — the model never sees the test sample.
- **5-fold cross-validation × 10 repeats:** Additional check for stability.
- **Temporal split:** Train on reps 1–6, test on reps 7–10 (and reverse).
  Checks that accuracy isn't from time-of-session drift.

**Results:**

| Evaluation | SVM | Random Forest | LDA |
|------------|-----|---------------|-----|
| Leave-one-recording-out | **100%** | 100% | 100% |
| 5-fold × 10 repeats | **100% ± 0%** | 100% ± 0% | 100% ± 0% |
| Temporal split (both directions) | **100%** | — | — |

Chance level = 20% (5 classes). Previous sliding-window approach = **47.7%**.

---

### STEP 7 — The Big Lesson: Why Utterance-Level Works

#### The old approach (sliding-window) — 47.7% accuracy

```
2-second recording of "yes"
├── window 0–256ms   → labelled "yes" (but this is actually silence before speaking)
├── window 128–384ms → labelled "yes" (still mostly silence)
├── window 256–512ms → labelled "yes" (the actual "yes" happens here)
├── window 384–640ms → labelled "yes" (tail of signal + silence)
└── ...15 more windows, mostly silence, all labelled "yes"
```

**The problem:** Most sub-windows in a 2-second recording are silence. But
they're labelled with the word. So the model is trained on data where
"silence" is labelled as "hello", "yes", etc. It learns nothing useful.

#### The new approach (utterance-level) — 100% accuracy

```
2-second recording of "yes"
    ↓ (one single feature extraction over the whole recording)
[19 numbers describing the whole 2-second shape]
    ↓
One training sample, labelled "yes"
```

The whole recording is described by one feature vector. No mislabelling.
The model sees the full shape of the word.

**This is the single biggest contribution of this project.**

---

### STEP 8 — Inference: Live Real-Time Prediction

Script: `tools/plot_words.py`

```
ESP32 streams samples over COM9 at 860 Hz
        ↓
[Background thread] continuously fills a ring buffer (8 seconds of data)
        ↓
[User presses SPACE]
        ↓
Script takes a 2-second slice from the buffer
(0.4s pre-roll + 1.6s post-roll for reaction time tolerance)
        ↓
Same filter chain → same 19 features → same trained model
        ↓
Predicted word + probability shown in the GUI
        ↓
Predicted word sent over serial to ESP32 → shown on OLED display
```

**Why the background thread?** The v1 implementation read the serial port
inside the GUI animation loop. A slow frame render could stall the serial
read, causing the capture window to contain far fewer samples than expected.
A 2-second window with only 200ms of real data would predict "rest" at
~46% confidence — a plausible-looking but completely wrong answer. The
background thread fixes this.

---

### STEP 9 — Backend API + Web Frontend

**FastAPI Backend** (`backend/main.py`) — runs at `http://localhost:8000`

Exposes REST endpoints:
- `GET /health` — is the server up?
- `GET /model/status` — is the model loaded? what vocabulary?
- `POST /predict_utterance` — send raw ADC samples, get back prediction
- `GET /demo/recording` — replay a real recording end-to-end

**Next.js Frontend** (`frontend/`) — runs at `http://localhost:3000`

A web app that talks to the backend. Shows:
- Bluetooth device connection
- Live EMG dashboard
- Word prediction display
- Settings screen

---

## System Architecture — Full Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        HARDWARE                             │
│                                                             │
│  Jaw Electrodes → AD8232 → ADS1115 → ESP32 → USB Serial    │
│                                         │                   │
│                                         └→ BLE (20Hz)       │
│                                         └→ OLED Display     │
└──────────────────────────┬──────────────────────────────────┘
                           │ COM9, 921600 baud
┌──────────────────────────▼──────────────────────────────────┐
│                        SOFTWARE (PC)                        │
│                                                             │
│  ┌──────────────────────────────────────┐                   │
│  │  plot_words.py (Live GUI)            │                   │
│  │  ├─ Background thread: serial reader │                   │
│  │  ├─ Ring buffer (8 sec of data)      │                   │
│  │  ├─ Matplotlib: live EMG waveform    │                   │
│  │  ├─ SPACE → capture 2s → classify   │                   │
│  │  └─ Probability bar chart per word  │                   │
│  └──────────────────────────────────────┘                   │
│                                                             │
│  ┌──────────────────────────────────────┐                   │
│  │  FastAPI Backend (port 8000)         │                   │
│  │  └─ /predict_utterance API           │                   │
│  │     ├─ preprocess() — filter chain   │                   │
│  │     ├─ extract() — 19 features       │                   │
│  │     └─ SVM classifier → word         │                   │
│  └──────────────────────────────────────┘                   │
│                                                             │
│  ┌──────────────────────────────────────┐                   │
│  │  Next.js Frontend (port 3000)        │                   │
│  │  └─ Web app, talks to backend API    │                   │
│  └──────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Honest Scope — What This Project Does and Does NOT Claim

| What it DOES show | What it does NOT show |
|-------------------|-----------------------|
| ✅ 100% LOO accuracy, 5 classes | ❌ Cross-subject generalization |
| ✅ Clean 860 Hz acquisition, 2.8µs jitter | ❌ Multi-day / re-adhesion robustness |
| ✅ Utterance-level > sliding-window (proven) | ❌ Open vocabulary |
| ✅ Full working pipeline hardware→prediction | ❌ Clinical or medical device claim |
| ✅ Reproducible, all code open | ❌ Works on a different person without retraining |

**The 100% accuracy is real and honestly measured. It means:**
*"Under controlled, single-subject, 5-word conditions, the approach works
perfectly."*
It does NOT mean "the problem is solved."

---

## Key Numbers to Remember

| Metric | Value |
|--------|-------|
| Sampling rate | 860 Hz |
| Timing jitter | **2.8 µs** (σ) |
| Feature vector size | **19 dimensions** |
| Vocabulary | 5 words: hello, help, no, yes, rest |
| Dataset | 50 recordings (5 words × 10 reps), 1 subject |
| Sliding-window accuracy (old) | **47.7%** |
| Utterance-level accuracy (new) | **100%** (LOO, 5-fold, temporal split) |
| Hardware cost | **under ₹2,000 (~$25)** |
| Subjects | 1 (honest limitation — first thing to fix next) |

---

## What Comes Next (Roadmap)

1. **Phase 1 — Multi-day robustness:** Same subject, different days. Does
   accuracy hold when electrodes are re-attached?

2. **Phase 2 — Bilateral hardware:** Add a second AD8232 + second ADS1115
   on the left side of the jaw. 6 electrodes total, 2 channels. Richer
   spatial features.

3. **Phase 3 — Multi-subject corpus:** Collect from multiple people. Target
   comparable to published EMG-speech corpora (~8 speakers).

4. **Phase 4 — Transfer learning:** Train a base model on the pooled corpus.
   New user calibrates with ≤10 repetitions per word rather than full
   retraining.

---

## One Earlier Mistake — Documented Honestly

An earlier version of this project trained the classifier on
**NinaPro DB1** — a dataset of forearm/hand-gesture EMG from able-bodied
subjects. The reasoning was "EMG is EMG."

**It is not.** NinaPro measures forearm muscles during hand movements.
This project measures jaw muscles during silent speech. Completely different
muscle group, completely different signal, completely different task. A model
trained on NinaPro cannot recognize a silently spoken word.

This mistake was caught, documented, and corrected. The lesson now shapes
the entire roadmap's approach to external data: any external EMG corpus
used for pretraining must be **facial/articulatory EMG specifically**, and
must be validated — not assumed to transfer — against this project's own
held-out data.

---

## How to Run — Commands for Demo

```powershell
# Terminal 1: Live GUI (the main demo — needs ESP32 on COM9)
cd j:\scratch\ASV-master\ASV-master
python tools/plot_words.py --port COM9

# Terminal 2: FastAPI backend
cd j:\scratch\ASV-master\ASV-master
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 3: Next.js web frontend
cd j:\scratch\ASV-master\ASV-master\frontend
npm install   # first time only
npm run dev   # opens at http://localhost:3000

# API docs (once backend is up)
# Open browser: http://localhost:8000/docs
```

---

*ASV — A Silent Voice | Feasibility study | Single-subject, single-channel,
5-word vocabulary, 100% utterance-level LOO accuracy.*
