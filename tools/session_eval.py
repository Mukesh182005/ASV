#!/usr/bin/env python3
"""ASV -- Leave-one-session-out evaluation
========================================
The honest accuracy test for this project.

Pooled leave-one-recording-out is optimistic: it leaves same-session recordings
of the held-out word in the training set, so the model can lean on the session's
signature -- electrode position, skin contact, hum level -- instead of the word.
On this hardware sessions are highly separable, so that inflation is large.

This holds out a whole donning instead. Train on every other session, test on the
one the model has never seen. That is the number that predicts "put the electrodes
on tomorrow and use it".

Sessions are recovered from the `timestamp` in each recording's _meta.json by
splitting wherever there is a gap longer than SESSION_GAP_MIN. A session is only
a valid test fold if it contains every word -- otherwise the model is graded on
an incomplete exam (session C, which held only `hi`, scored exactly chance for
that reason and told us nothing).

Usage:
    python tools/session_eval.py
    python tools/session_eval.py --model RandomForest
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml.refined.utterance_features import extract, load_counts_csv, FS_DEFAULT, signal_health  # noqa: E402

from sklearn.discriminant_analysis import LinearDiscriminantAnalysis  # noqa: E402
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, VotingClassifier  # noqa: E402
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix  # noqa: E402
from sklearn.model_selection import LeaveOneOut, cross_val_predict  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import LabelEncoder, StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402

DATA_DIR = REPO_ROOT / "datasets" / "custom_silent_speech" / "raw"
RANDOM_STATE = 42

# A gap this long between consecutive recordings means the electrodes came off.
SESSION_GAP_MIN = 15


def build_model(name):
    if name == "ExtraTrees":
        return ExtraTreesClassifier(n_estimators=500, max_features="sqrt", random_state=RANDOM_STATE)
    if name == "Ensemble":
        return VotingClassifier(
            estimators=[
                ("et", ExtraTreesClassifier(n_estimators=500, max_features="sqrt", random_state=RANDOM_STATE)),
                ("rf", RandomForestClassifier(n_estimators=400, max_depth=10, random_state=RANDOM_STATE)),
            ],
            voting="soft",
        )
    if name == "SVM_rbf":
        return make_pipeline(StandardScaler(), SVC(kernel="rbf", C=2.0, gamma="scale",
                                                   random_state=RANDOM_STATE))
    if name == "SVM_linear":
        return make_pipeline(StandardScaler(), SVC(kernel="linear", C=0.2,
                                                   random_state=RANDOM_STATE))
    if name == "LDA":
        return make_pipeline(StandardScaler(),
                             LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    return RandomForestClassifier(n_estimators=400, max_depth=10, random_state=RANDOM_STATE)


def load(filter_unhealthy=True):
    """Return (X, y, timestamps, files). One recording = one sample."""
    X, y, ts, files = [], [], [], []
    excluded = []
    for csv in sorted(glob.glob(str(DATA_DIR / "**" / "*.csv"), recursive=True)):
        p = Path(csv)
        meta = p.with_name(p.stem + "_meta.json")
        if meta.exists():
            stamp = json.load(open(meta))["timestamp"]
        else:
            # Fall back to the timestamp baked into the filename.
            stamp = "_".join(p.stem.split("_")[1:3])
        try:
            when = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        counts = load_counts_csv(csv)
        if filter_unhealthy:
            health = signal_health(counts)
            if not health["ok"]:
                excluded.append((p.name, p.parent.name, health["status"], health["pp_mv"]))
                continue
        X.append(extract(counts, fs=FS_DEFAULT))
        y.append(p.parent.name)
        ts.append(when)
        files.append(p.name)
    if excluded:
        print(f"[Signal Health Filter] Excluded {len(excluded)} corrupted/railed recordings (e.g. 50Hz mains hum):")
        cnts = {}
        for _, _, st, _ in excluded:
            cnts[st] = cnts.get(st, 0) + 1
        for st, c in cnts.items():
            print(f"  • {c}x {st}")
    return np.array(X), np.array(y), np.array(ts), files


def assign_sessions(ts):
    """Split recordings into donnings wherever there is a long gap."""
    order = np.argsort(ts)
    labels = np.empty(len(ts), dtype=object)
    current, letters = 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, idx in enumerate(order):
        if i > 0:
            gap = (ts[idx] - ts[order[i - 1]]).total_seconds() / 60.0
            if gap > SESSION_GAP_MIN:
                current += 1
        labels[idx] = letters[current % len(letters)]
    return labels


def main():
    ap = argparse.ArgumentParser(description="Leave-one-session-out evaluation")
    ap.add_argument("--model", default="ExtraTrees",
                    choices=["ExtraTrees", "Ensemble", "RandomForest", "SVM_rbf", "SVM_linear", "LDA"])
    ap.add_argument("--all-raw", action="store_true", help="Include corrupted/railed recordings without filtering")
    args = ap.parse_args()

    X, y, ts, _ = load(filter_unhealthy=not args.all_raw)
    if len(X) == 0:
        print("No recordings found.")
        sys.exit(1)
    sess = assign_sessions(ts)
    le = LabelEncoder()
    yy = le.fit_transform(y)
    all_words = set(y)

    print(f"\n{len(X)} clean recordings | {len(all_words)} words | model {args.model}")
    print("=" * 66)
    print("SESSIONS  (split at gaps > %d min)" % SESSION_GAP_MIN)
    order = sorted(set(sess), key=lambda s: ts[sess == s].min())
    valid = []
    for s in order:
        m = sess == s
        words = Counter(y[m])
        complete = set(words) == all_words
        if complete:
            valid.append(s)
        span = f"{ts[m].min():%H:%M}-{ts[m].max():%H:%M}"
        flag = "test fold" if complete else "not testable (missing words)"
        print(f"  {s}  {span}  n={m.sum():4d}  {len(words)}/{len(all_words)} words   {flag}")

    print("=" * 66)
    pooled = cross_val_predict(build_model(args.model), X, yy, cv=LeaveOneOut())
    pooled_acc = accuracy_score(yy, pooled)
    print(f"Pooled leave-one-recording-out : {pooled_acc:6.1%}   <- optimistic, leaks session")

    if not valid:
        print("\nNo session contains every word, so no honest test fold exists.")
        print("Record a full set of all words in one donning.")
        sys.exit(0)

    print("\nLEAVE-ONE-SESSION-OUT  (train on the rest, test on an unseen donning)")
    accs, preds, trues = [], [], []
    for s in valid:
        te = sess == s
        clf = build_model(args.model).fit(X[~te], yy[~te])
        p = clf.predict(X[te])
        a = accuracy_score(yy[te], p)
        accs.append(a)
        preds.append(p)
        trues.append(yy[te])
        print(f"  held out {s}  n={te.sum():4d}  ->  {a:6.1%}")

    mean = float(np.mean(accs))
    print(f"  {'MEAN':>10}              ->  {mean:6.1%}   <- the honest number")
    print(f"  {'chance':>10}              ->  {1/len(all_words):6.1%}")
    print(f"\n  inflation from session leakage: {pooled_acc - mean:+.1%}")

    yt = np.concatenate(trues)
    yp = np.concatenate(preds)
    print("\nPER-WORD, out-of-session only")
    print(classification_report(yt, yp, target_names=le.classes_, digits=2, zero_division=0))

    print("CONFUSION (rows = actual, cols = predicted)")
    cm = confusion_matrix(yt, yp)
    head = "        " + "".join(f"{c[:5]:>7}" for c in le.classes_)
    print(head)
    for i, c in enumerate(le.classes_):
        print(f"  {c:6s}" + "".join(f"{v:7d}" for v in cm[i]))
    print()


if __name__ == "__main__":
    main()
