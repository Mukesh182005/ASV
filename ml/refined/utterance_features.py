"""
ASV — Refined utterance-level feature extraction
================================================

The original pipeline slides a 256 ms window across a 2 s recording and labels
*every* window with the utterance label. Most windows in a "hello" clip are
actually silence (before/after the articulation), so the per-window classifier
is trained on heavily mislabelled data — that is the main reason its
cross-validated accuracy sat at ~48 %.

This module treats one recording (one articulated word) as ONE sample and
extracts a compact, physically-meaningful feature vector describing the whole
utterance: how much energy, what the amplitude envelope looks like over time
(shape, number of bursts, where the peak sits), and the spectral content of the
active portion. Those are the cues that actually differ between silently
articulated words on a single ECG-band EMG channel.

The SAME function is used at training time and inference time, so there is no
train/serve skew.
"""
from __future__ import annotations
import numpy as np
from scipy import signal as sps

# Hardware constants — must match firmware / ml.config.settings
FS_DEFAULT = 860.0
UV_PER_LSB = 125.0          # gain index 1: +/-4.096 V

# Signal-health thresholds — same numbers used to diagnose the railed-electrode
# bug during dataset collection (see test.png / clench_test.png in project
# history). Centralised here so every live tool (plot_words.py, predict_live.py,
# the backend) agrees on what "good contact" means.
BASELINE_TARGET_MV = 1635.0     # mid-supply (Vcc/2) at gain index 1
BASELINE_TOLERANCE_MV = 700.0   # outside [935, 2335] mV -> railed / DC-offset fault
MIN_HEALTHY_PP_MV = 3.0         # below this over ~1s -> flat / electrode not making contact


def signal_health(counts, uv_per_lsb=UV_PER_LSB):
    """Cheap pre-flight check on raw ADC counts: is this electrode contact usable?

    Returns dict(baseline_mv, pp_mv, status, ok). status is one of
    NO_DATA / RAILED_OR_OFFSET / FLAT / OK.
    """
    counts = np.asarray(counts, dtype=float)
    if counts.size == 0:
        return {"baseline_mv": 0.0, "pp_mv": 0.0, "status": "NO_DATA", "ok": False}
    mv = counts * uv_per_lsb / 1000.0
    baseline = float(np.mean(mv))
    pp = float(np.ptp(mv))
    if abs(baseline - BASELINE_TARGET_MV) > BASELINE_TOLERANCE_MV:
        status = "RAILED_OR_OFFSET"
    elif pp < MIN_HEALTHY_PP_MV:
        status = "FLAT"
    else:
        status = "OK"
    return {"baseline_mv": round(baseline, 1), "pp_mv": round(pp, 2),
            "status": status, "ok": status == "OK"}

# Ordered feature names — the model's schema depends on this order.
FEATURE_NAMES = [
    "rms", "mav", "wl", "zcr", "ssc",
    "env_mean", "env_max", "env_std", "env_peakiness", "iemg",
    "active_frac", "active_dur_s", "n_bursts",
    "env_centroid", "peak_time", "env_skew",
    "mean_freq", "median_freq", "spec_entropy",
]


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def _notch(x, fs, f0=50.0, q=30.0):
    if f0 >= fs / 2:
        return x
    b, a = sps.iirnotch(f0 / (fs / 2), q)
    return sps.filtfilt(b, a, x)


def _bandpass(x, fs, lo=10.0, hi=200.0, order=4):
    ny = fs / 2.0
    hi = min(hi, ny - 1.0)
    b, a = sps.butter(order, [lo / ny, hi / ny], btype="band")
    return sps.filtfilt(b, a, x)


def _envelope(xf, fs, cutoff=8.0):
    """Linear envelope: full-wave rectify then low-pass."""
    b, a = sps.butter(2, cutoff / (fs / 2.0), btype="low")
    return np.clip(sps.filtfilt(b, a, np.abs(xf)), 0, None)


def preprocess(counts, fs=FS_DEFAULT):
    """Raw ADC counts -> (filtered mV signal, envelope). DC removed."""
    x = (np.asarray(counts, dtype=float) - np.mean(counts)) * UV_PER_LSB / 1000.0
    xf = _bandpass(_notch(x, fs), fs)
    env = _envelope(xf, fs)
    return xf, env


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
def extract(counts, fs=FS_DEFAULT):
    """Return an ordered feature vector (np.ndarray) for one utterance.

    `counts` is a 1-D array of raw ADC counts (channel_0) for the whole
    recording. Length-agnostic; robust to short/flat signals.
    """
    counts = np.asarray(counts, dtype=float)
    if counts.size < 32:
        return np.zeros(len(FEATURE_NAMES), dtype=float)

    xf, env = preprocess(counts, fs)
    n = xf.size

    # --- time-domain amplitude ---
    rms = float(np.sqrt(np.mean(xf ** 2)))
    mav = float(np.mean(np.abs(xf)))
    diff = np.diff(xf)
    wl = float(np.sum(np.abs(diff)))
    signs = np.sign(xf); signs[signs == 0] = 1
    zcr = float(np.sum(np.abs(np.diff(signs)) > 0) / max(n - 1, 1))
    dsign = np.sign(diff); dsign[dsign == 0] = 1
    ssc = float(np.sum(np.abs(np.diff(dsign)) > 0) / max(n - 2, 1))

    # --- envelope amplitude ---
    env_mean = float(env.mean())
    env_max = float(env.max())
    env_std = float(env.std())
    env_p90 = float(np.percentile(env, 90))
    env_peakiness = float(env_max / (env_p90 + 1e-9))
    iemg = float(np.sum(env) / fs)                     # integrated envelope (mV*s)

    # --- envelope shape / articulation dynamics ---
    med = np.median(env)
    mad = np.median(np.abs(env - med)) + 1e-9
    thr = med + 3.0 * mad
    active = env > thr
    active_frac = float(active.mean())
    active_dur_s = float(active.sum() / fs)
    # count separate bursts (>= ~30 ms) as a syllable proxy
    min_gap = int(0.03 * fs)
    onsets = np.where(np.diff(active.astype(int)) == 1)[0]
    n_bursts = int(len(onsets))
    if n_bursts > 1:
        # merge bursts closer than min_gap
        keep = [onsets[0]]
        for o in onsets[1:]:
            if o - keep[-1] > min_gap:
                keep.append(o)
        n_bursts = len(keep)

    idx = np.arange(n)
    esum = np.sum(env) + 1e-9
    env_centroid = float(np.sum(idx * env) / esum / n)          # 0..1 time centre of mass
    peak_time = float(np.argmax(env) / n)                        # 0..1 location of peak
    # envelope skew (asymmetry of the energy in time)
    c = env_centroid * n
    env_skew = float(np.sum(((idx - c) ** 3) * env) / esum / (env.std() * n + 1e-9) ** 3 * n)
    env_skew = float(np.clip(env_skew, -50, 50))

    # --- spectral (on the active portion if present, else whole signal) ---
    seg = xf[active] if active.sum() >= 64 else xf
    freqs = np.fft.rfftfreq(seg.size, d=1.0 / fs)
    mag = np.abs(np.fft.rfft(seg))
    pmag = mag / (mag.sum() + 1e-12)
    mean_freq = float(np.sum(freqs * pmag))
    cumpow = np.cumsum(mag)
    half = cumpow[-1] / 2.0 if cumpow[-1] > 0 else 0.0
    mi = np.where(cumpow >= half)[0]
    median_freq = float(freqs[mi[0]]) if mi.size else 0.0
    spec_entropy = float(-np.sum(pmag * np.log(pmag + 1e-12)) / np.log(len(pmag) + 1e-12))

    return np.array([
        rms, mav, wl, zcr, ssc,
        env_mean, env_max, env_std, env_peakiness, iemg,
        active_frac, active_dur_s, n_bursts,
        env_centroid, peak_time, env_skew,
        mean_freq, median_freq, spec_entropy,
    ], dtype=float)


def load_counts_csv(path):
    """Load channel_0 counts from a collect_emg.py CSV (timestamp_us,channel_0)."""
    import pandas as pd
    df = pd.read_csv(path)
    ch_col = [c for c in df.columns if c != df.columns[0]][0]
    return df[ch_col].to_numpy(dtype=float)
