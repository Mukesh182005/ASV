import sys
from pathlib import Path
REPO_ROOT = Path('.').resolve()
sys.path.insert(0, str(REPO_ROOT))

import json, glob
from datetime import datetime
import numpy as np
from scipy import signal as sps
from sklearn.metrics import accuracy_score, classification_report
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder, RobustScaler
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC

from tools.session_eval import load_counts_csv, assign_sessions, FS_DEFAULT
from ml.refined.utterance_features import preprocess, UV_PER_LSB

DATA_DIR = REPO_ROOT / "datasets" / "custom_silent_speech" / "raw"

def extract_advanced_features(counts, fs=FS_DEFAULT):
    counts = np.asarray(counts, dtype=float)
    if counts.size < 32:
        return np.zeros(40, dtype=float)
    
    xf, env = preprocess(counts, fs)
    n = xf.size

    # --- 1. Teager-Kaiser Energy Operator (TKEO) for robust EMG onset detection ---
    # TKEO: psi(x[n]) = x[n]^2 - x[n-1]*x[n+1]
    tkeo = np.zeros_like(xf)
    tkeo[1:-1] = xf[1:-1]**2 - xf[:-2] * xf[2:]
    tkeo = np.clip(tkeo, 0, None)
    # Smooth TKEO
    b, a = sps.butter(2, 10.0 / (fs / 2.0), btype="low")
    tkeo_env = np.clip(sps.filtfilt(b, a, tkeo), 0, None)
    
    # Active detection via TKEO and envelope
    baseline_med = np.median(env)
    baseline_mad = np.median(np.abs(env - baseline_med)) + 1e-9
    threshold = baseline_med + 2.5 * baseline_mad
    active = (env > threshold) | (tkeo_env > np.percentile(tkeo_env, 75))
    
    # --- 2. Scale-Invariant Temporal Shape Features ---
    # Max envelope & total energy
    env_max = float(np.max(env)) + 1e-9
    env_norm = env / env_max  # Normalized to 0..1 peak amplitude! Invariant to donning!
    
    # Energy quantiles in time (0 to 1)
    cum_energy = np.cumsum(env**2)
    tot_energy = cum_energy[-1] + 1e-12
    t10 = float(np.searchsorted(cum_energy, 0.10 * tot_energy) / n)
    t25 = float(np.searchsorted(cum_energy, 0.25 * tot_energy) / n)
    t50 = float(np.searchsorted(cum_energy, 0.50 * tot_energy) / n)
    t75 = float(np.searchsorted(cum_energy, 0.75 * tot_energy) / n)
    t90 = float(np.searchsorted(cum_energy, 0.90 * tot_energy) / n)
    energy_spread = t90 - t10  # Duration of the main energy window
    
    # --- 3. 8-Bin Normalized Profile ---
    # Sample the normalized envelope across 8 temporal bins
    bin_size = n // 8
    profile = [float(np.mean(env_norm[i*bin_size:(i+1)*bin_size])) for i in range(8)]
    
    # Ratio of front-half energy to back-half energy
    front_energy = float(np.sum(env[:n//2]))
    back_energy = float(np.sum(env[n//2:]))
    front_back_ratio = float((front_energy - back_energy) / (front_energy + back_energy + 1e-9))
    
    # --- 4. Hjorth Parameters (Scale Invariant Bio-signal Features) ---
    # Activity = var(x)
    # Mobility = sqrt(var(dx) / var(x)) -> mean frequency proxy
    # Complexity = Mobility(dx) / Mobility(x) -> frequency variation proxy
    var_x = float(np.var(xf)) + 1e-12
    d1 = np.diff(xf)
    var_d1 = float(np.var(d1)) + 1e-12
    d2 = np.diff(d1)
    var_d2 = float(np.var(d2)) + 1e-12
    
    mobility_x = float(np.sqrt(var_d1 / var_x))
    mobility_d1 = float(np.sqrt(var_d2 / var_d1))
    complexity = float(mobility_d1 / (mobility_x + 1e-9))
    
    # --- 5. Frequency Subband Energy Ratios ---
    # Invariant to overall gain, measures frequency composition
    freqs = np.fft.rfftfreq(n, d=1.0/fs)
    fft_mag = np.abs(np.fft.rfft(xf))**2
    total_pow = np.sum(fft_mag) + 1e-12
    
    band1 = float(np.sum(fft_mag[(freqs >= 15) & (freqs < 45)]) / total_pow)
    band2 = float(np.sum(fft_mag[(freqs >= 45) & (freqs < 85)]) / total_pow)
    band3 = float(np.sum(fft_mag[(freqs >= 85) & (freqs < 140)]) / total_pow)
    band4 = float(np.sum(fft_mag[(freqs >= 140) & (freqs < 200)]) / total_pow)
    
    spectral_centroid = float(np.sum(freqs * fft_mag) / total_pow)
    
    # Spectral flatness & entropy
    p_spec = fft_mag / total_pow
    spec_entropy = float(-np.sum(p_spec * np.log(p_spec + 1e-12)) / np.log(len(p_spec)))
    
    # --- 6. Envelope Burst Dynamics ---
    onsets = np.where(np.diff(active.astype(int)) == 1)[0]
    n_bursts = float(len(onsets))
    active_frac = float(active.mean())
    active_dur = float(active.sum() / fs)
    
    # Normalized waveform length (independent of scale)
    diff = np.diff(xf)
    rms = float(np.sqrt(np.mean(xf ** 2))) + 1e-9
    norm_wl = float(np.sum(np.abs(diff)) / (rms * n))
    
    # Zero crossings and slope sign changes
    signs = np.sign(xf); signs[signs == 0] = 1
    zcr = float(np.sum(np.abs(np.diff(signs)) > 0) / max(n - 1, 1))
    dsign = np.sign(diff); dsign[dsign == 0] = 1
    ssc = float(np.sum(np.abs(np.diff(dsign)) > 0) / max(n - 2, 1))

    # Envelope centroid & peak location
    idx = np.arange(n)
    env_centroid = float(np.sum(idx * env_norm) / (np.sum(env_norm) + 1e-9) / n)
    peak_time = float(np.argmax(env) / n)
    
    features = [
        # Scale-invariant shape & dynamics
        env_centroid, peak_time, front_back_ratio,
        t10, t25, t50, t75, t90, energy_spread,
        # 8-bin profile
        *profile,
        # Hjorth parameters
        mobility_x, complexity,
        # Frequency band ratios
        band1, band2, band3, band4, spectral_centroid, spec_entropy,
        # Activity & complexity
        n_bursts, active_frac, active_dur, norm_wl, zcr, ssc,
        # Log relative energy (compressed scale)
        float(np.log1p(rms)), float(np.log1p(env_max))
    ]
    return np.array(features, dtype=float)

# Load dataset
raw_files = sorted(glob.glob(str(DATA_DIR / "**" / "*.csv"), recursive=True))
X_adv, y, ts = [], [], []
for csv in raw_files:
    p = Path(csv)
    meta = p.with_name(p.stem + "_meta.json")
    if meta.exists():
        stamp = json.load(open(meta))["timestamp"]
    else:
        stamp = "_".join(p.stem.split("_")[1:3])
    try:
        when = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
    except ValueError:
        continue
    counts = load_counts_csv(csv)
    X_adv.append(extract_advanced_features(counts))
    y.append(p.parent.name)
    ts.append(when)

X_adv = np.array(X_adv)
y = np.array(y)
ts = np.array(ts)

sess = assign_sessions(ts)
le = LabelEncoder()
yy = le.fit_transform(y)
all_words = set(y)
order = sorted(set(sess), key=lambda s: ts[sess == s].min())
valid = [s for s in order if set(y[sess == s]) == all_words]

print(f"Dataset: {len(X_adv)} recordings, {X_adv.shape[1]} advanced features")

models = {
    'ExtraTrees': ExtraTreesClassifier(n_estimators=400, max_features="sqrt", random_state=42),
    'RandomForest': RandomForestClassifier(n_estimators=400, max_depth=8, random_state=42),
    'SVM_rbf_norm': make_pipeline(RobustScaler(), SVC(kernel='rbf', C=3.0, gamma='scale')),
    'Ensemble_ET_RF': VotingClassifier(
        estimators=[
            ('et', ExtraTreesClassifier(n_estimators=400, random_state=42)),
            ('rf', RandomForestClassifier(n_estimators=400, max_depth=8, random_state=42)),
            ('svm', make_pipeline(RobustScaler(), SVC(kernel='rbf', C=3.0, probability=True, random_state=42)))
        ],
        voting='soft'
    )
}

for name, m in models.items():
    accs = []
    trues, preds = [], []
    for s in valid:
        te = sess == s
        clf = m.fit(X_adv[~te], yy[~te])
        p = clf.predict(X_adv[te])
        accs.append(accuracy_score(yy[te], p))
        trues.append(yy[te])
        preds.append(p)
    print(f"  {name:18s} Out-of-session accuracy: {np.mean(accs):.1%} (Sessions: {[round(a, 3) for a in accs]})")

