#!/usr/bin/env python3
"""ASV — Smart Dataset Consistency Curator
===========================================
Compares previously recorded signals against the newly recorded session.
Keeps previous recordings that match the current electrode setup and articulation
style; quarantines mismatched or noisy signals into datasets/quarantine/.

Usage:
    python tools/curate_dataset.py
    python tools/curate_dataset.py --threshold 0.80
"""
import os
import sys
import glob
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ml.refined.utterance_features import extract, load_counts_csv, FS_DEFAULT, signal_health
from tools.session_eval import assign_sessions

DATA_DIR = REPO_ROOT / "datasets" / "custom_silent_speech" / "raw"
QUARANTINE_DIR = REPO_ROOT / "datasets" / "custom_silent_speech" / "quarantine"


def curate_dataset(target_word=None, similarity_threshold=0.75, dry_run=False):
    print("=" * 65)
    print("ASV — Dataset Consistency Curator")
    if target_word:
        print(f"Targeting word: '{target_word.upper()}' against newest recordings")
    else:
        print("Aligning all training data with your newest recordings")
    print("=" * 65)

    all_csvs = sorted(glob.glob(str(DATA_DIR / "**" / "*.csv"), recursive=True))
    if not all_csvs:
        print("No CSV recordings found in", DATA_DIR)
        return

    # 1. Load all recordings and extract features
    records = []
    for csv_str in all_csvs:
        p = Path(csv_str)
        meta_p = p.with_name(p.stem + "_meta.json")
        if meta_p.exists():
            stamp_str = json.load(open(meta_p)).get("timestamp")
        else:
            parts = p.stem.split("_")
            stamp_str = "_".join(parts[1:3]) if len(parts) >= 3 else "20200101_000000"
        try:
            dt = datetime.strptime(stamp_str, "%Y%m%d_%H%M%S")
        except ValueError:
            dt = datetime.min
        
        counts = load_counts_csv(p)
        health = signal_health(counts)
        feat = extract(counts, fs=FS_DEFAULT)
        
        records.append({
            "path": p,
            "meta_path": meta_p if meta_p.exists() else None,
            "word": p.parent.name,
            "subject": p.parent.parent.name,
            "filename": p.name,
            "timestamp": dt,
            "health": health,
            "features": feat,
        })

    # Sort chronologically
    records.sort(key=lambda r: r["timestamp"])
    timestamps = [r["timestamp"] for r in records]
    sess_labels = assign_sessions(timestamps)
    for i, r in enumerate(records):
        r["session"] = sess_labels[i]

    all_words = sorted(list(set(r["word"] for r in records)))
    if target_word and target_word.lower() in all_words:
        curate_words = [target_word.lower()]
    else:
        curate_words = all_words

    kept_count = 0
    quarantined_count = 0

    scaler = StandardScaler()
    all_feats = np.array([r["features"] for r in records])
    scaled_feats = scaler.fit_transform(all_feats)
    for i, r in enumerate(records):
        r["scaled_feat"] = scaled_feats[i]

    print("\nEvaluating consistency:")
    print("-" * 65)

    for word in curate_words:
        word_records = [r for r in records if r["word"] == word]
        if not word_records:
            continue

        # Find the latest session for this word that has healthy recordings
        word_sessions = sorted(list(set(r["session"] for r in word_records)))
        latest_word_sess = word_sessions[-1]
        latest_word_records = [r for r in word_records if r["session"] == latest_word_sess and r["health"]["ok"]]
        
        if not latest_word_records:
            healthy_records = [r for r in word_records if r["health"]["ok"]]
            if healthy_records:
                latest_word_records = healthy_records[-10:]
            else:
                print(f"  {word:8s}: No healthy recordings found! Skipping.")
                continue

        # Target reference vector (mean of latest session for this word)
        target_vec = np.mean([r["scaled_feat"] for r in latest_word_records], axis=0).reshape(1, -1)

        print(f"\n  Word: '{word.upper()}' (Reference set: {len(latest_word_records)} recent samples from session '{latest_word_sess}')")
        
        for r in word_records:
            # Automatic rejection for electrical noise / mains hum
            if not r["health"]["ok"]:
                status = f"REJECTED ({r['health']['status']})"
                keep = False
                sim = 0.0
            elif r in latest_word_records:
                # Always keep the newest reference recordings
                status = "KEPT (Current Reference Session)"
                keep = True
                sim = 1.0
            else:
                # Compare similarity to the new session
                sim = float(cosine_similarity(r["scaled_feat"].reshape(1, -1), target_vec)[0, 0])
                if sim >= similarity_threshold:
                    status = f"KEPT (Similarity: {sim:.2f} >= {similarity_threshold:.2f})"
                    keep = True
                else:
                    status = f"REMOVED (Mismatch: {sim:.2f} < {similarity_threshold:.2f})"
                    keep = False

            if keep:
                kept_count += 1
            else:
                quarantined_count += 1
                if not dry_run:
                    target_dir = QUARANTINE_DIR / r["subject"] / r["word"]
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(r["path"]), str(target_dir / r["filename"]))
                    if r["meta_path"] and r["meta_path"].exists():
                        shutil.move(str(r["meta_path"]), str(target_dir / r["meta_path"].name))

            print(f"    • {r['filename']:28s} {status}")

    print("\n" + "=" * 65)
    print(f"Curator summary: {kept_count} matching signals KEPT, {quarantined_count} mismatched/noisy REMOVED.")
    if not dry_run:
        print(f"Quarantined files saved safely to: {QUARANTINE_DIR}")
        print("\nRetraining model on pristine, matching dataset...")
        os.system(f'"{sys.executable}" ml/refined/train_refined.py')
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curate dataset against newest recordings")
    parser.add_argument("--word", default=None, help="Target specific word to curate (e.g. 'help')")
    parser.add_argument("--threshold", type=float, default=0.75, help="Minimum cosine similarity with new session (default: 0.75)")
    parser.add_argument("--dry-run", action="store_true", help="Report only without moving files")
    args = parser.parse_args()

    curate_dataset(target_word=args.word, similarity_threshold=args.threshold, dry_run=args.dry_run)
