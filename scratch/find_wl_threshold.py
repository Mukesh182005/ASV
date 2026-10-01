"""
Deep analysis to find the precise WL threshold that separates REST from HELLO.
WL (Waveform Length) = sum of absolute differences between consecutive samples.
It captures the "busyness" of the signal, not just amplitude.
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

def get_all_windowed_features(label):
    files = list((settings.RAW_DATA_DIR / f"S01/{label}").glob("*.csv"))
    all_rms = []
    all_wl = []
    all_mav = []
    for f in files:
        df = pd.read_csv(f)
        ch_col = [c for c in df.columns if c.startswith('ch')][0]
        raw = df[ch_col].values.astype(float)
        filtered = apply_standard_emg_filter(raw, settings.SAMPLING_RATE_HZ)
        for start in range(0, len(filtered) - WINDOW_SIZE + 1, STEP_SIZE):
            window = filtered[start:start + WINDOW_SIZE]
            rms = float(np.sqrt(np.mean(window**2)))
            wl = float(np.sum(np.abs(np.diff(window))))
            mav = float(np.mean(np.abs(window)))
            all_rms.append(rms)
            all_wl.append(wl)
            all_mav.append(mav)
    return np.array(all_rms), np.array(all_wl), np.array(all_mav)

rest_rms, rest_wl, rest_mav = get_all_windowed_features("rest")
hello_rms, hello_wl, hello_mav = get_all_windowed_features("hello")

print(f"=== WAVEFORM LENGTH (WL) ===")
print(f"REST  - Min:{np.min(rest_wl):.0f} Mean:{np.mean(rest_wl):.0f} Median:{np.median(rest_wl):.0f} P95:{np.percentile(rest_wl,95):.0f} P99:{np.percentile(rest_wl,99):.0f} Max:{np.max(rest_wl):.0f}")
print(f"HELLO - Min:{np.min(hello_wl):.0f} Mean:{np.mean(hello_wl):.0f} Median:{np.median(hello_wl):.0f} P5:{np.percentile(hello_wl,5):.0f} P1:{np.percentile(hello_wl,1):.0f} Max:{np.max(hello_wl):.0f}")

rest_wl_max = np.percentile(rest_wl, 99)
hello_wl_min = np.percentile(hello_wl, 1)

if hello_wl_min > rest_wl_max:
    wl_threshold = (rest_wl_max + hello_wl_min) / 2
    print(f"\n  WL CLEAN SEPARATION! Gap: {hello_wl_min - rest_wl_max:.0f}")
    print(f"  OPTIMAL WL THRESHOLD: {wl_threshold:.0f}")
else:
    print(f"\n  WL OVERLAP: {rest_wl_max - hello_wl_min:.0f}")
    print(f"  BEST-EFFORT WL THRESHOLD: {(np.mean(rest_wl) + np.mean(hello_wl))/2:.0f}")

print(f"\n=== DUAL-GATE ANALYSIS (Both RMS > T1 AND WL > T2) ===")
# Find combination that minimizes false positives
best_rest_fp = 999
best_threshold_rms = 0
best_threshold_wl = 0
for rms_t in range(800, 2500, 50):
    for wl_t in range(5000, 40000, 500):
        rest_fp = np.sum((rest_rms > rms_t) & (rest_wl > wl_t))  / len(rest_rms)
        hello_fn = np.sum(~((hello_rms > rms_t) & (hello_wl > wl_t))) / len(hello_rms)
        if rest_fp < 0.01 and hello_fn < 0.5 and rest_fp < best_rest_fp:  # <1% false positives
            best_rest_fp = rest_fp
            best_threshold_rms = rms_t
            best_threshold_wl = wl_t

if best_threshold_rms > 0:
    tp = np.sum((hello_rms > best_threshold_rms) & (hello_wl > best_threshold_wl)) / len(hello_rms) * 100
    fp = best_rest_fp * 100
    print(f"  BEST DUAL-GATE: RMS > {best_threshold_rms} AND WL > {best_threshold_wl}")
    print(f"  HELLO detection rate (true pos): {tp:.1f}%")
    print(f"  REST false alarm rate (false pos): {fp:.1f}%")
else:
    print("  Could not find dual gate with < 1% false positives.")
    print(f"  Try single RMS gate: {(np.mean(rest_rms)+np.mean(hello_rms))/2:.0f}")
