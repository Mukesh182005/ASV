import glob
import pandas as pd
import numpy as np
from pathlib import Path
import sys, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from ml.refined.utterance_features import FS_DEFAULT, UV_PER_LSB, FEATURE_NAMES, _notch, _bandpass, _envelope
from sklearn.preprocessing import StandardScaler, LabelEncoder, RobustScaler
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC, LinearSVC
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

# Enhanced preprocessing with 50 Hz + 100 Hz notch
def enhanced_preprocess(counts, fs=FS_DEFAULT):
    x = (np.asarray(counts, dtype=float) - np.mean(counts)) * UV_PER_LSB / 1000.0
    # Notch 50 Hz and 100 Hz harmonic
    x_n = _notch(x, fs, f0=50.0, q=25.0)
    x_n = _notch(x_n, fs, f0=100.0, q=25.0)
    # Bandpass 15 Hz to 200 Hz
    xf = _bandpass(x_n, fs, lo=15.0, hi=200.0, order=4)
    env = _envelope(xf, fs)
    return xf, env

def extract_enhanced(counts, fs=FS_DEFAULT):
    counts = np.asarray(counts, dtype=float)
    if counts.size < 32:
        return np.zeros(len(FEATURE_NAMES), dtype=float)
    
    xf, env = enhanced_preprocess(counts, fs)
    n = xf.size

    rms = float(np.sqrt(np.mean(xf ** 2)))
    mav = float(np.mean(np.abs(xf)))
    diff = np.diff(xf)
    wl = float(np.sum(np.abs(diff)))
    signs = np.sign(xf); signs[signs == 0] = 1
    zcr = float(np.sum(np.abs(np.diff(signs)) > 0) / max(n - 1, 1))
    dsign = np.sign(diff); dsign[dsign == 0] = 1
    ssc = float(np.sum(np.abs(np.diff(dsign)) > 0) / max(n - 2, 1))

    env_mean = float(env.mean())
    env_max = float(env.max())
    env_std = float(env.std())
    env_p90 = float(np.percentile(env, 90))
    env_peakiness = float(env_max / (env_p90 + 1e-9))
    iemg = float(np.sum(env) / fs)

    med = np.median(env)
    mad = np.median(np.abs(env - med)) + 1e-9
    thr = med + 3.0 * mad
    active = env > thr
    active_frac = float(active.mean())
    active_dur_s = float(active.sum() / fs)
    
    min_gap = int(0.03 * fs)
    onsets = np.where(np.diff(active.astype(int)) == 1)[0]
    n_bursts = int(len(onsets))
    if n_bursts > 1:
        keep = [onsets[0]]
        for o in onsets[1:]:
            if o - keep[-1] > min_gap:
                keep.append(o)
        n_bursts = len(keep)

    idx = np.arange(n)
    esum = np.sum(env) + 1e-9
    env_centroid = float(np.sum(idx * env) / esum / n)
    peak_time = float(np.argmax(env) / n)
    c = env_centroid * n
    env_skew = float(np.sum(((idx - c) ** 3) * env) / esum / (env.std() * n + 1e-9) ** 3 * n)
    env_skew = float(np.clip(env_skew, -50, 50))

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

    active_int = active.astype(int)
    transitions = np.diff(np.concatenate(([0], active_int, [0])))
    burst_starts = np.where(transitions == 1)[0]
    burst_ends   = np.where(transitions == -1)[0]
    burst_dur_s = 0.0
    rise_time_s = 0.0
    fall_time_s = 0.0
    rise_fall_ratio = 1.0
    if len(burst_starts) > 0 and len(burst_ends) > 0:
        lengths = burst_ends - burst_starts
        bi = int(np.argmax(lengths))
        bs, be = int(burst_starts[bi]), int(burst_ends[bi])
        burst_dur_s = float((be - bs) / fs)
        burst_env = env[bs:be] if be > bs else env
        peak_idx = int(np.argmax(burst_env))
        rise_time_s = float(peak_idx / fs)
        fall_time_s = float((len(burst_env) - peak_idx) / fs)
        rise_fall_ratio = float(rise_time_s / (fall_time_s + 1e-6))
        rise_fall_ratio = float(np.clip(rise_fall_ratio, 0.0, 20.0))

    return np.array([
        rms, mav, wl, zcr, ssc,
        env_mean, env_max, env_std, env_peakiness, iemg,
        active_frac, active_dur_s, n_bursts,
        env_centroid, peak_time, env_skew,
        mean_freq, median_freq, spec_entropy,
        burst_dur_s, rise_time_s, fall_time_s, rise_fall_ratio,
    ], dtype=float)

files = sorted(glob.glob('datasets/custom_silent_speech/raw/**/*.csv', recursive=True))
X = np.array([extract_enhanced(pd.read_csv(f).iloc[:, 1].values, fs=FS_DEFAULT) for f in files])
y = np.array([Path(f).parent.name for f in files])
le = LabelEncoder()
yi = le.fit_transform(y)

print(f"Total recordings: {len(X)}")
print(f"Classes: {le.classes_.tolist()}")

models = {
    "SVM_linear_C1": make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0, probability=True)),
    "SVM_linear_C0.1": make_pipeline(StandardScaler(), SVC(kernel="linear", C=0.1, probability=True)),
    "LDA_shrinkage": make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")),
    "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=500)),
    "SVM_rbf_C1": make_pipeline(StandardScaler(), SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)),
    "SVM_rbf_C5": make_pipeline(StandardScaler(), SVC(kernel="rbf", C=5.0, gamma="scale", probability=True)),
}

best_acc = 0
best_model_name = ""

for name, model in models.items():
    pred = cross_val_predict(model, X, yi, cv=LeaveOneOut())
    acc = accuracy_score(yi, pred)
    print(f"{name:20s} LOO Accuracy: {acc:.1%}")
    if acc > best_acc:
        best_acc = acc
        best_model_name = name

print(f"\nBEST MODEL: {best_model_name} with {best_acc:.1%} LOO accuracy")

# Evaluate best model confusion matrix
best_clf = models[best_model_name]
pred = cross_val_predict(best_clf, X, yi, cv=LeaveOneOut())
print("\nConfusion Matrix:")
print(pd.DataFrame(confusion_matrix(yi, pred), index=le.classes_, columns=le.classes_))
print("\nClassification Report:")
print(classification_report(yi, pred, target_names=le.classes_, zero_division=0))
