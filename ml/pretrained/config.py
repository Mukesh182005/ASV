"""Configuration for the TinyMyo pretrained model adapter.

All parameters here are derived from the TinyMyo paper (arXiv:2512.15729)
and adapted for our ASV hardware specifications.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent

# Where we store downloaded pretrained weights
PRETRAINED_WEIGHTS_DIR = _PROJECT_ROOT / "ml" / "models" / "pretrained" / "tinymyo"

# Where we store fine-tuned model artifacts
FINETUNED_MODEL_DIR = _PROJECT_ROOT / "ml" / "models" / "pretrained_finetuned"

# Dataset paths
RAW_DATA_DIR = _PROJECT_ROOT / "datasets" / "custom_silent_speech" / "raw" / "S01"

# ---------------------------------------------------------------------------
# Our hardware specifications (FACT: from project settings)
# ---------------------------------------------------------------------------
OUR_SAMPLING_RATE_HZ = 475        # Actual effective rate from ADS1115/ESP32
OUR_NUM_CHANNELS = 1              # AD8232 single output -> ADS1115 A0
OUR_TRIAL_DURATION_SEC = 2.0      # Each recording is ~2 seconds
OUR_APPROX_SAMPLES_PER_TRIAL = 950  # ~475 Hz * 2s

# ---------------------------------------------------------------------------
# TinyMyo model specifications (FACT: from arXiv:2512.15729 & official config.json)
# ---------------------------------------------------------------------------
TINYMYO_TARGET_SAMPLING_RATE_HZ = 2000   # TinyMyo trained at 2 kHz
TINYMYO_WINDOW_SIZE = 1000               # T=1000 time steps per window
TINYMYO_PATCH_LENGTH = 20                # L=20 samples per patch
TINYMYO_PATCH_STRIDE = 20                # S=20 (non-overlapping patches)
TINYMYO_TOKENS_PER_CHANNEL = 50          # 1000 / 20 = 50

# Transformer encoder hyperparameters (from official PulpBio/TinyMyo config.json)
TINYMYO_EMBED_DIM = 192                  # Official embed_dim = 192
TINYMYO_NUM_HEADS = 3                    # Official n_head = 3 (head_dim = 64)
TINYMYO_DEPTH = 8                        # Official n_layer = 8
TINYMYO_MLP_RATIO = 4.0                  # Official mlp_ratio = 4 (hidden_dim = 768)
TINYMYO_DROPOUT = 0.1

# ---------------------------------------------------------------------------
# Adaptation parameters (INFERENCE: our engineering choices)
# ---------------------------------------------------------------------------
# Resampling: 475 Hz -> 2000 Hz (ratio ~4.21)
RESAMPLE_RATIO = TINYMYO_TARGET_SAMPLING_RATE_HZ / OUR_SAMPLING_RATE_HZ

# After resampling, a 2-second trial becomes ~4000 samples at 2kHz
# We can extract multiple 1000-sample windows with overlap
WINDOW_OVERLAP_RATIO = 0.5
WINDOW_STEP = int(TINYMYO_WINDOW_SIZE * (1.0 - WINDOW_OVERLAP_RATIO))

# Filtering (applied before resampling, at our native rate)
BANDPASS_LOW_HZ = 10
BANDPASS_HIGH_HZ = 200     # Conservative for 475 Hz Nyquist (~237.5 Hz)
NOTCH_FREQ_HZ = 50         # Power line interference

# Normalization
NORMALIZE_METHOD = "zscore"  # z-score normalization per trial

# ---------------------------------------------------------------------------
# Training hyperparameters
# ---------------------------------------------------------------------------
LABEL_MAP = {"rest": 0, "hello": 1}
NUM_CLASSES = 2
BATCH_SIZE = 16
LEARNING_RATE_HEAD = 1e-3        # For classifier head only
LEARNING_RATE_FINETUNE = 1e-4    # For full fine-tuning
WEIGHT_DECAY = 1e-4
NUM_EPOCHS_HEAD = 50
NUM_EPOCHS_FINETUNE = 30
PATIENCE = 10                    # Early stopping patience

# Cross-validation
CV_N_SPLITS = 5
RANDOM_STATE = 42

# ---------------------------------------------------------------------------
# HuggingFace model info (FACT: Verified official repository and file path)
# ---------------------------------------------------------------------------
HF_REPO_ID = "PulpBio/TinyMyo"
HF_CHECKPOINT_FILENAME = "pretraining/TinyMyo/TinyMyo.safetensors"
HF_CONFIG_FILENAME = "pretraining/TinyMyo/config.json"

