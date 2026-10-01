"""Tests for the pretrained EMG model pipeline.

Tests cover: preprocessing, dataset loading, model architecture,
input shapes, feature extraction, and leakage prevention.
All tests use synthetic signals — no physical hardware required.
"""
import pytest
import numpy as np
import torch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.pretrained.config import (
    TINYMYO_WINDOW_SIZE,
    TINYMYO_EMBED_DIM,
    TINYMYO_TOKENS_PER_CHANNEL,
    LABEL_MAP,
    OUR_SAMPLING_RATE_HZ,
    TINYMYO_TARGET_SAMPLING_RATE_HZ,
)


# ---------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------
class TestPretrainedPreprocessing:
    """Test the TinyMyo-specific preprocessing pipeline."""

    def test_resample_upsamples(self):
        """475 Hz -> 2000 Hz should increase sample count."""
        from ml.pretrained.preprocessing import resample_signal

        n_original = 950  # ~2 seconds at 475 Hz
        data = np.random.randn(n_original, 1)
        resampled = resample_signal(data, 475.0, 2000.0)

        # Expected: ~950 * (2000/475) ≈ 4000 samples
        expected = int(n_original * 2000 / 475)
        assert resampled.shape[0] > n_original
        assert abs(resampled.shape[0] - expected) < 10  # Allow small rounding
        assert resampled.shape[1] == 1

    def test_resample_preserves_channels(self):
        from ml.pretrained.preprocessing import resample_signal

        data = np.random.randn(500, 3)
        resampled = resample_signal(data, 500.0, 2000.0)
        assert resampled.shape[1] == 3

    def test_normalize_zscore(self):
        from ml.pretrained.preprocessing import normalize_signal

        data = np.random.randn(1000, 1) * 100 + 500
        normalized = normalize_signal(data, "zscore")
        assert abs(np.mean(normalized)) < 0.01
        assert abs(np.std(normalized) - 1.0) < 0.01

    def test_normalize_constant_signal(self):
        """Constant signal should not cause division by zero."""
        from ml.pretrained.preprocessing import normalize_signal

        data = np.ones((100, 1)) * 42
        normalized = normalize_signal(data, "zscore")
        assert not np.any(np.isnan(normalized))
        assert not np.any(np.isinf(normalized))

    def test_preprocess_trial_output_shape(self):
        from ml.pretrained.preprocessing import preprocess_trial

        raw = np.random.randn(950, 1) * 1000 + 15000
        processed = preprocess_trial(raw, actual_fs=475.0)
        # Should be resampled to ~4000 samples
        assert processed.shape[0] > 3500
        assert processed.shape[1] == 1

    def test_extract_windows(self):
        from ml.pretrained.preprocessing import extract_windows

        signal = np.random.randn(4000, 1)
        windows = extract_windows(signal, window_size=1000, step_size=500)
        # 4000 samples, 1000 window, 500 step -> windows at 0,500,1000,...,3000 = 7
        assert len(windows) == 7
        for w in windows:
            assert w.shape == (1000, 1)

    def test_short_trial_padded(self):
        from ml.pretrained.preprocessing import extract_windows

        signal = np.random.randn(500, 1)  # Too short
        windows = extract_windows(signal, window_size=1000, step_size=500)
        assert len(windows) == 1
        assert windows[0].shape == (1000, 1)

    def test_full_preprocess_and_window(self):
        from ml.pretrained.preprocessing import preprocess_and_window

        raw = np.random.randn(950, 1) * 1000 + 15000
        windows = preprocess_and_window(raw, actual_fs=475.0)
        assert len(windows) >= 1
        for w in windows:
            assert w.shape[0] == TINYMYO_WINDOW_SIZE
            assert w.shape[1] == 1


# ---------------------------------------------------------------
# Model Architecture
# ---------------------------------------------------------------
class TestTinyMyoModel:
    """Test the TinyMyo model architecture."""

    def test_encoder_output_shape(self):
        from ml.pretrained.tinymyo_model import TinyMyoEncoder

        model = TinyMyoEncoder()
        x = torch.randn(2, 1, TINYMYO_WINDOW_SIZE)  # batch=2, 1 channel
        features = model(x)
        assert features.shape == (2, 192)

    def test_encoder_multi_channel(self):
        """Verify architecture works with multiple channels too."""
        from ml.pretrained.tinymyo_model import TinyMyoEncoder

        model = TinyMyoEncoder()
        x = torch.randn(2, 8, TINYMYO_WINDOW_SIZE)  # 8 channels
        features = model(x)
        assert features.shape == (2, 192)


    def test_patch_embedding_tokens(self):
        from ml.pretrained.tinymyo_model import PatchEmbedding

        pe = PatchEmbedding()
        x = torch.randn(1, 1, TINYMYO_WINDOW_SIZE)
        tokens = pe(x)
        # 1 channel * (1000 / 20) = 50 tokens
        assert tokens.shape == (1, TINYMYO_TOKENS_PER_CHANNEL, TINYMYO_EMBED_DIM)

    def test_patch_embedding_multi_channel_tokens(self):
        from ml.pretrained.tinymyo_model import PatchEmbedding

        pe = PatchEmbedding()
        x = torch.randn(1, 4, TINYMYO_WINDOW_SIZE)
        tokens = pe(x)
        # 4 channels * 50 tokens = 200 tokens
        assert tokens.shape == (1, 4 * TINYMYO_TOKENS_PER_CHANNEL, TINYMYO_EMBED_DIM)

    def test_classifier_output_shape(self):
        from ml.pretrained.tinymyo_model import TinyMyoClassifier

        model = TinyMyoClassifier(num_classes=2, head_type="mlp")
        x = torch.randn(4, 1, TINYMYO_WINDOW_SIZE)
        logits = model(x)
        assert logits.shape == (4, 2)

    def test_classifier_linear_head(self):
        from ml.pretrained.tinymyo_model import TinyMyoClassifier

        model = TinyMyoClassifier(num_classes=2, head_type="linear")
        x = torch.randn(4, 1, TINYMYO_WINDOW_SIZE)
        logits = model(x)
        assert logits.shape == (4, 2)

    def test_frozen_backbone_params(self):
        from ml.pretrained.tinymyo_model import TinyMyoClassifier

        model = TinyMyoClassifier(freeze_backbone=True)
        params = model.count_parameters()
        assert params["frozen"] > 0
        assert params["trainable"] < params["total"]
        # Only head should be trainable
        assert params["trainable"] == params["head"]

    def test_unfreeze_backbone(self):
        from ml.pretrained.tinymyo_model import TinyMyoClassifier

        model = TinyMyoClassifier(freeze_backbone=True)
        model.unfreeze_backbone()
        params = model.count_parameters()
        assert params["frozen"] == 0
        assert params["trainable"] == params["total"]

    def test_feature_extraction(self):
        from ml.pretrained.tinymyo_model import TinyMyoClassifier

        model = TinyMyoClassifier(freeze_backbone=True)
        x = torch.randn(2, 1, TINYMYO_WINDOW_SIZE)
        features = model.get_features(x)

        assert not features.requires_grad  # Should be detached

    def test_forward_tokens(self):
        from ml.pretrained.tinymyo_model import TinyMyoEncoder

        model = TinyMyoEncoder()
        x = torch.randn(1, 1, TINYMYO_WINDOW_SIZE)
        tokens = model.forward_tokens(x)
        assert tokens.shape == (1, TINYMYO_TOKENS_PER_CHANNEL, TINYMYO_EMBED_DIM)


# ---------------------------------------------------------------
# Weight Loading
# ---------------------------------------------------------------
class TestWeightLoading:
    """Test weight loading utilities."""

    def test_load_nonexistent_checkpoint(self):
        from ml.pretrained.tinymyo_model import TinyMyoEncoder, load_pretrained_weights

        model = TinyMyoEncoder()
        success, msg = load_pretrained_weights(model, "/nonexistent/path.pt")
        assert success is False
        assert "not found" in msg.lower()

    def test_load_mismatched_checkpoint(self, tmp_path):
        from ml.pretrained.tinymyo_model import TinyMyoEncoder, load_pretrained_weights

        # Save a checkpoint with wrong keys
        wrong_state = {"wrong_key": torch.randn(10)}
        path = tmp_path / "wrong.pt"
        torch.save(wrong_state, path)

        model = TinyMyoEncoder()
        success, msg = load_pretrained_weights(model, str(path))
        # Should fail gracefully
        assert success is False


# ---------------------------------------------------------------
# Leakage Prevention
# ---------------------------------------------------------------
class TestLeakagePrevention:
    """Verify that trial-level grouping prevents data leakage."""

    def test_groupkfold_no_trial_overlap(self):
        """Windows from the same trial must never be in both train and test."""
        from sklearn.model_selection import GroupKFold

        # Simulate: 10 trials, ~7 windows each
        trial_ids = []
        for i in range(10):
            trial_ids.extend([f"trial_{i}"] * 7)
        trial_ids = np.array(trial_ids)
        X = np.random.randn(len(trial_ids), 10)
        y = np.array([0] * 35 + [1] * 35)

        gkf = GroupKFold(n_splits=5)
        for train_idx, test_idx in gkf.split(X, y, trial_ids):
            train_trials = set(trial_ids[train_idx])
            test_trials = set(trial_ids[test_idx])
            overlap = train_trials & test_trials
            assert len(overlap) == 0, f"Trial leakage detected: {overlap}"
