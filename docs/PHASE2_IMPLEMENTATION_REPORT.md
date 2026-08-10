# Phase 2 Implementation Report

## Summary

Built the complete real EMG data collection + dataset management + preprocessing + training foundation.

---

## 1. Files Created

| File | Purpose |
|------|---------|
| `ml/config/vocabulary.txt` | Configurable vocabulary (hello, help, yes, no) — editable to add words |
| `ml/acquisition/validate_dataset.py` | Dataset quality validator: checks flatline, NaN, saturation, rate deviations |
| `docs/REAL_DATA_COLLECTION_GUIDE.md` | Complete guide: electrode placement, collection protocol, commands, limitations |

## 2. Files Modified

| File | What Changed |
|------|-------------|
| `ml/config/settings.py` | `NUM_CHANNELS` 4→1 (matches real hardware), vocabulary loaded from file, added `SPLITS_DIR`, bandpass high reduced to 200 Hz |
| `ml/acquisition/serial_reader.py` | Complete rewrite: `parse_line()` method for individual packet parsing, returns numpy arrays, firmware log filtering, malformed packet stats |
| `ml/acquisition/collect_emg.py` | Complete rewrite: saves to `raw/{subject}/{label}/`, per-trial metadata JSON, no hardcoded vocabulary `choices`, configurable channels/baud/rest |
| `ml/preprocessing/pipeline.py` | Added `trial_id` preservation, simulated-data rejection in training mode, `channel_` column support, `PREPROCESSING_VERSION`, richer saved config |
| `ml/training/train_pipeline.py` | Complete rewrite: recursive `raw/{subject}/{label}/` discovery, metadata JSON parsing, simulated file skipping, feature_schema.json + metadata.json + evaluation.json output, GroupKFold/StratifiedKFold fallback, class balance reporting |
| `ml/inference/realtime_engine.py` | Unchanged (still compatible — loads classifier.pkl + preprocessor.pkl + label_encoder.pkl) |
| `ml/utils/features.py` | Unchanged (already correct for 1+ channels) |
| `ml/utils/filters.py` | Unchanged (already has Nyquist safety) |
| `firmware/src/main.cpp` | `NUM_CHANNELS` 4→1 (matches hardware: only A0 has AD8232), added sample counter |
| `tests/test_pipeline.py` | Expanded from 3 → 23 tests covering serial parsing, features, filters, preprocessing, inference, dataset validation |

## 3. Existing Files Reused (No Changes Needed)

- `ml/utils/features.py` — Feature extraction already supports 1+ channels
- `ml/utils/filters.py` — Filtering already has Nyquist protection
- `ml/inference/realtime_engine.py` — Inference engine already compatible with new artifact format
- `backend/main.py` — Backend already returns `MODEL_NOT_TRAINED` correctly
- `firmware/src/ads1115_test.cpp` — ADS1115 driver unchanged
- All frontend files — Unchanged (Demo/Live mode toggle from Phase 1 preserved)

## 4. Commands Executed

| Command | Result |
|---------|--------|
| `python -c "from ml.config import settings; ..."` | ✓ CHANNELS=1, VOCAB=[hello,help,yes,no], WINDOW=128, STEP=64 |
| `python -m pytest tests/test_pipeline.py -v` | ✓ **23 passed, 0 failed** (2.57s) |
| `python ml/training/train_pipeline.py` | ✓ Correctly reports `INSUFFICIENT_DATA` |
| `python ml/acquisition/validate_dataset.py` | ✓ Correctly reports `No data files found` |
| `python ml/acquisition/collect_emg.py --help` | ✓ Shows all CLI options |
| `python -c "from backend.main import app"` | ✓ Backend loads, reports `MODEL_NOT_TRAINED` |

## 5. Tests: 23 Passed, 0 Failed

| Test Category | Tests | Status |
|--------------|-------|--------|
| Serial packet parsing (valid, malformed, firmware logs, multi-channel, extra channels) | 7 | ✓ All pass |
| Feature extraction (1-ch, 4-ch, deterministic ordering) | 3 | ✓ All pass |
| Filtering (bandpass Nyquist, notch skip, full chain) | 3 | ✓ All pass |
| Preprocessing (fit, simulated rejection, segmentation, short skip, save/load, trial_id) | 6 | ✓ All pass |
| Inference engine (not-trained state) | 1 | ✓ Pass |
| Dataset validation (empty, good, flatline) | 3 | ✓ All pass |

## 6. Key Commands Reference

```powershell
# Collect data (real hardware)
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3

# Collect data (simulate for testing)
python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 5 --simulate

# Validate dataset quality
python ml/acquisition/validate_dataset.py

# Train model
python ml/training/train_pipeline.py

# Run tests
python -m pytest tests/test_pipeline.py -v
```

## 7. Model Artifact Location

After training: `ml/models/latest/` containing:
- `classifier.pkl`, `preprocessor.pkl`, `label_encoder.pkl`
- `feature_schema.json`, `metadata.json`, `evaluation.json`

## 8. What Is Ready Now

- ✓ Serial reader with packet parsing and malformed stats
- ✓ CLI data collector with per-trial CSV + metadata JSON
- ✓ Dataset directory structure: `raw/{subject}/{label}/`
- ✓ Dataset validator (flatline, NaN, saturation, rate deviation)
- ✓ Preprocessing: filter → segment → extract features (1+ channels)
- ✓ Training pipeline with GroupKFold, confusion matrix, evaluation JSON
- ✓ Inference engine with `MODEL_NOT_TRAINED` safety
- ✓ Backend API
- ✓ 23 passing tests
- ✓ Configurable vocabulary via `ml/config/vocabulary.txt`
- ✓ Firmware sending 1 real channel (A0) at 500 Hz

## 9. What Still Requires Physical Hardware

- ⚠ Collecting real jaw/neck EMG data (electrodes must be placed on facial muscles)
- ⚠ Verifying the actual serial stream format with `python ml/acquisition/collect_emg.py --port COMx --subject TEST --label hello --reps 1`
- ⚠ Verifying the achievable sampling rate (500 Hz target, may vary)
- ⚠ Training a real model (requires data from at least 2 word labels)

## 10. Exact Next Physical Experiment

1. **Attach electrodes to jaw muscles** (masseter/submental) — NOT forearm
2. **Connect ESP32 via USB**, identify COM port
3. **Collect data** for each word:
   ```powershell
   python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20 --port COM3
   python ml/acquisition/collect_emg.py --subject S01 --label help  --reps 20 --port COM3
   python ml/acquisition/collect_emg.py --subject S01 --label yes   --reps 20 --port COM3
   python ml/acquisition/collect_emg.py --subject S01 --label no    --reps 20 --port COM3
   ```
4. **Validate**: `python ml/acquisition/validate_dataset.py`
5. **Train**: `python ml/training/train_pipeline.py`
6. **Review**: Check `ml/models/latest/evaluation.json`
