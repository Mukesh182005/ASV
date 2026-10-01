"""Dataset loader for pretrained model experiments.

Loads our real HELLO/REST CSV recordings, applies TinyMyo-specific
preprocessing, and provides trial-level grouping for leakage-free
cross-validation.
"""
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import torch
from torch.utils.data import Dataset

from ml.pretrained.config import (
    RAW_DATA_DIR,
    LABEL_MAP,
    OUR_SAMPLING_RATE_HZ,
)
from ml.pretrained.preprocessing import preprocess_and_window

logger = logging.getLogger(__name__)


def discover_trials(data_dir: Optional[Path] = None) -> List[Dict]:
    """Discover all CSV trial recordings with metadata.

    Returns list of dicts with keys: path, label, subject, trial_id,
    actual_fs, n_samples, is_simulated.
    """
    if data_dir is None:
        data_dir = RAW_DATA_DIR

    data_dir = Path(data_dir)
    trials = []

    for label_dir in sorted(data_dir.iterdir()):
        if not label_dir.is_dir():
            continue
        label = label_dir.name.lower()
        if label not in LABEL_MAP:
            logger.info(f"Skipping unknown label directory: {label}")
            continue

        for csv_path in sorted(label_dir.glob("*.csv")):
            # Skip metadata files
            if "_meta" in csv_path.stem:
                continue

            # Load metadata if available
            meta_path = csv_path.with_name(csv_path.stem + "_meta.json")
            meta = {}
            if meta_path.exists():
                try:
                    with open(meta_path) as f:
                        meta = json.load(f)
                except Exception:
                    pass

            # Skip simulated data
            if meta.get("is_simulated", False):
                logger.warning(f"Skipping simulated file: {csv_path.name}")
                continue

            trial_id = csv_path.stem  # Unique ID for grouping
            actual_fs = meta.get(
                "actual_sampling_rate_hz", OUR_SAMPLING_RATE_HZ
            )

            trials.append({
                "path": csv_path,
                "label": label,
                "subject": meta.get("subject", "S01"),
                "trial_id": trial_id,
                "actual_fs": actual_fs,
                "n_samples": meta.get("n_samples", 0),
            })

    logger.info(
        f"Discovered {len(trials)} trials: "
        + ", ".join(
            f"{l}={sum(1 for t in trials if t['label'] == l)}"
            for l in sorted(set(t["label"] for t in trials))
        )
    )
    return trials


def load_trial_signal(trial: Dict) -> np.ndarray:
    """Load raw EMG signal from a CSV file.

    Returns: (n_samples, n_channels) array of raw ADC values.
    """
    df = pd.read_csv(trial["path"])

    # Find EMG columns
    emg_cols = sorted([
        c for c in df.columns
        if c.startswith("ch") or c.startswith("channel_")
    ])

    if not emg_cols:
        raise ValueError(f"No EMG columns found in {trial['path']}")

    signal = df[emg_cols].values.astype(np.float64)
    if signal.ndim == 1:
        signal = signal.reshape(-1, 1)

    return signal


class PretrainedEMGDataset(Dataset):
    """PyTorch dataset for TinyMyo fine-tuning.

    Each item is a preprocessed window with its label and trial_id.
    Windows from the same trial share the same trial_id for GroupKFold.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        trial_ids: Optional[List[str]] = None,
    ):
        """
        Args:
            data_dir: Path to raw data directory (default: config RAW_DATA_DIR)
            trial_ids: If given, only load these specific trial IDs (for splits)
        """
        self.trials = discover_trials(data_dir)
        if trial_ids is not None:
            self.trials = [t for t in self.trials if t["trial_id"] in trial_ids]

        # Preprocess all trials and collect windows
        self.windows: List[torch.Tensor] = []
        self.labels: List[int] = []
        self.trial_ids: List[str] = []
        self.trial_labels: List[str] = []

        self._load_all()

    def _load_all(self):
        """Load and preprocess all trials."""
        for trial in self.trials:
            try:
                raw = load_trial_signal(trial)
                windows = preprocess_and_window(
                    raw, actual_fs=trial["actual_fs"]
                )

                label_idx = LABEL_MAP[trial["label"]]
                for w in windows:
                    # Shape: (n_channels, window_size) for PyTorch conv1d
                    w_tensor = torch.from_numpy(w.T).float()  # (C, T)
                    self.windows.append(w_tensor)
                    self.labels.append(label_idx)
                    self.trial_ids.append(trial["trial_id"])
                    self.trial_labels.append(trial["label"])

            except Exception as e:
                logger.warning(f"Error processing {trial['path'].name}: {e}")

        logger.info(
            f"Loaded {len(self.windows)} windows from "
            f"{len(set(self.trial_ids))} trials"
        )

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, str]:
        return self.windows[idx], self.labels[idx], self.trial_ids[idx]

    def get_groups(self) -> np.ndarray:
        """Return trial group IDs for GroupKFold."""
        return np.array(self.trial_ids)

    def get_labels(self) -> np.ndarray:
        """Return integer labels."""
        return np.array(self.labels)

    def get_summary(self) -> Dict:
        """Return dataset statistics."""
        labels = np.array(self.labels)
        trial_ids = np.array(self.trial_ids)
        return {
            "n_windows": len(self.windows),
            "n_trials": len(set(self.trial_ids)),
            "n_hello_windows": int(np.sum(labels == LABEL_MAP["hello"])),
            "n_rest_windows": int(np.sum(labels == LABEL_MAP["rest"])),
            "n_hello_trials": len(set(
                tid for tid, lab in zip(self.trial_ids, self.trial_labels)
                if lab == "hello"
            )),
            "n_rest_trials": len(set(
                tid for tid, lab in zip(self.trial_ids, self.trial_labels)
                if lab == "rest"
            )),
            "window_shape": tuple(self.windows[0].shape) if self.windows else None,
        }
