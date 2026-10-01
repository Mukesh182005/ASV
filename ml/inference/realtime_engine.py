import os
import joblib
import numpy as np
import logging
from collections import deque
from pathlib import Path

# Fix python path if running directly
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from ml.config import settings
from ml.preprocessing.pipeline import ASVPreprocessor

logger = logging.getLogger(__name__)

class RealtimeASVEngine:
    def __init__(self, model_dir=None):
        if model_dir is None:
            model_dir = settings.MODELS_DIR / "latest"
            
        self.model_dir = Path(model_dir)
        self.is_loaded = False
        self.classifier = None
        self.label_encoder = None
        self.preprocessor = None
        
        # History for majority voting / smoothing
        self.prediction_history = deque(maxlen=5)
        
        self._load_artifacts()
        
    def _load_artifacts(self):
        if not self.model_dir.exists():
            logger.warning(f"Model directory not found: {self.model_dir}")
            return
            
        clf_path = self.model_dir / "classifier.pkl"
        le_path = self.model_dir / "label_encoder.pkl"
        prep_path = self.model_dir / "preprocessor.pkl"
        
        if not all(p.exists() for p in [clf_path, le_path, prep_path]):
            logger.warning(f"Incomplete model artifacts in {self.model_dir}")
            return
            
        try:
            self.classifier = joblib.load(clf_path)
            self.label_encoder = joblib.load(le_path)
            self.preprocessor = ASVPreprocessor.load(prep_path)
            self.is_loaded = True
            logger.info(f"Successfully loaded model from {self.model_dir}")
        except Exception as e:
            logger.error(f"Failed to load model artifacts: {e}")
            self.is_loaded = False

    def predict_window(self, window_data):
        """
        Process a single window of live EMG data.
        window_data: ndarray (WINDOW_SIZE, NUM_CHANNELS)
        """
        if not self.is_loaded:
            return {
                "status": "MODEL_NOT_TRAINED",
                "prediction": None,
                "confidence": 0.0,
                "smoothed_prediction": None
            }
            
        try:
            # Match training dimensions
            if window_data.shape != (settings.WINDOW_SIZE, settings.NUM_CHANNELS):
                logger.warning(f"Window shape mismatch: got {window_data.shape}, expected {(settings.WINDOW_SIZE, settings.NUM_CHANNELS)}")
                # Allow it to proceed if time dimension is close, but warn
                
            # Preprocess, filter, feature extract, scale (identically to training)
            features = self.preprocessor.process_live_window(window_data)
            
            # Predict
            features_2d = features.reshape(1, -1)
            pred_idx = self.classifier.predict(features_2d)[0]
            pred_word = self.label_encoder.inverse_transform([pred_idx])[0]
            
            if hasattr(self.classifier, "predict_proba"):
                probs = self.classifier.predict_proba(features_2d)[0]
                confidence = float(probs[pred_idx])
            else:
                confidence = 1.0
                
            self.prediction_history.append(pred_word)
            
            # Smoothing (majority vote over last N predictions)
            from collections import Counter
            most_common = Counter(self.prediction_history).most_common(1)[0][0]
            
            return {
                "status": "SUCCESS",
                "prediction": pred_word,
                "confidence": confidence,
                "smoothed_prediction": most_common
            }
            
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return {
                "status": "ERROR",
                "error": str(e),
                "prediction": None,
                "confidence": 0.0,
                "smoothed_prediction": None
            }
