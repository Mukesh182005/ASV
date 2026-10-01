import glob, pandas as pd, numpy as np
from pathlib import Path
import sys, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from ml.refined.utterance_features import extract, FS_DEFAULT, FEATURE_NAMES

files = sorted(glob.glob('datasets/custom_silent_speech/raw/**/*.csv', recursive=True))

data = []
for f in files:
    label = Path(f).parent.name
    df = pd.read_csv(f)
    ch_col = [c for c in df.columns if 'channel' in c or 'ch' in c][0]
    counts = df[ch_col].values
    feats = extract(counts)
    row = {'file': Path(f).name, 'label': label}
    for idx, name in enumerate(FEATURE_NAMES):
        row[name] = feats[idx]
    data.append(row)

df_all = pd.DataFrame(data)

print("=== MEAN FEATURE VALUES BY WORD ===")
cols_to_show = ['rms', 'mav', 'wl', 'env_max', 'iemg', 'active_frac', 'n_bursts', 'burst_dur_s', 'rise_time_s']
print(df_all.groupby('label')[cols_to_show].mean().round(3))

print("\n=== PER-TRIAL VALUES FOR 'NO' ===")
print(df_all[df_all['label'] == 'no'][['file', 'rms', 'wl', 'active_frac', 'n_bursts']].to_string())

print("\n=== PER-TRIAL VALUES FOR 'REST' ===")
print(df_all[df_all['label'] == 'rest'][['file', 'rms', 'wl', 'active_frac', 'n_bursts']].to_string())

print("\n=== PER-TRIAL VALUES FOR 'YES' ===")
print(df_all[df_all['label'] == 'yes'][['file', 'rms', 'wl', 'active_frac', 'n_bursts']].to_string())
