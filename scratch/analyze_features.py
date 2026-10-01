import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.preprocessing.pipeline import ASVPreprocessor
import joblib

def analyze_features():
    demo_model_dir = settings.MODELS_DIR / "demo_hello_rest"
    prep = ASVPreprocessor.load(demo_model_dir / "preprocessor.pkl")
    clf = joblib.load(demo_model_dir / "classifier.pkl")
    
    # Load one REST and one HELLO
    rest_file = list((settings.RAW_DATA_DIR / "S01/rest").glob("*.csv"))[0]
    hello_file = list((settings.RAW_DATA_DIR / "S01/hello").glob("*.csv"))[0]
    
    def get_feats(f):
        df = pd.read_csv(f)
        emg_cols = [c for c in df.columns if c.startswith("ch") or c.startswith("channel_")]
        raw = df[emg_cols].values
        
        # Segment offline style
        window_size = settings.WINDOW_SIZE
        step_size = settings.STEP_SIZE
        
        from ml.utils.filters import apply_standard_emg_filter
        filtered = apply_standard_emg_filter(
            raw,
            fs=settings.SAMPLING_RATE_HZ,
            notch_freq=settings.NOTCH_FREQ_HZ,
            lowcut=settings.BANDPASS_LOW_HZ,
            highcut=settings.BANDPASS_HIGH_HZ
        )
        
        feats = []
        raw_rmss = []
        for start in range(0, len(raw) - window_size + 1, step_size):
            window = filtered[start : start + window_size]
            
            raw_rms = float(np.sqrt(np.mean(window**2)))
            raw_rmss.append(raw_rms)
            
            feat_dict = prep.feature_extractor.extract_features_vectorized(window, include_frequency=True)
            flat, _ = prep.feature_extractor.flatten_features(feat_dict)
            scaled = prep.scaler.transform([flat])[0]
            feats.append(scaled)
            
        return np.array(feats), np.array(raw_rmss), prep.feature_names
        
    rest_feats, rest_rms, names = get_feats(rest_file)
    hello_feats, hello_rms, _ = get_feats(hello_file)
    
    print(f"Feature Names: {names}")
    print("\n--- REST ---")
    print(f"Mean Filtered RMS: {np.mean(rest_rms):.2f}")
    print(f"Mean Scaled Features: {np.mean(rest_feats, axis=0)}")
    
    print("\n--- HELLO ---")
    print(f"Mean Filtered RMS: {np.mean(hello_rms):.2f}")
    print(f"Mean Scaled Features: {np.mean(hello_feats, axis=0)}")
    
    print("\nFeature Importances (Random Forest):")
    if hasattr(clf, 'feature_importances_'):
        importances = clf.feature_importances_
        for name, imp in sorted(zip(names, importances), key=lambda x: x[1], reverse=True):
            print(f"{name}: {imp:.4f}")

if __name__ == "__main__":
    analyze_features()
