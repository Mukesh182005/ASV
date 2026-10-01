"""Preprocessing pipeline for TinyMyo pretrained model.

Transforms raw EMG from our AD8232/ADS1115 hardware into the format
expected by TinyMyo: resampled to 2kHz, filtered, normalized, windowed.

Key transformations documented:
1. DC offset removal
2. Notch filter (50Hz powerline)
3. Bandpass filter (10-200 Hz)
4. Resampling from ~475 Hz to 2000 Hz (cubic interpolation)
5. Z-score normalization per trial
6. Windowing into 1000-sample segments
"""
import numpy as np
import logging
from scipy import signal as scipy_signal
from typing import List, Tuple, Optional

from ml.pretrained.config import (
    OUR_SAMPLING_RATE_HZ,
    TINYMYO_TARGET_SAMPLING_RATE_HZ,
    TINYMYO_WINDOW_SIZE,
    WINDOW_STEP,
    BANDPASS_LOW_HZ,
    BANDPASS_HIGH_HZ,
    NOTCH_FREQ_HZ,
    NORMALIZE_METHOD,
)

logger = logging.getLogger(__name__)


def remove_dc_offset(data: np.ndarray) -> np.ndarray:
    """Remove DC offset (mean) from each channel."""
    return data - np.mean(data, axis=0)


def apply_notch_filter(
    data: np.ndarray, fs: float, freq: float = NOTCH_FREQ_HZ, Q: float = 30.0
) -> np.ndarray:
    """Apply notch filter to remove powerline interference."""
    nyquist = fs / 2.0
    if freq >= nyquist:
        logger.warning(f"Notch freq {freq} Hz >= Nyquist {nyquist} Hz, skipping")
        return data
    w0 = freq / nyquist
    b, a = scipy_signal.iirnotch(w0, Q)
    return scipy_signal.filtfilt(b, a, data, axis=0)


def apply_bandpass_filter(
    data: np.ndarray,
    fs: float,
    lowcut: float = BANDPASS_LOW_HZ,
    highcut: float = BANDPASS_HIGH_HZ,
    order: int = 4,
) -> np.ndarray:
    """Apply Butterworth bandpass filter."""
    nyquist = fs / 2.0
    if highcut >= nyquist:
        highcut = nyquist - 1
        logger.warning(f"Adjusted highcut to {highcut} Hz for Nyquist safety")
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = scipy_signal.butter(order, [low, high], btype="band")
    return scipy_signal.filtfilt(b, a, data, axis=0)


def resample_signal(
    data: np.ndarray,
    original_fs: float,
    target_fs: float,
) -> np.ndarray:
    """Resample EMG signal from original_fs to target_fs.

    Uses scipy.signal.resample_poly for integer-ratio resampling
    approximation, which applies an anti-aliasing FIR filter.

    IMPORTANT NOTE: Upsampling from 475 Hz to 2000 Hz does NOT add
    new information. It interpolates between existing samples to make
    the temporal representation compatible with TinyMyo's learned
    patch tokenization. This is a standard and valid signal processing
    technique for model compatibility.
    """
    if abs(original_fs - target_fs) < 1.0:
        return data  # No resampling needed

    # Find good integer ratio approximation
    # 2000/475 ≈ 4.21 → use 400/95 = 4.2105...
    from math import gcd
    # Use rational approximation
    up = int(target_fs)
    down = int(original_fs)
    g = gcd(up, down)
    up //= g
    down //= g

    logger.debug(f"Resampling: up={up}, down={down} (ratio={up/down:.4f})")

    resampled = scipy_signal.resample_poly(data, up, down, axis=0)
    return resampled


def normalize_signal(data: np.ndarray, method: str = NORMALIZE_METHOD) -> np.ndarray:
    """Normalize EMG signal.

    Z-score: subtract mean, divide by std.
    This ensures the signal amplitude is standardized regardless
    of electrode impedance or gain differences.
    """
    if method == "zscore":
        mean = np.mean(data, axis=0)
        std = np.std(data, axis=0)
        std = np.where(std < 1e-8, 1.0, std)  # Prevent division by zero
        return (data - mean) / std
    elif method == "minmax":
        mn = np.min(data, axis=0)
        mx = np.max(data, axis=0)
        rng = mx - mn
        rng = np.where(rng < 1e-8, 1.0, rng)
        return (data - mn) / rng
    else:
        return data


def preprocess_trial(
    raw_signal: np.ndarray,
    actual_fs: float = OUR_SAMPLING_RATE_HZ,
    target_fs: float = TINYMYO_TARGET_SAMPLING_RATE_HZ,
) -> np.ndarray:
    """Full preprocessing pipeline for a single trial.

    Args:
        raw_signal: (n_samples, n_channels) raw EMG data
        actual_fs: actual sampling rate of the recording
        target_fs: target sampling rate for the model

    Returns:
        processed: (n_samples_resampled, n_channels) preprocessed signal
    """
    if raw_signal.ndim == 1:
        raw_signal = raw_signal.reshape(-1, 1)

    # Step 1: DC offset removal
    data = remove_dc_offset(raw_signal)

    # Step 2: Notch filter at native rate
    data = apply_notch_filter(data, fs=actual_fs)

    # Step 3: Bandpass filter at native rate
    data = apply_bandpass_filter(data, fs=actual_fs)

    # Step 4: Resample to target rate
    data = resample_signal(data, original_fs=actual_fs, target_fs=target_fs)

    # Step 5: Z-score normalization
    data = normalize_signal(data)

    return data


def extract_windows(
    processed_signal: np.ndarray,
    window_size: int = TINYMYO_WINDOW_SIZE,
    step_size: int = WINDOW_STEP,
) -> List[np.ndarray]:
    """Extract fixed-length windows from a preprocessed signal.

    Args:
        processed_signal: (n_samples, n_channels) preprocessed data
        window_size: number of samples per window (default 1000)
        step_size: stride between windows (default 500 for 50% overlap)

    Returns:
        List of (window_size, n_channels) arrays
    """
    n_samples = processed_signal.shape[0]
    windows = []

    if n_samples < window_size:
        # Pad with zeros if trial is too short after resampling
        padded = np.zeros((window_size, processed_signal.shape[1]))
        padded[:n_samples, :] = processed_signal
        windows.append(padded)
        logger.warning(
            f"Trial too short ({n_samples} < {window_size}), zero-padded"
        )
    else:
        for start in range(0, n_samples - window_size + 1, step_size):
            window = processed_signal[start : start + window_size]
            windows.append(window)

    return windows


def preprocess_and_window(
    raw_signal: np.ndarray,
    actual_fs: float = OUR_SAMPLING_RATE_HZ,
) -> List[np.ndarray]:
    """Convenience: preprocess + window extraction in one call.

    Args:
        raw_signal: (n_samples, n_channels) raw EMG

    Returns:
        List of (window_size, n_channels) preprocessed windows
    """
    processed = preprocess_trial(raw_signal, actual_fs=actual_fs)
    return extract_windows(processed)
