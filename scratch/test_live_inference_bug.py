import os
import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.preprocessing.pipeline import ASVPreprocessor
from ml.utils.filters import apply_standard_emg_filter
import joblib

def test_replay():
    # Load model and preprocessor
    demo_model_dir = settings.MODELS_DIR / "demo_hello_rest"
    clf = joblib.load(demo_model_dir / "classifier.pkl")
    le = joblib.load(demo_model_dir / "label_encoder.pkl")
    prep = ASVPreprocessor.load(demo_model_dir / "preprocessor.pkl")
    
    print(f"Classes: {le.classes_}")

    # Pick a rest file and a hello file
    rest_file = list((settings.RAW_DATA_DIR / "S01/rest").glob("*.csv"))[0]
    hello_file = list((settings.RAW_DATA_DIR / "S01/hello").glob("*.csv"))[0]
    
    def process_file(file_path, label):
        print(f"\nProcessing {label} file: {file_path.name}")
        df = pd.read_csv(file_path)
        emg_cols = [c for c in df.columns if c.startswith("ch") or c.startswith("channel_")]
        raw_data = df[emg_cols].values
        if raw_data.ndim == 1:
            raw_data = raw_data.reshape(-1, 1)
            
        print(f"Raw data shape: {raw_data.shape}")
        
        # Method 1: Offline (Training) style
        print("\n--- Offline Method ---")
        offline_feats = prep.transform(df)
        if not offline_feats.empty:
            X_off = offline_feats[prep.feature_names].values
            preds = clf.predict(X_off)
            prob_off = clf.predict_proba(X_off)
            for i, p in enumerate(preds):
                pred_label = le.inverse_transform([p])[0]
                print(f"Win {i} offline pred: {pred_label} (Probs: {prob_off[i]})")
        
        # Method 3: Live style with larger buffer for filtering
        print("\n--- Live Method (Large Filter Buffer) ---")
        window_size = settings.WINDOW_SIZE
        step_size = settings.STEP_SIZE
        buffer_size = 2000 # Keep last 2000 samples for filtering
        for i, start in enumerate(range(0, len(raw_data) - window_size + 1, step_size)):
            buf_start = max(0, start + window_size - buffer_size)
            large_window = raw_data[buf_start : start + window_size]
            
            # Apply filter on large window
            filtered = apply_standard_emg_filter(
                large_window,
                fs=settings.SAMPLING_RATE_HZ,
                notch_freq=settings.NOTCH_FREQ_HZ,
                lowcut=settings.BANDPASS_LOW_HZ,
                highcut=settings.BANDPASS_HIGH_HZ
            )
            # Extract the actual window (last 128 samples)
            actual_window = filtered[-window_size:]
            
            # Feature extraction
            feat_dict = prep.feature_extractor.extract_features_vectorized(actual_window, include_frequency=True)
            flat, _ = prep.feature_extractor.flatten_features(feat_dict)
            feat_vector = prep.scaler.transform([flat])[0]
            
            pred_idx = clf.predict([feat_vector])[0]
            prob_live = clf.predict_proba([feat_vector])[0]
            pred_label = le.inverse_transform([pred_idx])[0]
            print(f"Win {i} live pred: {pred_label} (Probs: {prob_live})")

    process_file(rest_file, "REST")
    process_file(hello_file, "HELLO")

if __name__ == "__main__":
    test_replay()
