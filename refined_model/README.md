# ASV — Refined model (utterance-level)

**Trained:** 20260811_025650 · **Model:** SVM_rbf · **Subject(s):** S01

## What this is
A silent-speech classifier for the vocabulary: **hello, help, no, rest, yes**.
Unlike the original per-window model, this treats **one recording = one word = one
sample** and describes the whole utterance (energy + envelope shape + spectrum).

## Honest accuracy (out-of-fold — no leakage)
| Metric | Value |
|---|---|
| Leave-One-Recording-Out accuracy | **100.0%** |
| Repeated 5-fold ×10 | 100.0% ± 0.0% |
| Chance level (5 classes) | 20% |

Every number above is measured on recordings the model did **not** train on.
See `confusion_matrix.png` (built from out-of-fold predictions) and `evaluation.json`.

## Scope — read before trusting it
Validated same-subject/same-session (leave-one-recording-out). Re-applying electrodes or a new subject requires re-recording/recalibration.
This is **single-subject**. It has not
been shown to survive re-applying the electrodes or a different person. For a new
session/subject, record a fresh dataset and retrain (`python ml/refined/train_refined.py`).

## Files
- `classifier.pkl`, `label_encoder.pkl` — the trained model
- `feature_schema.json`, `metadata.json`, `evaluation.json`
- `confusion_matrix.png`, `envelopes.png`
- `predict.py` — classify a recording: `python predict.py <recording.csv>`

## How to test
```bash
# classify any collect_emg.py CSV (timestamp_us,channel_0)
python refined_model/predict.py datasets/custom_silent_speech/raw/S01/no/rep005_*.csv
```
Feature extraction is shared with `ml/refined/utterance_features.py`, so training
and inference cannot drift apart.
