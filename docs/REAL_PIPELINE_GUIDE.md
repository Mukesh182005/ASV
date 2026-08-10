# ASV Real Pipeline Execution Guide

This guide explains how to use the newly implemented real hardware pipeline for ASV.

## 1. Hardware Setup (Future)
When the physical ESP32, ADS1115, and AD8232 are wired, flash the firmware in `firmware/` via PlatformIO or Arduino IDE.
The firmware samples data at 500 Hz (configurable via `TARGET_SAMPLE_RATE_HZ`) and streams structured CSV over USB Serial.

## 2. Data Collection

To collect real silent-speech EMG data:

1. Connect the ESP32 via USB.
2. Ensure you have installed requirements: `pip install -r requirements.txt`
3. Run the collection script from PowerShell (in the repository root):
   ```powershell
   python ml\acquisition\collect_emg.py --subject SUB01 --word HELLO --reps 5 --duration 2.0
   ```
4. The script will guide you with a countdown for each repetition.
5. Files are saved to `datasets/custom_silent_speech/raw/`.

**Test Mode (No Hardware)**
If you do not have hardware connected, you can run the collector in simulation mode to test the pipeline:
```powershell
python ml\acquisition\collect_emg.py --subject SUB01 --word HELLO --reps 5 --duration 2.0 --simulate
```
*Note: This data is explicitly marked as simulated and should not be used for production training.*

## 3. Training the Model

Once you have recorded a sufficient number of words:

```powershell
python ml\training\train_pipeline.py
```

- This script loads data from `datasets/custom_silent_speech/raw/`.
- It performs filtering, feature extraction, and groups data by subject+repetition to avoid leakage.
- It trains a Random Forest and an SVM, evaluates via GroupKFold cross-validation, and saves the best model.
- Artifacts (model, preprocessor, label encoder) are saved to `ml/models/latest/`.

## 4. Realtime Inference & Backend

To serve predictions (for the Next.js frontend):

```powershell
uvicorn backend.main:app --reload
```

- If a model has been trained, it will load it and return predictions via `POST /predict`.
- If no model is trained, it will safely return `MODEL_NOT_TRAINED`.

## 5. Frontend UI

Start the frontend:
```powershell
cd frontend
npm run dev
```

- The UI features a **Live Mode / Demo Mode** toggle on the Live Detection screen.
- When in "Live Mode", it no longer generates random mock accuracy or words. Instead, it expects real API data (or displays neutral dashes `--` if disconnected).
