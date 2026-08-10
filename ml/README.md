# ASV — ML pipeline

Python side of the chain: read EMG off the ESP32, label it, filter it, extract features,
train a classifier, serve predictions.

> **Status: no model has ever been trained here.** `models/` is empty. The acquisition
> layer works and is tested; everything downstream of it is code that has not yet been
> run against real data. Treat accuracy claims with suspicion until you produce one.

---

## Layout

| Path | What it does | State |
|---|---|---|
| `acquisition/serial_reader.py` | Reads the firmware's CSV stream, handles the `s` handshake, parses microsecond timestamps | **Working, tested** |
| `acquisition/collect_emg.py` | Records labelled trials to `datasets/custom_silent_speech/raw/` | **Working** |
| `acquisition/validate_dataset.py` | Per-trial QA: rate, jitter, flatline, saturation, duration | **Working** |
| `config/settings.py` | Sampling rate, filters, window size, vocabulary | **Keep in sync with firmware** |
| `utils/filters.py` | Notch + Butterworth bandpass | Ready, unrun on real data |
| `utils/features.py` | MAV, RMS, ZCR, WL, VAR, STD, mean/median frequency | Ready, unrun on real data |
| `preprocessing/pipeline.py` | Cleaning, normalisation, segmentation | Written for 10-channel NinaPro — **needs adapting to 1 channel** |
| `training/train_pipeline.py` | Random Forest / SVM / KNN | Never executed |
| `inference/realtime_engine.py` | Windowed inference with majority voting | Never executed |

---

## Usage

```powershell
# record 20 trials of one word (firmware handshake is automatic)
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3

# QA everything recorded so far
python ml/acquisition/validate_dataset.py

# tests
python -m pytest tests/ -q
```

---

## Things that will bite you

**Sampling rate must match the firmware.** `settings.SAMPLING_RATE_HZ` is 860 (with the
ADS1115 ALRT wire) or 500 (without). The firmware announces its real rate in the
`# ASV_STREAM` header at the start of every stream, and `collect_emg.py` warns if the
measured rate drifts more than 10%. A silent mismatch between collection and inference
destroys accuracy with no visible error.

**Split by recording block, not randomly.** `train_test_split(X, y, shuffle=True)` puts
overlapping windows from the same utterance in both train and test. That inflates
accuracy dramatically and the number will not survive contact with live data.

**Record a `rest` class.** Without one the classifier has no way to output "no word", and
will confidently label chewing, swallowing and idle noise as speech.

**The preprocessing pipeline assumes NinaPro's shape** — 10 channels at 2000 Hz. Your
hardware gives 1 channel at 860 Hz. Adapt it before the first training run.

**Don't reuse a scaler fit on other data.** Normalisation must be fit on recordings from
your own amplifier and electrode placement.

---

## Data layout

```
datasets/custom_silent_speech/
├── raw/<subject>/<label>/repNNN_<timestamp>.csv       timestamp_us, channel_0
│                        repNNN_<timestamp>_meta.json  rate, jitter, firmware header
├── processed/
├── metadata/
└── splits/
```

Dependencies: `pip install -r ml/requirements.txt`
