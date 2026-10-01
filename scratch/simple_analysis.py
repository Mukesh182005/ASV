import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings
from ml.utils.filters import apply_standard_emg_filter

def simple_analysis():
    rest_file = list((settings.RAW_DATA_DIR / "S01/rest").glob("*.csv"))[0]
    hello_file = list((settings.RAW_DATA_DIR / "S01/hello").glob("*.csv"))[0]
    
    def analyze(f, name):
        df = pd.read_csv(f)
        emg = df[[c for c in df.columns if c.startswith('ch')][0]].values
        filtered = apply_standard_emg_filter(emg, settings.SAMPLING_RATE_HZ)
        
        print(f"\n--- {name} ({f.name}) ---")
        print(f"Raw Min: {np.min(emg):.1f}, Max: {np.max(emg):.1f}, Std: {np.std(emg):.1f}")
        print(f"Filtered RMS: {np.sqrt(np.mean(filtered**2)):.2f}")
        
        # Windowed RMS
        rmss = []
        for i in range(0, len(filtered)-128, 64):
            rmss.append(np.sqrt(np.mean(filtered[i:i+128]**2)))
        print(f"Windowed RMS - Min: {np.min(rmss):.2f}, Max: {np.max(rmss):.2f}, Mean: {np.mean(rmss):.2f}")
        
    analyze(rest_file, "REST")
    analyze(hello_file, "HELLO")

if __name__ == "__main__":
    simple_analysis()
