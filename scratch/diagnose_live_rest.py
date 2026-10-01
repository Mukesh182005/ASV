import os
import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.acquisition.serial_reader import EMGSerialReader
from ml.preprocessing.pipeline import ASVPreprocessor
import joblib

def print_stats(name, raw_data, feat_vector, pred_label, probs):
    rms = float(np.sqrt(np.mean(raw_data**2)))
    mean_val = float(np.mean(raw_data))
    min_val = float(np.min(raw_data))
    max_val = float(np.max(raw_data))
    print(f"\n--- {name} ---")
    print(f"Raw Mean: {mean_val:.2f} | Raw RMS: {rms:.2f} | Raw Min: {min_val:.2f} | Raw Max: {max_val:.2f}")
    print(f"Feature Vector Mean: {np.mean(feat_vector):.4f} | Var: {np.var(feat_vector):.4f} | Max: {np.max(feat_vector):.4f}")
    print(f"Prediction: {pred_label}")
    print(f"Probabilities: {probs}")

def run_diagnostic():
    demo_model_dir = settings.MODELS_DIR / "demo_hello_rest"
    clf = joblib.load(demo_model_dir / "classifier.pkl")
    le = joblib.load(demo_model_dir / "label_encoder.pkl")
    prep = ASVPreprocessor.load(demo_model_dir / "preprocessor.pkl")
    
    print(f"Label Encoding: {dict(enumerate(le.classes_))}")

    # 1. Evaluate Recorded REST
    rest_file = list((settings.RAW_DATA_DIR / "S01/rest").glob("*.csv"))[0]
    df = pd.read_csv(rest_file)
    emg_cols = [c for c in df.columns if c.startswith("ch") or c.startswith("channel_")]
    rec_rest = df[emg_cols].values.reshape(-1, 1)[:2000] # Use a 2000-sample block
    feat_rec_rest = prep.process_live_window(rec_rest)
    pred_rec_rest = le.inverse_transform([clf.predict([feat_rec_rest])[0]])[0]
    prob_rec_rest = clf.predict_proba([feat_rec_rest])[0]
    print_stats("RECORDED REST", rec_rest[-128:], feat_rec_rest, pred_rec_rest, prob_rec_rest)

    # 2. Evaluate Recorded HELLO
    hello_file = list((settings.RAW_DATA_DIR / "S01/hello").glob("*.csv"))[0]
    df = pd.read_csv(hello_file)
    rec_hello = df[emg_cols].values.reshape(-1, 1)[:2000]
    feat_rec_hello = prep.process_live_window(rec_hello)
    pred_rec_hello = le.inverse_transform([clf.predict([feat_rec_hello])[0]])[0]
    prob_rec_hello = clf.predict_proba([feat_rec_hello])[0]
    print_stats("RECORDED HELLO", rec_hello[-128:], feat_rec_hello, pred_rec_hello, prob_rec_hello)

    # 3. Evaluate Live Signal
    print("\nCapturing 4 seconds of LIVE REST from COM5...")
    reader = EMGSerialReader("COM5", baud_rate=500000, num_channels=1)
    if not reader.connect():
        print("Failed to connect to COM5. Ensure hardware is plugged in.")
        return
        
    result = reader.read_samples(4.0, simulate=False)
    reader.disconnect()
    
    live_data = result["channels"]
    if len(live_data) < 2000:
        print(f"Not enough live data captured: {len(live_data)} samples.")
        return
        
    live_window = live_data[:2000]
    feat_live = prep.process_live_window(live_window)
    pred_live = le.inverse_transform([clf.predict([feat_live])[0]])[0]
    prob_live = clf.predict_proba([feat_live])[0]
    print_stats("LIVE SIGNAL (ASSUMED REST)", live_window[-128:], feat_live, pred_live, prob_live)
    
    print("\n--- Summary ---")
    if pred_live == "hello":
        print("DIAGNOSIS: Live inference incorrectly predicts HELLO.")
        print(f"Comparing recorded REST raw mean ({np.mean(rec_rest[-128:]):.2f}) vs Live raw mean ({np.mean(live_window[-128:]):.2f})")
    else:
        print("DIAGNOSIS: Live inference correctly predicts REST.")

if __name__ == "__main__":
    run_diagnostic()
