"""Diagnose train/live feature mismatch.
Captures 2.5s of live REST signal and compares features to training REST CSVs.
"""
import sys, warnings, glob, numpy as np, joblib
from pathlib import Path
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
from ml.refined.utterance_features import extract, load_counts_csv, FS_DEFAULT, signal_health
from ml.acquisition.serial_reader import EMGSerialReader

PORT = "COM5"

# 1. Load a training REST CSV for comparison
rest_files = sorted(glob.glob('datasets/custom_silent_speech/raw/S01/rest/*.csv'))
train_counts = load_counts_csv(rest_files[0])
train_feats = extract(train_counts, fs=FS_DEFAULT)

# 2. Capture live REST signal
print(f"Connecting to {PORT}...")
reader = EMGSerialReader(PORT, baud_rate=921600, num_channels=1)
if not reader.connect():
    print("ERROR: Could not connect")
    sys.exit(1)

print("Capturing 2.5s of live data (keep jaw relaxed)...")
result = reader.read_samples(2.5)
reader.disconnect()

live_channels = result["channels"]
n_samples = len(live_channels)
print(f"Captured {n_samples} samples")

if n_samples < 32:
    print("ERROR: Too few samples!")
    sys.exit(1)

live_counts = live_channels[:, 0]
live_feats = extract(live_counts, fs=FS_DEFAULT)

# 3. Compare raw signal characteristics
print("\n=== RAW SIGNAL COMPARISON ===")
print(f"  Training REST CSV: n={len(train_counts)}, mean={np.mean(train_counts):.1f}, std={np.std(train_counts):.1f}, min={np.min(train_counts):.0f}, max={np.max(train_counts):.0f}")
print(f"  Live capture:      n={len(live_counts)}, mean={np.mean(live_counts):.1f}, std={np.std(live_counts):.1f}, min={np.min(live_counts):.0f}, max={np.max(live_counts):.0f}")

train_health = signal_health(train_counts)
live_health = signal_health(live_counts)
print(f"  Training health: {train_health}")
print(f"  Live health:     {live_health}")

# 4. Compare features side by side
from ml.refined.utterance_features import FEATURE_NAMES
print("\n=== FEATURE COMPARISON (training REST vs live REST) ===")
print(f"  {'Feature':20s} {'Training':>12s} {'Live':>12s} {'Ratio':>8s}")
for i, name in enumerate(FEATURE_NAMES):
    t = train_feats[i]
    l = live_feats[i]
    ratio = l / (t + 1e-9)
    flag = " <<<" if abs(ratio - 1.0) > 0.5 and abs(t) > 0.001 else ""
    print(f"  {name:20s} {t:12.4f} {l:12.4f} {ratio:8.2f}{flag}")

# 5. What does the model predict for this live capture?
clf = joblib.load('refined_model/classifier.pkl')
le = joblib.load('refined_model/label_encoder.pkl')
x = live_feats.reshape(1, -1)
pred = le.inverse_transform(clf.predict(x))[0]
print(f"\nLive prediction: {pred.upper()}")
if hasattr(clf, 'predict_proba'):
    probs = clf.predict_proba(x)[0]
    for cls, p in sorted(zip(le.classes_, probs), key=lambda t: -t[1]):
        print(f"  {cls:8s}: {p:.1%}")
