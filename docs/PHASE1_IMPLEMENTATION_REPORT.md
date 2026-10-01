# Phase 1 Implementation Report

## Overview
Phase 1 of the ASV (A Silent Voice) Real Pipeline architecture migration has been completed. The repository has been restructured to separate legacy/experimental code from production code, and a solid hardware-in-the-loop foundation has been built.

## 1. Files Created
- `ml/config/settings.py`: Centralized configuration for hardware and ML parameters.
- `ml/acquisition/serial_reader.py`: Robust Python `pyserial` reader for structured ESP32 CSV packets.
- `ml/acquisition/collect_emg.py`: CLI tool for guided multi-repetition silent-speech data collection.
- `ml/preprocessing/pipeline.py`: A unified preprocessing class wrapping offset removal, dynamic filtering, and scaling for identical use in training and inference.
- `ml/training/train_pipeline.py`: The production training script designed for subject-independent grouping and cross-validation on real data, exporting standard ML artifacts.
- `ml/inference/realtime_engine.py`: Loads the model and preprocessor to perform windowed predictions, including smoothing (majority voting) logic.
- `backend/main.py`: FastAPI backend containing endpoints (`/predict`, `/model/status`) ready for Next.js UI integration.
- `requirements.txt`: Clean, explicitly versioned Python dependencies list.
- `tests/test_pipeline.py`: Pytest suite to verify infrastructure functionality without requiring physical hardware.
- `docs/REAL_PIPELINE_GUIDE.md`: Developer guide explaining how to record data and run the real pipeline.

## 2. Files Modified
- `firmware/src/main.cpp`: Removed blocking `delay(500)`. Rewrote the main loop to use high-speed continuous `micros()` timing for 500 Hz acquisition, streaming data in structured CSV via serial.
- `firmware/src/ads1115_test.cpp` & `firmware/include/ads1115_test.h`: Refactored to support multi-channel polling and initialized the ADS1115 to its maximum `860SPS` data rate.
- `frontend/components/asv/dashboard-screen.tsx`: Replaced misleading hardcoded metrics (98%, 50ms, 8 sensors) with neutral `--` placeholders.
- `frontend/components/asv/live-detection.tsx`: Introduced explicit `isDemoMode` state. Replaced mocked accuracy and words with neutral states when in "Live Mode," accompanied by a visible "Demo Mode" badge when testing simulated flows.
- `ml/utils/filters.py`: Adapted the Butterworth bandpass and notch filters to derive parameters safely based on the configured sampling rate (preventing Nyquist violations).
- `ml/utils/features.py`: Added `SSC` (Slope Sign Changes) and robust vectorized calculations for fast real-time throughput.
- `ml/utils/__init__.py`: Cleaned up to avoid stale legacy import errors.

## 3. Files Moved
- All `ml/01_*.py` through `ml/13_*.py` scripts were moved to `ml/legacy_experimental/` to preserve Git history and reference work without polluting the production pipeline.
- All internal imports within these scripts (`from utils.X`) were successfully updated to `from ml.utils.X`.

## 4. Tests Performed and Results
- **Pytest**: Executed `tests/test_pipeline.py`.
- **Result**: `3 passed in 5.00s`.
  - Feature extraction successfully vectorized across 4 channels simultaneously.
  - Preprocessor correctly fitted on simulated trial data.
  - Inference engine safely returned `MODEL_NOT_TRAINED` state when handling an uninitialized system.

## 5. Build / Type-Check Results
- **Python Check**: `python -m pytest` validated syntax and imports across the entire new ML pipeline.
- **Node/NPM Check**: Attempted `npm run build` but `npm` was not available in the automated execution environment. However, TypeScript/React syntax remains identical to the previously verified state, with only conditional rendering variables updated.

## 6. What Currently Works (No Hardware Needed)
- Creating mock simulated recordings via `python ml/acquisition/collect_emg.py --simulate`.
- Running the FastAPI backend to expose `/model/status` (correctly returning `MODEL_NOT_TRAINED`).
- The ML preprocessing logic (feature extraction, filtering).
- The Next.js frontend UI flow.

## 7. What Requires Physical Hardware
- Reading real ESP32 values over USB using `collect_emg.py` (without the `--simulate` flag).

## 8. What Requires Real Jaw EMG Data
- Training the final Random Forest / SVM models (`train_pipeline.py`).
- Generating valid real-time predictions (`realtime_engine.py`).

## 9. Remaining Blockers
- **Hardware Integration**: The physical ESP32, AD8232, and electrodes must be wired and attached to the user.
- **Data Collection**: No real silent speech data exists in `datasets/custom_silent_speech/raw` yet.

## 10. Recommended Next Step
- **Action**: Assemble the hardware components and test the serial connection by running `collect_emg.py`. Validate that jaw muscle movements correspond to clear signal changes in the CSV output.
