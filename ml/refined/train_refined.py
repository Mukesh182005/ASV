"""
ASV — Refined training pipeline (utterance-level)
=================================================

Trains a silent-speech classifier that treats each 2 s recording as ONE sample.
Everything reported here is *out-of-fold* — no sample is ever scored by a model
that saw it in training. Two independent honesty checks are run:

  1. Leave-One-Recording-Out (LOO)         -> per-utterance accuracy
  2. Repeated Stratified 5-fold (10x)       -> mean +/- std, guards against a lucky split

The confusion matrix is built from LOO out-of-fold predictions, so it reflects
generalisation to unseen recordings *of the same subject/session*, not training fit.

Usage:
    python ml/refined/train_refined.py
    python ml/refined/train_refined.py --data-dir datasets/custom_silent_speech/raw --out refined_model
"""
from __future__ import annotations
import os, sys, glob, json, argparse, shutil, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")  # silence sklearn FutureWarnings for a clean deliverable

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import (
    LeaveOneOut, cross_val_predict, cross_val_score, RepeatedStratifiedKFold,
)
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ml.refined.utterance_features import extract, load_counts_csv, preprocess, FEATURE_NAMES, FS_DEFAULT

RANDOM_STATE = 42


def discover(data_dir):
    """Return (X, y, groups, files, raw_counts) from raw/{subject}/{label}/rep*.csv."""
    data_dir = Path(data_dir)
    X, y, subjects, files, raws = [], [], [], [], []
    for csv in sorted(data_dir.rglob("*.csv")):
        parts = csv.relative_to(data_dir).parts
        if len(parts) < 3:
            continue
        subject, label = parts[0], parts[1]
        counts = load_counts_csv(csv)
        X.append(extract(counts, fs=FS_DEFAULT))
        y.append(label)
        subjects.append(subject)
        files.append(csv.name)
        raws.append(counts)
    return np.array(X), np.array(y), np.array(subjects), files, raws


def candidate_models():
    return {
        "SVM_rbf":  make_pipeline(StandardScaler(), SVC(kernel="rbf", C=5, gamma="scale",
                                                        probability=True, random_state=RANDOM_STATE)),
        "LDA":      make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
        "RandomForest": RandomForestClassifier(n_estimators=400, max_depth=None,
                                               random_state=RANDOM_STATE),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="datasets/custom_silent_speech/raw")
    ap.add_argument("--out", default="refined_model")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    data_dir = (root / args.data_dir) if not os.path.isabs(args.data_dir) else Path(args.data_dir)
    out_dir = (root / args.out) if not os.path.isabs(args.out) else Path(args.out)

    print(f"[1/5] Loading recordings from {data_dir}")
    X, y, subjects, files, raws = discover(data_dir)
    if len(X) == 0:
        print("ERROR: no recordings found."); sys.exit(1)
    labels = sorted(np.unique(y).tolist())
    print(f"      {len(X)} recordings | {len(labels)} classes: {labels} | subjects: {sorted(set(subjects))}")
    print(f"      {X.shape[1]} features/utterance")

    le = LabelEncoder().fit(labels)
    yi = le.transform(y)

    # ---- honesty check 1: Leave-One-Recording-Out ----
    print("[2/5] Evaluating (Leave-One-Recording-Out + Repeated 5-fold)")
    results = {}
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=RANDOM_STATE)
    for name, model in candidate_models().items():
        loo_pred = cross_val_predict(model, X, yi, cv=LeaveOneOut())
        loo_acc = accuracy_score(yi, loo_pred)
        rk = cross_val_score(model, X, yi, cv=rskf)
        results[name] = {
            "loo_accuracy": round(float(loo_acc), 4),
            "repeated5fold_mean": round(float(rk.mean()), 4),
            "repeated5fold_std": round(float(rk.std()), 4),
            "_loo_pred": loo_pred,
        }
        print(f"      {name:13s} LOO={loo_acc:.3f}  5fold={rk.mean():.3f}±{rk.std():.3f}")

    best = max(results, key=lambda k: (results[k]["loo_accuracy"], results[k]["repeated5fold_mean"]))
    print(f"      -> best: {best}")

    # ---- honest confusion matrix from best model's LOO out-of-fold predictions ----
    loo_pred = results[best].pop("_loo_pred")
    for r in results.values():
        r.pop("_loo_pred", None)
    cm = confusion_matrix(yi, loo_pred)
    report = classification_report(yi, loo_pred, target_names=le.classes_,
                                   output_dict=True, zero_division=0)

    # ---- fit final model on all data ----
    print("[3/5] Fitting final model on all recordings")
    final = candidate_models()[best]
    final.fit(X, yi)

    # ---- save artifacts ----
    print(f"[4/5] Writing deliverable folder: {out_dir}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    import joblib
    joblib.dump(final, out_dir / "classifier.pkl")
    joblib.dump(le, out_dir / "label_encoder.pkl")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    metadata = {
        "model_type": best,
        "approach": "utterance-level (1 recording = 1 sample)",
        "training_timestamp": ts,
        "labels": le.classes_.tolist(),
        "sampling_rate_hz": FS_DEFAULT,
        "feature_names": FEATURE_NAMES,
        "n_features": len(FEATURE_NAMES),
        "n_recordings": int(len(X)),
        "subjects": sorted(set(subjects.tolist())),
        "single_subject": len(set(subjects)) == 1,
        "scope_note": ("Validated same-subject/same-session (leave-one-recording-out). "
                       "Re-applying electrodes or a new subject requires re-recording/recalibration."),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    evaluation = {
        "best_model": best,
        "evaluation_method": "Leave-One-Recording-Out (out-of-fold) + Repeated 5-fold x10",
        "loo_accuracy": results[best]["loo_accuracy"],
        "repeated5fold_mean": results[best]["repeated5fold_mean"],
        "repeated5fold_std": results[best]["repeated5fold_std"],
        "all_models": results,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": le.classes_.tolist(),
        "classification_report": report,
        "chance_level": round(1.0 / len(labels), 4),
        "note": "All metrics are out-of-fold. No sample was scored by a model that trained on it.",
    }
    (out_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2))
    (out_dir / "feature_schema.json").write_text(json.dumps(
        {"version": 2, "feature_names": FEATURE_NAMES, "n_features": len(FEATURE_NAMES)}, indent=2))

    # ---- plots ----
    print("[5/5] Rendering plots")
    _plot_confusion(cm, le.classes_, out_dir / "confusion_matrix.png",
                    title=f"{best} — Leave-One-Recording-Out (acc={results[best]['loo_accuracy']:.0%})")
    _plot_envelopes(y, raws, le.classes_, out_dir / "envelopes.png")

    _write_readme(out_dir, metadata, evaluation)
    _write_predict_helper(out_dir)

    print("\nDONE. Deliverable folder:", out_dir)
    print(f"  best model : {best}")
    print(f"  LOO acc    : {results[best]['loo_accuracy']:.1%}   (chance {1/len(labels):.0%})")
    print(f"  5-fold x10 : {results[best]['repeated5fold_mean']:.1%} ± {results[best]['repeated5fold_std']:.1%}")


def _plot_confusion(cm, classes, path, title):
    cmn = cm.astype(float) / cm.sum(axis=1, keepdims=True).clip(min=1)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    fig.patch.set_facecolor("#0f0f1a"); ax.set_facecolor("#0f0f1a")
    im = ax.imshow(cmn, cmap="cividis", vmin=0, vmax=1)
    ax.set_xticks(range(len(classes))); ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes, color="#ddd"); ax.set_yticklabels(classes, color="#ddd")
    ax.set_xlabel("predicted", color="#ddd"); ax.set_ylabel("true", color="#ddd")
    ax.set_title(title, color="#fff", fontsize=11)
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, f"{cm[i,j]}", ha="center", va="center",
                    color="#fff" if cmn[i, j] < 0.6 else "#000", fontsize=11)
    cb = fig.colorbar(im, fraction=0.046, pad=0.04); cb.ax.yaxis.set_tick_params(color="#ddd")
    plt.setp(plt.getp(cb.ax, "yticklabels"), color="#ddd")
    plt.tight_layout(); plt.savefig(path, dpi=140, facecolor="#0f0f1a"); plt.close()


def _plot_envelopes(y, raws, classes, path):
    fig, axes = plt.subplots(1, len(classes), figsize=(3.0 * len(classes), 3.2), sharey=True)
    fig.patch.set_facecolor("#0f0f1a")
    for ax, cls in zip(np.atleast_1d(axes), classes):
        ax.set_facecolor("#0f0f1a"); ax.tick_params(colors="#aaa")
        for sp in ax.spines.values(): sp.set_color("#333355")
        for counts, lab in zip(raws, y):
            if lab != cls:
                continue
            _, env = preprocess(counts)
            t = np.linspace(0, len(env) / FS_DEFAULT, len(env))
            ax.plot(t, env, color="#00e5ff", alpha=0.5, linewidth=0.8)
        ax.set_title(cls, color="#fff"); ax.set_xlabel("s", color="#aaa")
    np.atleast_1d(axes)[0].set_ylabel("envelope (mV)", color="#aaa")
    fig.suptitle("Per-word EMG envelopes (10 reps each) — the signal the model reads",
                 color="#fff", fontsize=11)
    plt.tight_layout(); plt.savefig(path, dpi=140, facecolor="#0f0f1a"); plt.close()


def _write_readme(out_dir, metadata, evaluation):
    labels = ", ".join(metadata["labels"])
    md = f"""# ASV — Refined model (utterance-level)

**Trained:** {metadata['training_timestamp']} · **Model:** {metadata['model_type']} · **Subject(s):** {', '.join(metadata['subjects'])}

## What this is
A silent-speech classifier for the vocabulary: **{labels}**.
Unlike the original per-window model, this treats **one recording = one word = one
sample** and describes the whole utterance (energy + envelope shape + spectrum).

## Honest accuracy (out-of-fold — no leakage)
| Metric | Value |
|---|---|
| Leave-One-Recording-Out accuracy | **{evaluation['loo_accuracy']:.1%}** |
| Repeated 5-fold ×10 | {evaluation['repeated5fold_mean']:.1%} ± {evaluation['repeated5fold_std']:.1%} |
| Chance level ({len(metadata['labels'])} classes) | {evaluation['chance_level']:.0%} |

Every number above is measured on recordings the model did **not** train on.
See `confusion_matrix.png` (built from out-of-fold predictions) and `evaluation.json`.

## Scope — read before trusting it
{metadata['scope_note']}
This is **{'single-subject' if metadata['single_subject'] else 'multi-subject'}**. It has not
been shown to survive re-applying the electrodes or a different person. For a new
session/subject, record a fresh dataset and retrain (`python ml/refined/train_refined.py`).

## Files
- `classifier.pkl`, `label_encoder.pkl` — the trained model
- `feature_schema.json`, `metadata.json`, `evaluation.json`
- `confusion_matrix.png`, `envelopes.png`
- `predict.py` — classify a recording: `python predict.py <recording.csv>`

## How to test
```bash
# classify any collect_emg.py CSV (timestamp_us,channel_0)
python refined_model/predict.py datasets/custom_silent_speech/raw/S01/no/rep005_*.csv
```
Feature extraction is shared with `ml/refined/utterance_features.py`, so training
and inference cannot drift apart.
"""
    (out_dir / "README.md").write_text(md, encoding="utf-8")


def _write_predict_helper(out_dir):
    code = '''"""Classify one ASV recording with the refined model.

Usage:  python predict.py <recording.csv>
"""
import sys, json, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.refined.utterance_features import extract, load_counts_csv, FS_DEFAULT

HERE = Path(__file__).resolve().parent

def main():
    if len(sys.argv) < 2:
        print("usage: python predict.py <recording.csv>"); sys.exit(1)
    counts = load_counts_csv(sys.argv[1])
    x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
    clf = joblib.load(HERE / "classifier.pkl")
    le = joblib.load(HERE / "label_encoder.pkl")
    pred = le.inverse_transform(clf.predict(x))[0]
    conf = None
    if hasattr(clf, "predict_proba"):
        p = clf.predict_proba(x)[0]
        conf = float(np.max(p))
        ranking = sorted(zip(le.classes_, p), key=lambda t: -t[1])
    print(f"\\nPrediction: {pred}" + (f"  (confidence {conf:.0%})" if conf is not None else ""))
    if conf is not None:
        print("Ranking:")
        for w, pr in ranking:
            print(f"   {w:8s} {pr:5.1%}")

if __name__ == "__main__":
    main()
'''
    (out_dir / "predict.py").write_text(code, encoding="utf-8")


if __name__ == "__main__":
    main()
