import glob
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, '.')
from ml.refined.utterance_features import extract, signal_health

files = glob.glob('datasets/custom_silent_speech/raw/**/*.csv', recursive=True)
print(f"Total CSVs found: {len(files)}")

stats_by_label = {}
for f in sorted(files):
    p = Path(f)
    label = p.parent.name
    df = pd.read_csv(f)
    ch_col = [c for c in df.columns if 'channel' in c or 'ch' in c][0]
    counts = df[ch_col].values
    sh = signal_health(counts)
    feats = extract(counts)
    if label not in stats_by_label:
        stats_by_label[label] = []
    stats_by_label[label].append({
        'base': sh['baseline_mv'],
        'pp': sh['pp_mv'],
        'status': sh['status'],
        'rms': feats[0],
        'mav': feats[1],
        'wl': feats[2],
        'active_frac': feats[10],
        'n_bursts': feats[12]
    })

for label, lst in stats_by_label.items():
    df_lab = pd.DataFrame(lst)
    b_mean = df_lab['base'].mean()
    pp_mean = df_lab['pp'].mean()
    rms_mean = df_lab['rms'].mean()
    wl_mean = df_lab['wl'].mean()
    act_mean = df_lab['active_frac'].mean()
    b_cnt = df_lab['n_bursts'].mean()
    print(f"\n=== LABEL: {label.upper()} (n={len(lst)}) ===")
    print(f"  Baseline: {b_mean:.1f} mV | PP: {pp_mean:.1f} mV")
    print(f"  RMS: {rms_mean:.2f} mV | WL: {wl_mean:.1f}")
    print(f"  Active Frac: {act_mean:.2f} | Bursts: {b_cnt:.1f}")
    print(f"  Status: {df_lab['status'].value_counts().to_dict()}")
