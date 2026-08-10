"""Tests for the ASV ML pipeline.

All tests use synthetic/mock signals created within the test itself.
No physical hardware required. No synthetic data used for production training.
"""
import pytest
import numpy as np
import pandas as pd
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.config import settings
from ml.utils.features import EMGFeatureExtractor
from ml.utils.filters import bandpass_filter, notch_filter, apply_standard_emg_filter
from ml.preprocessing.pipeline import ASVPreprocessor
from ml.inference.realtime_engine import RealtimeASVEngine


# ---------------------------------------------------------------
# Serial packet parsing
# ---------------------------------------------------------------
class TestSerialParsing:
    """Test the serial line parser without hardware."""

    def _make_reader(self):
        from ml.acquisition.serial_reader import EMGSerialReader
        reader = EMGSerialReader(port="FAKE", num_channels=1)
        return reader

    def test_valid_single_channel(self):
        reader = self._make_reader()
        result = reader.parse_line(b"12345,1024\n")
        assert result is not None
        ts, channels = result
        assert ts == 12345
        assert channels == [1024.0]
        assert reader.stats["valid_packets"] == 1

    def test_valid_multi_channel(self):
        from ml.acquisition.serial_reader import EMGSerialReader
        reader = EMGSerialReader(port="FAKE", num_channels=4)
        result = reader.parse_line(b"100,10,20,30,40\n")
        assert result is not None
        assert result[1] == [10.0, 20.0, 30.0, 40.0]

    def test_malformed_no_comma(self):
        reader = self._make_reader()
        result = reader.parse_line(b"garbage\n")
        assert result is None
        assert reader.stats["malformed"] == 1

    def test_malformed_non_numeric(self):
        reader = self._make_reader()
        result = reader.parse_line(b"abc,def\n")
        assert result is None
        assert reader.stats["malformed"] == 1

    def test_firmware_log_line_skipped(self):
        reader = self._make_reader()
        result = reader.parse_line(b"[INFO] System ready\n")
        assert result is None
        assert reader.stats["malformed"] == 0  # Not counted as malformed

    def test_empty_line(self):
        reader = self._make_reader()
        result = reader.parse_line(b"\n")
        assert result is None

    def test_extra_channels_ignored(self):
        """Firmware sends 4 channels but we only want 1."""
        reader = self._make_reader()  # num_channels=1
        result = reader.parse_line(b"500,100,200,300,400\n")
        assert result is not None
        ts, channels = result
        assert len(channels) == 1
        assert channels[0] == 100.0


# ---------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------
class TestFeatureExtraction:

    def test_single_channel(self):
        extractor = EMGFeatureExtractor(fs=500)
        window = np.random.randn(128, 1)
        features = extractor.extract_features_vectorized(window, include_frequency=True)
        for feat in ["MAV", "RMS", "VAR", "STD", "WL", "ZCR", "SSC", "MF", "MEDF"]:
            assert feat in features
            assert len(features[feat]) == 1

    def test_multi_channel(self):
        extractor = EMGFeatureExtractor(fs=500)
        window = np.random.randn(128, 4)
        features = extractor.extract_features_vectorized(window, include_frequency=True)
        flat, names = extractor.flatten_features(features)
        assert len(flat) == 4 * 9
        assert len(names) == len(flat)

    def test_flatten_deterministic(self):
        """Feature ordering must be deterministic for training/inference agreement."""
        extractor = EMGFeatureExtractor(fs=500)
        window = np.random.randn(128, 2)
        _, names1 = extractor.flatten_features(
            extractor.extract_features_vectorized(window, include_frequency=True)
        )
        _, names2 = extractor.flatten_features(
            extractor.extract_features_vectorized(window, include_frequency=True)
        )
        assert names1 == names2


# ---------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------
class TestFiltering:

    def test_bandpass_nyquist_safety(self):
        """highcut >= Nyquist should be adjusted, not crash."""
        data = np.random.randn(500, 1)
        result = bandpass_filter(data, lowcut=10, highcut=300, fs=500)
        assert result.shape == data.shape

    def test_notch_above_nyquist_skipped(self):
        data = np.random.randn(500, 1)
        result = notch_filter(data, notch_freq=300, fs=500)
        np.testing.assert_array_equal(result, data)

    def test_standard_filter_chain(self):
        data = np.random.randn(500, 1)
        result = apply_standard_emg_filter(data, fs=500)
        assert result.shape == data.shape


# ---------------------------------------------------------------
# Preprocessing pipeline
# ---------------------------------------------------------------
class TestPreprocessing:

    def _make_recording(self, n_samples=1000, n_channels=1, label="hello", subject="T01", trial_id="trial_1"):
        cols = {"timestamp": np.arange(n_samples)}
        for ch in range(n_channels):
            cols[f"ch{ch}"] = np.random.randn(n_samples) * 100
        cols["label"] = label
        cols["subject"] = subject
        cols["trial_id"] = trial_id
        return pd.DataFrame(cols)

    def test_fit_basic(self):
        pp = ASVPreprocessor(is_training=True)
        df = self._make_recording()
        result = pp.fit([df])
        assert not result.empty
        assert pp.scaler is not None
        assert pp.feature_names is not None
        assert len(pp.feature_names) > 0

    def test_fit_rejects_simulated_in_training(self):
        pp = ASVPreprocessor(is_training=True)
        df = self._make_recording()
        df["is_simulated"] = True
        with pytest.raises(ValueError, match="No valid features"):
            pp.fit([df])

    def test_segmentation_window_count(self):
        pp = ASVPreprocessor(is_training=True)
        n = settings.WINDOW_SIZE * 3  # Should yield at least 3 windows
        df = self._make_recording(n_samples=n)
        result = pp.fit([df])
        # With 50% overlap, expect ~5 windows from 3x window_size
        assert len(result) >= 3

    def test_short_recording_skipped(self):
        pp = ASVPreprocessor(is_training=True)
        df = self._make_recording(n_samples=10)  # Too short
        with pytest.raises(ValueError):
            pp.fit([df])

    def test_save_load_roundtrip(self):
        pp = ASVPreprocessor(is_training=True)
        df = self._make_recording()
        pp.fit([df])

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            tmp = f.name
        try:
            pp.save(tmp)
            loaded = ASVPreprocessor.load(tmp)
            assert loaded.scaler is not None
            assert loaded.feature_names == pp.feature_names
        finally:
            os.unlink(tmp)

    def test_trial_id_preserved(self):
        pp = ASVPreprocessor(is_training=True)
        df = self._make_recording(trial_id="my_trial")
        result = pp.fit([df])
        assert "trial_id" in result.columns
        assert (result["trial_id"] == "my_trial").all()


# ---------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------
class TestInferenceEngine:

    def test_not_trained_state(self):
        engine = RealtimeASVEngine(model_dir="non_existent_dir_xyz")
        assert engine.is_loaded is False
        result = engine.predict_window(np.zeros((settings.WINDOW_SIZE, settings.NUM_CHANNELS)))
        assert result["status"] == "MODEL_NOT_TRAINED"
        assert result["prediction"] is None


# ---------------------------------------------------------------
# Dataset validation
# ---------------------------------------------------------------
class TestDatasetValidation:

    def test_empty_file(self):
        from ml.acquisition.validate_dataset import validate_trial
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("timestamp,channel_0\n")
            tmp = f.name
        try:
            report = validate_trial(tmp)
            assert report["status"] == "INVALID"
        finally:
            os.unlink(tmp)

    def test_good_file(self):
        from ml.acquisition.validate_dataset import validate_trial
        n = 500
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("timestamp,channel_0\n")
            for i in range(n):
                f.write(f"{i*2},{np.random.randint(0, 10000)}\n")
            tmp = f.name
        try:
            report = validate_trial(tmp, expected_rate=500)
            assert report["status"] in ("GOOD", "WARNING")
            assert report["n_samples"] == n
        finally:
            os.unlink(tmp)

    def test_flatline_detected(self):
        from ml.acquisition.validate_dataset import validate_trial
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("timestamp,channel_0\n")
            for i in range(100):
                f.write(f"{i*2},5000\n")
            tmp = f.name
        try:
            report = validate_trial(tmp)
            warnings = " ".join(report.get("warnings", []))
            assert "flatline" in warnings.lower()
        finally:
            os.unlink(tmp)
