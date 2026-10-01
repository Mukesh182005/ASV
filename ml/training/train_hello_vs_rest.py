"""Temporary Proof-of-Concept Binary HELLO vs REST Trainer.

Trains a binary classifier (HELLO vs REST) using proper GroupKFold cross-validation
by trial_id to prevent window leakage. Saves model to ml/models/demo_hello_rest/
without overwriting ml/models/latest/.

Usage:
    python ml/training/train_hello_vs_rest.py
    python ml/training/train_hello_vs_rest.py --data-dir datasets/custom_silent_speech/raw/S01
"""
import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    confusion_matrix, classification_report,
)
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ml.config import settings
from ml.preprocessing.pipeline import ASVPreprocessor
from ml.training.train_pipeline import discover_recordings, load_recording

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEMO_MODEL_DIR = settings.MODELS_DIR / "demo_hello_rest"


def inspect_s01_hello_dataset(data_dir):
    """Inspect and report statistics on existing hello recordings."""
    hello_dir = Path(data_dir) / "hello"
    if not hello_dir.exists():
        hello_dir = Path(data_dir)
    
    csv_files = sorted(hello_dir.rglob("*.csv"))
    logger.info(f"Inspecting hello dataset at: {hello_dir}")
    logger.info(f"Found {len(csv_files)} CSV files")
    
    records = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            meta_path = f.with_name(f.stem + "_meta.json")
            meta = {}
            if meta_path.exists():
                with open(meta_path) as mp:
                    meta = json.load(mp)
            
            # Find emg col
            emg_cols = [c for c in df.columns if c.startswith("ch") or c.startswith("channel_")]
            ch0 = df[emg_cols[0]].values if emg_cols else np.array([])
            
            records.append({
                "file": f.name,
                "n_samples": len(df),
                "duration_sec": meta.get("duration_sec", len(df) / settings.SAMPLING_RATE_HZ),
                "actual_fs": meta.get("actual_sampling_rate_hz", 0),
                "mean": round(float(np.mean(ch0)), 2) if len(ch0) > 0 else 0,
                "std": round(float(np.std(ch0)), 2) if len(ch0) > 0 else 0,
                "min": round(float(np.min(ch0)), 2) if len(ch0) > 0 else 0,
                "max": round(float(np.max(ch0)), 2) if len(ch0) > 0 else 0,
            })
        except Exception as e:
            logger.warning(f"Could not inspect {f.name}: {e}")
            
    return pd.DataFrame(records)


def train_hello_vs_rest(data_dir=None):
    """Attempt binary training of HELLO vs REST.
    
    If true REST recordings are missing, logs a scientific error and stops
    without fabricating data.
    """
    if data_dir is None:
        data_dir = settings.RAW_DATA_DIR / "S01"
        if not data_dir.exists():
            data_dir = settings.RAW_DATA_DIR

    logger.info(f"=== ASV Proof-of-Concept: HELLO vs REST Training ===")
    logger.info(f"Checking dataset directory: {data_dir}")
    
    # 1. Inspect existing hello recordings
    hello_df = inspect_s01_hello_dataset(data_dir)
    if not hello_df.empty:
        logger.info(f"Hello dataset summary: {len(hello_df)} recordings, ~{hello_df['n_samples'].sum()} total samples.")

    # 2. Discover all recordings in data_dir
    recordings = discover_recordings(data_dir)
    
    labels_found = set(r["label"] for r in recordings)
    logger.info(f"Labels found in dataset: {list(labels_found)}")
    
    # 3. Scientific Validity Check for REST Data
    has_rest = "rest" in labels_found or "no_hello" in labels_found
    
    if not has_rest or len(labels_found) < 2:
        logger.error("\n" + "="*70)
        logger.error("VALIDATION ERROR: INSUFFICIENT REST DATA FOR SCIENTIFIC BINARY CLASSIFICATION")
        logger.error("="*70)
        logger.error("Found ONLY 'hello' recordings in the dataset.")
        logger.error("Missing: True 'rest' / non-hello EMG recordings (e.g., in datasets/custom_silent_speech/raw/S01/rest/).")
        logger.error("NOTE: Per project guidelines, synthetic/carved rest data will NOT be fabricated.")
        logger.error("To make this binary experiment valid, collect true REST trials using:")
        logger.error("    python ml/acquisition/collect_emg.py --subject S01 --label rest --reps 20 --port COM5")
        logger.error("="*70 + "\n")
        return {
            "valid": False,
            "reason": "Missing true REST recordings in raw dataset. Fabricating rest data is prohibited.",
            "hello_count": len(hello_df),
            "rest_count": 0,
            "accuracy": None,
            "f1": None
        }

    # 4. Load all recordings if REST data is present
    data_list = []
    for r in recordings:
        if r["label"] in ("hello", "rest", "no_hello"):
            # Standardize label to 'hello' or 'rest'
            lbl = "hello" if r["label"] == "hello" else "rest"
            df = load_recording(r["path"], lbl, r["subject"], r["trial_id"])
            if df is not None:
                data_list.append(df)

    preprocessor = ASVPreprocessor(is_training=True)
    features_df = preprocessor.fit(data_list)
    
    le = LabelEncoder()
    y = le.fit_transform(features_df["label"])
    X = features_df[preprocessor.feature_names].values
    groups = features_df["trial_id"].astype(str)
    
    cv = GroupKFold(n_splits=min(5, len(groups.unique())))
    model = RandomForestClassifier(n_estimators=100, max_depth=15, random_state=settings.RANDOM_STATE)
    
    fold_scores = []
    y_true_all, y_pred_all = [], []
    for train_idx, test_idx in cv.split(X, y, groups):
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict(X[test_idx])
        fold_scores.append(accuracy_score(y[test_idx], preds))
        y_true_all.extend(y[test_idx])
        y_pred_all.extend(preds)
        
    avg_acc = float(np.mean(fold_scores))
    prec, rec, f1, _ = precision_recall_fscore_support(y_true_all, y_pred_all, average="binary", zero_division=0)
    cm = confusion_matrix(y_true_all, y_pred_all).tolist()
    
    # Save demo model separately from ml/models/latest/
    DEMO_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.fit(X, y)
    joblib.dump(model, DEMO_MODEL_DIR / "classifier.pkl")
    joblib.dump(le, DEMO_MODEL_DIR / "label_encoder.pkl")
    preprocessor.save(DEMO_MODEL_DIR / "preprocessor.pkl")
    
    meta = {
        "model_type": "Binary HELLO vs REST Demo Classifier",
        "training_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "labels": le.classes_.tolist(),
        "cv_accuracy": round(avg_acc, 4),
        "cv_f1": round(f1, 4),
        "note": "Temporary proof-of-concept binary model. Saved separately from ml/models/latest/."
    }
    with open(DEMO_MODEL_DIR / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
        
    logger.info(f"Demo model saved to: {DEMO_MODEL_DIR}")
    logger.info(f"CV Accuracy: {avg_acc:.4f}, Binary F1: {f1:.4f}")
    
    return {
        "valid": True,
        "accuracy": round(avg_acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "confusion_matrix": cm,
        "model_dir": str(DEMO_MODEL_DIR)
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train HELLO vs REST proof-of-concept classifier")
    parser.add_argument("--data-dir", default=None, help="Path to raw dataset directory")
    args = parser.parse_args()
    
    result = train_hello_vs_rest(data_dir=args.data_dir)
    print("\n--- Summary ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
