import glob
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, '.')
from ml.refined.utterance_features import FS_DEFAULT, UV_PER_LSB, _notch, _bandpass

files = glob.glob('datasets/custom_silent_speech/raw/**/*.csv', recursive=True)

for label in ["rest", "yes", "hello", "no"]:
    lab_files = [f for f in files if Path(f).parent.name == label]
    if not lab_files:
        continue
    df = pd.read_csv(lab_files[0])
    ch_col = [c for c in df.columns if 'channel' in c or 'ch' in c][0]
    counts = df[ch_col].values
    
    # Raw mV
    raw_mv = (counts - np.mean(counts)) * UV_PER_LSB / 1000.0
    
    # FFT
    freqs = np.fft.rfftfreq(len(raw_mv), d=1.0/FS_DEFAULT)
    fft_mag = np.abs(np.fft.rfft(raw_mv))
    
    # Find top 3 peak frequencies
    top_indices = np.argsort(fft_mag)[::-1][:5]
    top_freqs = [(round(freqs[i], 1), round(fft_mag[i], 1)) for i in top_indices if freqs[i] > 1.0]
    
    print(f"=== {label.upper()} ({lab_files[0]}) ===")
    print(f"  Raw Peak-to-Peak: {np.ptp(raw_mv):.1f} mV | Raw RMS: {np.sqrt(np.mean(raw_mv**2)):.2f} mV")
    print(f"  Top Frequencies (Hz, mag): {top_freqs[:4]}")
