import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.config import settings

def check_datasets():
    rest_files = list((settings.RAW_DATA_DIR / "S01/rest").glob("*.csv"))
    hello_files = list((settings.RAW_DATA_DIR / "S01/hello").glob("*.csv"))
    
    def print_stats(name, files):
        print(f"\n--- {name} ({len(files)} files) ---")
        for f in files[:5]: # just print first 5
            df = pd.read_csv(f)
            ch0 = df[[c for c in df.columns if c.startswith('ch')][0]].values
            print(f"{f.name} -> Min: {np.min(ch0):.1f} | Max: {np.max(ch0):.1f} | Std: {np.std(ch0):.1f}")
            
    print_stats("REST", rest_files)
    print_stats("HELLO", hello_files)

if __name__ == "__main__":
    check_datasets()
