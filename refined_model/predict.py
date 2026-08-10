"""Classify one ASV recording with the refined model.

Usage:  python predict.py <recording.csv>
"""
import sys, json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.refined.utterance_features import extract, load_counts_csv, FS_DEFAULT

HERE = Path(__file__).resolve().parent

def main():
    if len(sys.argv) < 2:
        print("usage: python predict.py <recording.csv>"); sys.exit(1)
    counts = load_counts_csv(sys.argv[1])
    x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
    clf = joblib.load(HERE / "classifier.pkl")
    le = joblib.load(HERE / "label_encoder.pkl")
    pred = le.inverse_transform(clf.predict(x))[0]
    conf = None
    if hasattr(clf, "predict_proba"):
        p = clf.predict_proba(x)[0]
        conf = float(np.max(p))
        ranking = sorted(zip(le.classes_, p), key=lambda t: -t[1])
    print(f"\nPrediction: {pred}" + (f"  (confidence {conf:.0%})" if conf is not None else ""))
    if conf is not None:
        print("Ranking:")
        for w, pr in ranking:
            print(f"   {w:8s} {pr:5.1%}")

if __name__ == "__main__":
    main()
