import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.preprocessing.pipeline import ASVPreprocessor
import joblib

def replay_files():
    # Load model and preprocessor
    demo_model_dir = settings.MODELS_DIR / "demo_hello_rest"
    clf = joblib.load(demo_model_dir / "classifier.pkl")
    le = joblib.load(demo_model_dir / "label_encoder.pkl")
    prep = ASVPreprocessor.load(demo_model_dir / "preprocessor.pkl")
    
    print(f"Classes: {le.classes_}")

    def evaluate_class(class_name):
        files = list((settings.RAW_DATA_DIR / f"S01/{class_name}").glob("*.csv"))
        print(f"\n--- Replaying {len(files)} {class_name.upper()} files ---")
        
        correct_windows = 0
        total_windows = 0
        
        window_size = settings.WINDOW_SIZE
        step_size = settings.STEP_SIZE
        buffer_size = 2000
        
        for file_path in files:
            df = pd.read_csv(file_path)
            emg_cols = [c for c in df.columns if c.startswith("ch") or c.startswith("channel_")]
            if not emg_cols:
                continue
            
            raw_data = df[emg_cols].values
            if raw_data.ndim == 1:
                raw_data = raw_data.reshape(-1, 1)
            
            # Simulate real-time continuous feed
            for start in range(0, len(raw_data) - window_size + 1, step_size):
                buf_start = max(0, start + window_size - buffer_size)
                large_window = raw_data[buf_start : start + window_size]
                
                # We use the pipeline's exact live API
                feat_vector = prep.process_live_window(large_window)
                pred_idx = clf.predict([feat_vector])[0]
                pred_label = le.inverse_transform([pred_idx])[0]
                
                total_windows += 1
                if pred_label.lower() == class_name.lower():
                    correct_windows += 1
                    
        print(f"{class_name.upper()} replay: {correct_windows} / {total_windows} correct ({(correct_windows/total_windows*100):.1f}%)")

    evaluate_class("rest")
    evaluate_class("hello")

if __name__ == "__main__":
    replay_files()
