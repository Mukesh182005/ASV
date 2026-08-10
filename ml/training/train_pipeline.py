"""Production training pipeline for ASV silent-speech classifier.

Usage:
    python ml/training/train_pipeline.py
    python ml/training/train_pipeline.py --data-dir datasets/custom_silent_speech/raw
"""
import os
import sys
import json
import glob
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def discover_recordings(data_dir):
    """Walk data_dir/{subject}/{label}/*.csv and return list of (csv_path, subject, label, rep)."""
    data_dir = Path(data_dir)
    recordings = []
    for csv_path in sorted(data_dir.rglob("*.csv")):
        # Try to infer subject/label from directory structure: raw/{subject}/{label}/file.csv
        parts = csv_path.relative_to(data_dir).parts
        meta_path = csv_path.with_name(csv_path.stem + "_meta.json")
        subject, label = None, None
        if len(parts) >= 3:  # subject/label/file.csv
            subject = parts[0]
            label = parts[1]
        # Try metadata JSON
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                subject = meta.get("subject", subject)
                label = meta.get("label", label)
                if meta.get("is_simulated", False):
                    logger.warning(f"Skipping simulated file: {csv_path.name}")
                    continue
            except Exception:
                pass
        if subject is None or label is None:
            logger.warning(f"Cannot determine subject/label for {csv_path}, skipping")
            continue
        # Extract rep number from filename if possible
        rep = csv_path.stem  # use full stem as unique trial ID
        recordings.append({"path": csv_path, "subject": subject, "label": label, "trial_id": rep})
    return recordings


def load_recording(csv_path, label, subject, trial_id):
    """Load a single CSV recording into a DataFrame with metadata columns."""
    try:
        df = pd.read_csv(csv_path)
        # Rename columns to standard format if needed
        col_map = {}
        for c in df.columns:
            if c.startswith("channel_"):
                idx = c.replace("channel_", "")
                col_map[c] = f"ch{idx}"
        if col_map:
            df = df.rename(columns=col_map)
        df["label"] = label
        df["subject"] = subject
        df["trial_id"] = trial_id
        return df
    except Exception as e:
        logger.error(f"Failed to load {csv_path}: {e}")
        return None


def train_and_evaluate(data_dir=None):
    if data_dir is None:
        data_dir = settings.RAW_DATA_DIR

    logger.info(f"Discovering recordings in {data_dir}")
    recordings = discover_recordings(data_dir)

    if not recordings:
        logger.error("INSUFFICIENT_DATA: No valid recordings found.")
        logger.error("Collect data first: python ml/acquisition/collect_emg.py --help")
        return

    # Count labels
    label_counts = {}
    for r in recordings:
        label_counts[r["label"]] = label_counts.get(r["label"], 0) + 1
    logger.info(f"Found {len(recordings)} recordings across {len(label_counts)} labels: {label_counts}")

    if len(label_counts) < 2:
        logger.error("INSUFFICIENT_DATA: Need at least 2 different labels to train a classifier.")
        return

    # Load all recordings
    data_list = []
    for r in recordings:
        df = load_recording(r["path"], r["label"], r["subject"], r["trial_id"])
        if df is not None:
            data_list.append(df)

    if not data_list:
        logger.error("INSUFFICIENT_DATA: Could not load any recordings.")
        return

    # Preprocess: filter + segment + extract features
    preprocessor = ASVPreprocessor(is_training=True)
    try:
        features_df = preprocessor.fit(data_list)
    except ValueError as e:
        logger.error(f"Preprocessing failed: {e}")
        return

    if features_df.empty or len(features_df) < 5:
        logger.error("INSUFFICIENT_DATA: Not enough feature windows extracted.")
        return

    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(features_df["label"])
    X = features_df[preprocessor.feature_names].values

    # Grouping for cross-validation: group by trial_id to prevent leakage
    if "trial_id" in features_df.columns:
        groups = features_df["trial_id"].astype(str)
    else:
        groups = features_df["subject"].astype(str) + "_" + features_df.get("repetition", pd.Series(range(len(features_df)))).astype(str)

    n_unique_groups = len(groups.unique())
    subjects = features_df["subject"].unique().tolist() if "subject" in features_df.columns else []

    logger.info(f"Feature matrix: {X.shape[0]} windows x {X.shape[1]} features")
    logger.info(f"Labels: {le.classes_.tolist()}, Groups: {n_unique_groups}, Subjects: {subjects}")

    if len(subjects) == 1:
        logger.warning("Only 1 subject — cannot evaluate subject-independent generalization.")

    # Models
    models = {
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=15, random_state=settings.RANDOM_STATE),
        "SVM": SVC(kernel="rbf", C=1.0, gamma="scale", probability=True, random_state=settings.RANDOM_STATE),
    }

    n_splits = min(5, n_unique_groups)
    if n_splits < 2:
        logger.warning("Only 1 group — using stratified split instead of GroupKFold.")
        cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=settings.RANDOM_STATE)
        use_groups = False
    else:
        cv = GroupKFold(n_splits=n_splits)
        use_groups = True

    best_name, best_model, best_score = None, None, -1
    eval_results = {}

    for name, model in models.items():
        logger.info(f"Evaluating {name}...")
        fold_scores = []
        split_iter = cv.split(X, y, groups) if use_groups else cv.split(X, y)
        for train_idx, test_idx in split_iter:
            model.fit(X[train_idx], y[train_idx])
            preds = model.predict(X[test_idx])
            fold_scores.append(accuracy_score(y[test_idx], preds))

        avg = float(np.mean(fold_scores))
        logger.info(f"  {name} CV accuracy: {avg:.4f} (folds: {[round(s,3) for s in fold_scores]})")

        # Train on full data
        model.fit(X, y)
        eval_results[name] = {"cv_accuracy": avg, "fold_scores": [round(s, 4) for s in fold_scores]}

        if avg > best_score:
            best_score = avg
            best_name = name
            best_model = model

    # Full evaluation of best model (on training data — noted as such)
    full_preds = best_model.predict(X)
    prec, rec, f1, _ = precision_recall_fscore_support(y, full_preds, average="weighted", zero_division=0)
    cm = confusion_matrix(y, full_preds).tolist()
    cr = classification_report(y, full_preds, target_names=le.classes_, output_dict=True, zero_division=0)

    logger.info(f"\nBest model: {best_name} (CV acc: {best_score:.4f})")
    logger.info(f"Weighted P/R/F1 (train): {prec:.3f} / {rec:.3f} / {f1:.3f}")

    # Save artifacts
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = settings.MODELS_DIR / f"asv_model_{ts}"
    model_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(best_model, model_dir / "classifier.pkl")
    joblib.dump(le, model_dir / "label_encoder.pkl")
    preprocessor.save(model_dir / "preprocessor.pkl")

    # Feature schema
    feature_schema = {
        "version": 1,
        "feature_names": preprocessor.feature_names,
        "n_features": len(preprocessor.feature_names),
    }
    with open(model_dir / "feature_schema.json", "w") as f:
        json.dump(feature_schema, f, indent=2)

    # Metadata
    metadata = {
        "model_type": best_name,
        "training_timestamp": ts,
        "labels": le.classes_.tolist(),
        "feature_version": 1,
        "preprocessing_version": 1,
        "sampling_rate_hz": settings.SAMPLING_RATE_HZ,
        "window_size": settings.WINDOW_SIZE,
        "window_step": settings.STEP_SIZE,
        "num_channels": settings.NUM_CHANNELS,
        "training_subjects": subjects,
        "n_recordings": len(recordings),
        "n_windows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "single_subject_warning": len(subjects) == 1,
    }
    with open(model_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Evaluation
    evaluation = {
        "best_model": best_name,
        "cv_accuracy": best_score,
        "cv_n_splits": n_splits,
        "cv_method": "GroupKFold" if use_groups else "StratifiedKFold",
        "all_models": eval_results,
        "train_weighted_precision": round(prec, 4),
        "train_weighted_recall": round(rec, 4),
        "train_weighted_f1": round(f1, 4),
        "confusion_matrix": cm,
        "classification_report": cr,
        "note": "Metrics on full training data after cross-validation. Evaluate on held-out subjects for true generalization.",
    }
    with open(model_dir / "evaluation.json", "w") as f:
        json.dump(evaluation, f, indent=2)

    # Update 'latest' alias
    latest_dir = settings.MODELS_DIR / "latest"
    if latest_dir.exists():
        import shutil
        shutil.rmtree(latest_dir)
    import shutil
    shutil.copytree(model_dir, latest_dir)

    logger.info(f"Model artifacts saved to: {model_dir}")
    logger.info(f"Latest alias updated: {latest_dir}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Train ASV classifier")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()
    train_and_evaluate(data_dir=args.data_dir)


if __name__ == "__main__":
    main()
