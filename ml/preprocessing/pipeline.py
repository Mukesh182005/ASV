"""ASV Preprocessing Pipeline.

Provides consistent filtering, segmentation, and feature extraction
for both training and real-time inference.
"""
import numpy as np
import pandas as pd
import json
import logging
from ml.config import settings
from ml.utils.filters import apply_standard_emg_filter
from ml.utils.features import EMGFeatureExtractor
from sklearn.preprocessing import StandardScaler
import joblib

logger = logging.getLogger(__name__)


class ASVPreprocessor:
    """Wraps filtering, segmentation, feature extraction, and scaling."""

    PREPROCESSING_VERSION = 1

    def __init__(self, is_training=False):
        self.is_training = is_training
        self.scaler = None
        self.feature_extractor = EMGFeatureExtractor(fs=settings.SAMPLING_RATE_HZ)
        self.feature_names = None

    # ------------------------------------------------------------------
    # Training API
    # ------------------------------------------------------------------
    def fit(self, data_list):
        """Fit scaler on a list of recording DataFrames. Returns features DataFrame."""
        if not self.is_training:
            raise ValueError("fit() called but is_training=False")

        logger.info("Fitting ASVPreprocessor...")
        all_features = []
        for df in data_list:
            features_df = self._process_recording(df)
            if not features_df.empty:
                all_features.append(features_df)

        if not all_features:
            raise ValueError("No valid features extracted from training data")

        combined = pd.concat(all_features, ignore_index=True)
        feature_cols = [c for c in combined.columns
                        if c not in ("label", "subject", "repetition", "trial_id")]
        self.feature_names = feature_cols

        self.scaler = StandardScaler()
        self.scaler.fit(combined[feature_cols].values)
        logger.info(f"Scaler fitted on {len(combined)} windows, {len(feature_cols)} features.")

        # Scale the combined features in-place before returning
        combined[feature_cols] = self.scaler.transform(combined[feature_cols].values)
        return combined

    def transform(self, df):
        """Transform a single recording DataFrame (already fitted scaler)."""
        if self.scaler is None:
            raise ValueError("Scaler is not fitted or loaded")
        features_df = self._process_recording(df)
        if features_df.empty:
            return features_df
        features_df[self.feature_names] = self.scaler.transform(
            features_df[self.feature_names].values
        )
        return features_df

    # ------------------------------------------------------------------
    # Real-time inference API
    # ------------------------------------------------------------------
    def process_live_window(self, window_data):
        """Process a single live window (n_samples, n_channels) → scaled feature vector."""
        if self.scaler is None:
            raise ValueError("Scaler is not fitted or loaded")

        filtered = apply_standard_emg_filter(
            window_data,
            fs=settings.SAMPLING_RATE_HZ,
            notch_freq=settings.NOTCH_FREQ_HZ,
            lowcut=settings.BANDPASS_LOW_HZ,
            highcut=settings.BANDPASS_HIGH_HZ,
        )
        features_dict = self.feature_extractor.extract_features_vectorized(
            filtered, include_frequency=True
        )
        flat, names = self.feature_extractor.flatten_features(features_dict)

        if self.feature_names is None:
            self.feature_names = names

        return self.scaler.transform([flat])[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _process_recording(self, df):
        """Filter → segment → extract features for one recording."""
        # Reject simulated data in production training
        if self.is_training and "is_simulated" in df.columns and df["is_simulated"].any():
            logger.warning("Skipping simulated data in training mode")
            return pd.DataFrame()

        # Find EMG channel columns (ch0, ch1, ... or channel_0, channel_1, ...)
        emg_cols = sorted(
            [c for c in df.columns if
             (c.startswith("ch") and c[2:].isdigit()) or
             (c.startswith("channel_") and c.split("_")[-1].isdigit())],
        )
        if not emg_cols:
            logger.warning("No EMG channels found in data")
            return pd.DataFrame()

        emg_data = df[emg_cols].values
        if emg_data.ndim == 1:
            emg_data = emg_data.reshape(-1, 1)

        n_samples = len(emg_data)
        window_size = settings.WINDOW_SIZE
        step_size = settings.STEP_SIZE

        if n_samples < window_size:
            logger.warning(f"Recording too short ({n_samples} < {window_size}), skipping")
            return pd.DataFrame()

        # Filter the entire recording
        filtered = apply_standard_emg_filter(
            emg_data,
            fs=settings.SAMPLING_RATE_HZ,
            notch_freq=settings.NOTCH_FREQ_HZ,
            lowcut=settings.BANDPASS_LOW_HZ,
            highcut=settings.BANDPASS_HIGH_HZ,
        )

        # Segment and extract features
        features_list = []
        for start in range(0, n_samples - window_size + 1, step_size):
            window = filtered[start : start + window_size]
            feat_dict = self.feature_extractor.extract_features_vectorized(
                window, include_frequency=True
            )
            flat, names = self.feature_extractor.flatten_features(feat_dict)
            row = dict(zip(names, flat))

            # Carry metadata from the recording
            for col in ("label", "subject", "repetition", "trial_id"):
                if col in df.columns:
                    row[col] = df[col].iloc[start]

            features_list.append(row)

        return pd.DataFrame(features_list)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, filepath):
        obj = {
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "preprocessing_version": self.PREPROCESSING_VERSION,
            "settings": {
                "SAMPLING_RATE_HZ": settings.SAMPLING_RATE_HZ,
                "WINDOW_SIZE": settings.WINDOW_SIZE,
                "STEP_SIZE": settings.STEP_SIZE,
                "NUM_CHANNELS": settings.NUM_CHANNELS,
                "BANDPASS_LOW_HZ": settings.BANDPASS_LOW_HZ,
                "BANDPASS_HIGH_HZ": settings.BANDPASS_HIGH_HZ,
                "NOTCH_FREQ_HZ": settings.NOTCH_FREQ_HZ,
            },
        }
        joblib.dump(obj, filepath)

    @classmethod
    def load(cls, filepath):
        obj = joblib.load(filepath)
        instance = cls(is_training=False)
        instance.scaler = obj["scaler"]
        instance.feature_names = obj["feature_names"]
        saved = obj.get("settings", {})
        if saved.get("SAMPLING_RATE_HZ") != settings.SAMPLING_RATE_HZ:
            logger.warning(
                f"Loaded sampling rate ({saved.get('SAMPLING_RATE_HZ')}) "
                f"differs from config ({settings.SAMPLING_RATE_HZ})"
            )
        return instance
