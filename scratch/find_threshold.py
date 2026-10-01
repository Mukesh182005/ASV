"""
Deep analysis of ALL recorded REST and HELLO files to find the precise threshold
that completely separates the two states with zero overlap.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.utils.filters import apply_standard_emg_filter

WINDOW_SIZE = settings.WINDOW_SIZE  # 128 samples
STEP_SIZE = settings.STEP_SIZE      # 64 samples

def get_all_windowed_rms(label):
    files = list((settings.RAW_DATA_DIR / f"S01/{label}").glob("*.csv"))
    all_rms = []
    for f in files:
        df = pd.read_csv(f)
        ch_col = [c for c in df.columns if c.startswith('ch')][0]
        raw = df[ch_col].values.astype(float)
        
        filtered = apply_standard_emg_filter(raw, settings.SAMPLING_RATE_HZ)
        
        for start in range(0, len(filtered) - WINDOW_SIZE + 1, STEP_SIZE):
            window = filtered[start:start + WINDOW_SIZE]
            rms = float(np.sqrt(np.mean(window**2)))
            all_rms.append(rms)
    return np.array(all_rms)

print(f"Window size: {WINDOW_SIZE} samples | Step: {STEP_SIZE} samples")
print(f"Sampling rate: {settings.SAMPLING_RATE_HZ} Hz")
print()

rest_rms = get_all_windowed_rms("rest")
hello_rms = get_all_windowed_rms("hello")

print(f"=== REST ({len(rest_rms)} windows from 20 files) ===")
print(f"  Min: {np.min(rest_rms):.1f}")
print(f"  Max: {np.max(rest_rms):.1f}")
print(f"  Mean: {np.mean(rest_rms):.1f}")
print(f"  Median: {np.median(rest_rms):.1f}")
print(f"  P90: {np.percentile(rest_rms, 90):.1f}")
print(f"  P95: {np.percentile(rest_rms, 95):.1f}")
print(f"  P99: {np.percentile(rest_rms, 99):.1f}")
print()

print(f"=== HELLO ({len(hello_rms)} windows from 20 files) ===")
print(f"  Min: {np.min(hello_rms):.1f}")
print(f"  Max: {np.max(hello_rms):.1f}")
print(f"  Mean: {np.mean(hello_rms):.1f}")
print(f"  Median: {np.median(hello_rms):.1f}")
print(f"  P10: {np.percentile(hello_rms, 10):.1f}")
print(f"  P5:  {np.percentile(hello_rms, 5):.1f}")
print(f"  P1:  {np.percentile(hello_rms, 1):.1f}")
print()

# Find the clean separation point
rest_max = np.percentile(rest_rms, 99)
hello_min = np.percentile(hello_rms, 1)

print(f"=== SEPARATION ANALYSIS ===")
print(f"  REST 99th percentile (worst-case noise): {rest_max:.1f}")
print(f"  HELLO 1st percentile (weakest movement): {hello_min:.1f}")

if hello_min > rest_max:
    clean_threshold = (rest_max + hello_min) / 2
    print(f"  GAP: {hello_min - rest_max:.1f} units of clean separation!")
    print(f"  OPTIMAL THRESHOLD: {clean_threshold:.1f}")
else:
    overlap = rest_max - hello_min
    print(f"  WARNING: Overlap of {overlap:.1f} units — some windows share RMS range.")
    # Use the midpoint of means as a reasonable threshold
    midpoint = (np.mean(rest_rms) + np.mean(hello_rms)) / 2
    print(f"  BEST-EFFORT THRESHOLD (midpoint of means): {midpoint:.1f}")

print()
print(f"=== WHAT BASELINE MULTIPLIER IS NEEDED? ===")
rest_median = np.median(rest_rms)
print(f"  REST median (live baseline): ~{rest_median:.1f}")
if hello_min > rest_max:
    print(f"  Multiplier to exceed REST max: {rest_max / rest_median:.2f}x")
    print(f"  Multiplier to catch weakest HELLO: {hello_min / rest_median:.2f}x")
    print(f"  IDEAL MULTIPLIER: {clean_threshold / rest_median:.2f}x")
