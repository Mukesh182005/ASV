import sys, glob
from pathlib import Path
REPO_ROOT = Path('.').resolve()
sys.path.insert(0, str(REPO_ROOT))
from tools.session_eval import load, assign_sessions
from ml.refined.utterance_features import signal_health, load_counts_csv
import numpy as np

X, y, ts, files = load()
sess = assign_sessions(ts)

c_indices = [i for i, s in enumerate(sess) if s == 'C']
print(f'Count in C: {len(c_indices)}')

healths = []
for idx in c_indices:
    f = files[idx]
    matching = glob.glob(f'datasets/**/{f}', recursive=True)
    if matching:
        counts = load_counts_csv(matching[0])
        h = signal_health(counts)
        healths.append((y[idx], h['status'], h['pp_mv'], h['baseline_mv']))

statuses = {}
for word, stat, pp, base in healths:
    statuses[stat] = statuses.get(stat, 0) + 1

print('Signal health statuses in Session C:', statuses)
print('Sample entries in C (first 10):')
for word, stat, pp, base in healths[:10]:
    print(f'  {word:6s} | {stat:15s} | pp={pp:6.1f} mV | base={base:6.1f} mV')

print('\nCompare with Session A (first 5):')
a_indices = [i for i, s in enumerate(sess) if s == 'A']
for idx in a_indices[:5]:
    f = files[idx]
    matching = glob.glob(f'datasets/**/{f}', recursive=True)
    counts = load_counts_csv(matching[0])
    h = signal_health(counts)
    print(f'  {y[idx]:6s} | {h["status"]:15s} | pp={h["pp_mv"]:6.1f} mV | base={h["baseline_mv"]:6.1f} mV')

