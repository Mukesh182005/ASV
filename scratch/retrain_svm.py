"""
Retrain the demo model with an SVM (RBF kernel) which draws better
non-linear boundaries than Random Forest for overlapping EMG data.
Also check cross-val accuracy to confirm improvement.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.utils.filters import apply_standard_emg_filter
from ml.utils.features import EMGFeatureExtractor

WINDOW_SIZE = settings.WINDOW_SIZE
STEP_SIZE = settings.STEP_SIZE
extractor = EMGFeatureExtractor(fs=settings.SAMPLING_RATE_HZ)

def get_features(label):
    files = list((settings.RAW_DATA_DIR / f"S01/{label}").glob("*.csv"))
    all_feats = []
    all_labels = []
    for f in files:
        df = pd.read_csv(f)
        ch_col = [c for c in df.columns if c.startswith('ch')][0]
        raw = df[ch_col].values.astype(float)
        filtered = apply_standard_emg_filter(raw, settings.SAMPLING_RATE_HZ)
        for start in range(0, len(filtered) - WINDOW_SIZE + 1, STEP_SIZE):
            window = filtered[start:start + WINDOW_SIZE].reshape(-1, 1)
            feat_dict = extractor.extract_features_vectorized(window, include_frequency=True)
            flat, _ = extractor.flatten_features(feat_dict)
            all_feats.append(flat)
            all_labels.append(label)
    return all_feats, all_labels

print("Extracting features...")
rest_feats, rest_labels = get_features("rest")
hello_feats, hello_labels = get_features("hello")

X = np.array(rest_feats + hello_feats)
y = np.array(rest_labels + hello_labels)

le = LabelEncoder()
y_enc = le.fit_transform(y)
print(f"Label mapping: {dict(zip(le.classes_, le.transform(le.classes_)))}")
print(f"Total samples: {len(X)} ({sum(y=='rest')} REST, {sum(y=='hello')} HELLO)")

# SVM with RBF kernel
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('svm', SVC(kernel='rbf', C=10, gamma='scale', probability=True))
])

# Cross-validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X, y_enc, cv=cv, scoring='accuracy')
print(f"\nSVM Cross-Val Accuracy: {scores.mean()*100:.1f}% ± {scores.std()*100:.1f}%")

# Fit on all data
pipeline.fit(X, y_enc)

# Save model
demo_dir = settings.MODELS_DIR / "demo_hello_rest"
demo_dir.mkdir(exist_ok=True)
joblib.dump(pipeline.named_steps['svm'], demo_dir / "classifier.pkl")
joblib.dump(pipeline.named_steps['scaler'], demo_dir / "scaler.pkl")
joblib.dump(le, demo_dir / "label_encoder.pkl")

# Save feature names
_, feature_names = extractor.flatten_features(
    extractor.extract_features_vectorized(np.zeros((WINDOW_SIZE,1)), include_frequency=True)
)
print(f"Feature names: {feature_names}")
print(f"\nModel saved to {demo_dir}")
print("Done!")
