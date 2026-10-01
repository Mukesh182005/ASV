# ASV — Real Data Collection Guide

## Overview

This guide explains how to physically collect the ASV silent-speech EMG dataset using the existing hardware (ESP32 + ADS1115 + AD8232 + surface electrodes).

> **IMPORTANT DISTINCTION:**
> - The **forearm clench/relax test** was hardware validation only. It proved the acquisition chain works. It is NOT silent-speech data.
> - The **real ASV dataset** requires jaw/neck surface EMG electrodes and silently articulated words.

---

## A. Hardware Setup

### Components
| Component       | Role                                      |
|-----------------|-------------------------------------------|
| ESP32 DevKit V1 | Microcontroller + USB serial              |
| ADS1115         | 16-bit ADC, I2C addr 0x48                 |
| AD8232          | EMG analog front-end                      |
| SSD1306 OLED    | Status display (I2C addr 0x3C)            |
| Surface electrodes | Acquire jaw/neck muscle signals         |
| USB cable       | ESP32 to PC (CP2102 driver required)      |

### Wiring (already validated)
```
AD8232 OUTPUT  → ADS1115 A0
ADS1115 SDA    → ESP32 GPIO 21
ADS1115 SCL    → ESP32 GPIO 22
ADS1115 ADDR   → GND (address 0x48)
ADS1115 VDD    → 3.3V
SSD1306 SDA    → ESP32 GPIO 21
SSD1306 SCL    → ESP32 GPIO 22
SSD1306 VDD    → 3.3V
All GND        → Common GND
```

### Firmware
The ESP32 firmware in `firmware/src/main.cpp` streams structured CSV at 500 Hz:
```
timestamp_ms,adc_value
```
One channel (A0 = AD8232 output). Baud rate: 115200.

---

## B. Serial Connection

1. Connect the ESP32 via USB.
2. Install the CP2102 driver if needed.
3. Identify the COM port:
   - Windows: Device Manager → Ports (COM & LPT)
   - Or run: `python -c "from ml.acquisition.serial_reader import EMGSerialReader; print(EMGSerialReader.list_ports())"`

---

## C. Electrode Placement for Silent Speech

### Target muscles
For silent speech recognition, place surface electrodes on the **jaw/facial muscles**:

1. **Masseter** — side of jaw (clenching muscle)
2. **Anterior belly of digastric** — under the chin (jaw opening)
3. **Submental region** — beneath the chin

### Electrode positions (3-electrode AD8232 setup)
- **RA (Right Arm / positive)** → Primary muscle site (e.g., right masseter)
- **LA (Left Arm / negative)** → Secondary site or nearby reference
- **RL (Right Leg / ground/reference)** → Bony prominence (e.g., behind the ear, mastoid process)

### Skin preparation
1. Clean electrode sites with isopropyl alcohol
2. Lightly abrade if using dry electrodes
3. Apply adhesive gel electrodes firmly
4. Ensure good skin contact (low impedance)

---

## D. Vocabulary

Initial recommended vocabulary (configurable in `ml/config/vocabulary.txt`):

| Word  | Description              |
|-------|--------------------------|
| hello | Common greeting          |
| help  | Emergency/assistance     |
| yes   | Affirmative              |
| no    | Negative                 |

You can add more words later by editing `ml/config/vocabulary.txt`.

---

## E. Starting the Collector

```powershell
# From the repository root:
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
```

### Required arguments
| Argument    | Description                               |
|-------------|-------------------------------------------|
| `--subject` | Subject ID (e.g., S01, S02)               |
| `--label`   | Word label (e.g., hello, yes)             |

### Optional arguments
| Argument      | Default | Description                              |
|---------------|---------|------------------------------------------|
| `--reps`      | 20      | Number of repetitions per word           |
| `--duration`  | 2.0     | Recording duration per trial (seconds)   |
| `--port`      | (auto)  | Serial port (e.g., COM3)                 |
| `--baud`      | 115200  | Serial baud rate                         |
| `--channels`  | 1       | Number of ADC channels                   |
| `--rest`      | 3.0     | Rest period between trials (seconds)     |
| `--simulate`  | false   | Use simulated data (testing only)        |

---

## F. Repetition Protocol

For each word:
1. The tool shows a 3-second countdown
2. **RECORDING** — Silently articulate the word (mouth the word without voicing it)
3. Recording lasts 2 seconds (configurable)
4. 3-second rest period
5. Repeat for 20 repetitions

### Recommended session plan
```
Session = 1 word × 20 reps ≈ 3 minutes
Full vocabulary = 4 words × 20 reps ≈ 12 minutes
```

### Per-word collection
```powershell
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
python ml/acquisition/collect_emg.py --subject S01 --label help  --reps 20 --port COM3
python ml/acquisition/collect_emg.py --subject S01 --label yes   --reps 20 --port COM3
python ml/acquisition/collect_emg.py --subject S01 --label no    --reps 20 --port COM3
```

---

## G. Rest Periods

- **Between trials:** 3 seconds (automatic)
- **Between words:** Take a 2–5 minute break
- **Between sessions:** At least 30 minutes

---

## H. Data Storage

Files are saved to:
```
datasets/custom_silent_speech/raw/{subject}/{label}/
    rep001_20260809_143022.csv          ← raw ADC values
    rep001_20260809_143022_meta.json    ← trial metadata
```

### CSV format
```csv
timestamp,channel_0
12345,8192
12347,8210
...
```

### Metadata JSON
```json
{
  "subject": "S01",
  "label": "hello",
  "repetition": 1,
  "n_samples": 1000,
  "duration_sec": 2.0,
  "configured_sampling_rate_hz": 500,
  "actual_sampling_rate_hz": 498.5,
  "num_channels": 1,
  "is_simulated": false
}
```

---

## I. Data Quality Checks

After collecting data, validate it:

```powershell
python ml/acquisition/validate_dataset.py
```

This checks for:
- Empty recordings
- NaN values
- Sampling rate deviations (>15% from expected)
- Flatline signals
- Saturation/clipping
- Timestamp monotonicity
- Recording duration

Output: GOOD / WARNING / INVALID per trial.

### Repeating failed trials
If a trial is marked INVALID, delete it and re-record:
```powershell
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 1 --port COM3
```

---

## J. Training

Once you have data for at least 2 labels:

```powershell
python ml/training/train_pipeline.py
```

This will:
1. Discover all recordings in `datasets/custom_silent_speech/raw/`
2. Filter → segment → extract features
3. Train Random Forest and SVM classifiers
4. Evaluate with GroupKFold cross-validation (grouped by trial to prevent data leakage)
5. Save the best model to `ml/models/asv_model_{timestamp}/`
6. Update `ml/models/latest/` alias

### What if training fails?
- **"INSUFFICIENT_DATA"** — You need more recordings (at least 2 different labels with enough samples)
- **Low accuracy** — Normal for early data. Collect more reps, improve electrode placement

---

## K. Model Artifacts

After successful training:
```
ml/models/latest/
    classifier.pkl          ← trained model
    preprocessor.pkl        ← fitted scaler + config
    label_encoder.pkl       ← label mapping
    feature_schema.json     ← feature names and version
    metadata.json           ← training configuration
    evaluation.json         ← CV accuracy, confusion matrix, F1
```

---

## L. Evaluation

Review `ml/models/latest/evaluation.json` for:
- Cross-validation accuracy
- Per-class precision/recall/F1
- Confusion matrix
- Which CV method was used (GroupKFold vs StratifiedKFold)

---

## M. Current Limitations

1. **Single subject:** If only one subject is recorded, the model cannot claim subject-independent generalization.
2. **Single channel:** Currently using 1 ADC channel (AD8232 → A0). More channels can be added when hardware is expanded.
3. **No real jaw EMG data yet:** The forearm validation test is NOT speech data. Real jaw/neck electrode data must be collected before meaningful speech recognition training.
4. **Small vocabulary:** Starting with 4 words. Can be expanded by editing `ml/config/vocabulary.txt`.

---

## N. Exact Next Physical Experiment

1. **Attach electrodes to jaw muscles** (masseter / submental) instead of the forearm
2. **Connect to the same hardware chain** (AD8232 → ADS1115 A0 → ESP32)
3. **Run the collector** for each word in the vocabulary
4. **Validate** the recordings
5. **Train** the classifier
6. **Evaluate** and iterate
