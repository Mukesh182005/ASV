"""
ASV — Utterance-level inference engine (refined model)
======================================================

Loads the refined model produced by ml/refined/train_refined.py and classifies a
whole utterance (one articulated word) from raw ADC counts. Feature extraction is
imported from ml.refined.utterance_features, so training and serving cannot drift.
"""
from __future__ import annotations
import logging
from pathlib import Path

import numpy as np
import joblib

from ml.refined.utterance_features import extract, FEATURE_NAMES, FS_DEFAULT

logger = logging.getLogger(__name__)

# refined_model/ lives at the repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_DIR = REPO_ROOT / "refined_model"


class UtteranceEngine:
    def __init__(self, model_dir: Path | None = None):
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.classifier = None
        self.label_encoder = None
        self.labels: list[str] = []
        self.is_loaded = False
        self._load()

    def _load(self):
        clf = self.model_dir / "classifier.pkl"
        le = self.model_dir / "label_encoder.pkl"
        if not (clf.exists() and le.exists()):
            logger.warning(f"Refined model not found in {self.model_dir}")
            return
        try:
            self.classifier = joblib.load(clf)
            self.label_encoder = joblib.load(le)
            self.labels = self.label_encoder.classes_.tolist()
            self.is_loaded = True
            logger.info(f"Loaded refined model from {self.model_dir} — labels: {self.labels}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to load refined model: {e}")
            self.is_loaded = False

    def predict(self, counts, fs: float = FS_DEFAULT) -> dict:
        """Classify one utterance from raw ADC counts (1-D)."""
        if not self.is_loaded:
            return {"status": "MODEL_NOT_TRAINED", "prediction": None,
                    "confidence": 0.0, "ranking": []}

        counts = np.asarray(counts, dtype=float).ravel()
        if counts.size < 32:
            return {"status": "TOO_SHORT", "prediction": None,
                    "confidence": 0.0, "ranking": []}

        x = extract(counts, fs=fs).reshape(1, -1)
        idx = int(self.classifier.predict(x)[0])
        word = self.label_encoder.inverse_transform([idx])[0]

        ranking, confidence = [], 1.0
        if hasattr(self.classifier, "predict_proba"):
            proba = self.classifier.predict_proba(x)[0]
            order = np.argsort(proba)[::-1]
            ranking = [{"word": self.label_encoder.inverse_transform([int(i)])[0],
                        "prob": round(float(proba[i]), 4)} for i in order]
            confidence = round(float(proba[idx]), 4)

        return {"status": "SUCCESS", "prediction": word,
                "confidence": confidence, "ranking": ranking}
