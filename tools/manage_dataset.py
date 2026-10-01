#!/usr/bin/env python3
"""ASV -- Dataset Manager
========================
Manage per-word training data: list, delete one word, add more reps,
or retrain after changes.

Usage:
    python tools/manage_dataset.py status
    python tools/manage_dataset.py delete --word no
    python tools/manage_dataset.py collect --word no --reps 20 --port COM5
    python tools/manage_dataset.py collect-all --reps 20 --port COM5
    python tools/manage_dataset.py retrain
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "datasets" / "custom_silent_speech" / "raw"


def cmd_status(args):
    if not DATA_DIR.exists():
        print("No dataset directory found.")
        return
    total = 0
    for subject_dir in sorted(DATA_DIR.iterdir()):
        if not subject_dir.is_dir():
            continue
        print(f"\nSubject: {subject_dir.name}")
        for word_dir in sorted(subject_dir.iterdir()):
            if not word_dir.is_dir():
                continue
            csvs = list(word_dir.glob("*.csv"))
            n = len(csvs)
            total += n
            bar = "#" * n + "." * max(0, 30 - n)
            print(f"  {word_dir.name:10s} {n:3d} recordings  [{bar}]")
    print(f"\n  Total: {total} recordings")


def cmd_delete(args):
    word = args.word.lower()
    subject = args.subject
    word_dir = DATA_DIR / subject / word
    if not word_dir.exists():
        print(f"No recordings found for '{word}' (subject {subject}).")
        return
    csvs = list(word_dir.glob("*.csv"))
    print(f"Found {len(csvs)} recordings for '{word}' in {word_dir}")
    if not args.yes:
        confirm = input(f"Delete all {len(csvs)} '{word}' recordings? [y/N] ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return
    shutil.rmtree(word_dir)
    word_dir.mkdir(parents=True, exist_ok=True)
    print(f"Deleted all '{word}' recordings. Directory kept empty for re-collection.")


def cmd_collect(args):
    word = args.word.lower()
    cmd = [
        sys.executable,
        str(REPO_ROOT / "ml" / "acquisition" / "collect_emg.py"),
        "--subject", args.subject,
        "--label", word,
        "--reps", str(args.reps),
        "--port", args.port,
        "--duration", str(args.duration),
    ]
    print(f"Collecting {args.reps} recordings of '{word}'...")
    subprocess.run(cmd)


def cmd_retrain(args):
    cmd = [sys.executable, str(REPO_ROOT / "ml" / "refined" / "train_refined.py")]
    print("Retraining model on current dataset...")
    subprocess.run(cmd)


def cmd_collect_all(args):
    words = ["hello", "yes", "water", "rest", "help"]
    for i, word in enumerate(words, 1):
        word_dir = DATA_DIR / args.subject / word
        existing = len(list(word_dir.glob("*.csv"))) if word_dir.exists() else 0
        print(f"\n{'='*50}")
        print(f"  Word {i}/5: {word.upper()}  (existing: {existing} recordings)")
        print(f"{'='*50}")
        if existing > 0 and not args.yes:
            choice = input(f"  '{word}' already has {existing} recordings. [A]dd more / [S]kip / [R]eplace? ").strip().lower()
            if choice == "s":
                print(f"  Skipping '{word}'.")
                continue
            elif choice == "r":
                shutil.rmtree(word_dir)
                word_dir.mkdir(parents=True, exist_ok=True)
                print(f"  Cleared '{word}' recordings.")
        cmd = [
            sys.executable,
            str(REPO_ROOT / "ml" / "acquisition" / "collect_emg.py"),
            "--subject", args.subject,
            "--label", word,
            "--reps", str(args.reps),
            "--port", args.port,
            "--duration", str(args.duration),
        ]
        subprocess.run(cmd)
    print(f"\nAll words collected! Run: python tools/manage_dataset.py retrain")


def main():
    parser = argparse.ArgumentParser(description="ASV Dataset Manager")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show recording counts per word")

    p_del = sub.add_parser("delete", help="Delete all recordings for a word")
    p_del.add_argument("--word", required=True)
    p_del.add_argument("--subject", default="S01")
    p_del.add_argument("--yes", "-y", action="store_true")

    p_col = sub.add_parser("collect", help="Collect recordings for one word")
    p_col.add_argument("--word", required=True)
    p_col.add_argument("--reps", type=int, default=20)
    p_col.add_argument("--port", default="COM5")
    p_col.add_argument("--subject", default="S01")
    p_col.add_argument("--duration", type=float, default=5.0)

    p_all = sub.add_parser("collect-all", help="Collect all 5 words")
    p_all.add_argument("--reps", type=int, default=20)
    p_all.add_argument("--port", default="COM5")
    p_all.add_argument("--subject", default="S01")
    p_all.add_argument("--duration", type=float, default=5.0)
    p_all.add_argument("--yes", "-y", action="store_true")

    sub.add_parser("retrain", help="Retrain model on current dataset")

    args = parser.parse_args()
    cmds = {"status": cmd_status, "delete": cmd_delete, "collect": cmd_collect,
            "collect-all": cmd_collect_all, "retrain": cmd_retrain}
    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
