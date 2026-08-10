"""Dataset validation and quality reporting for ASV EMG recordings.

Usage:
    python ml/acquisition/validate_dataset.py
    python ml/acquisition/validate_dataset.py --data-dir datasets/custom_silent_speech/raw
"""
import os
import sys
import json
import argparse
import logging
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ml.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def validate_trial(csv_path, meta_path=None, expected_rate=None):
    """Validate a single trial recording. Returns a quality report dict."""
    report = {
        "file": str(csv_path),
        "status": "GOOD",
        "warnings": [],
        "errors": [],
    }

    # Detect the timestamp unit from the header row. Firmware v2 writes
    # "timestamp_us"; older recordings wrote "timestamp" (milliseconds).
    ts_per_second = 1000.0
    report["timestamp_unit"] = "ms"
    try:
        with open(csv_path, "r") as fh:
            first_col = fh.readline().split(",")[0].strip().lower()
        if first_col.endswith("_us"):
            ts_per_second = 1e6
            report["timestamp_unit"] = "us"
    except Exception:
        pass

    # Load CSV
    try:
        data = np.loadtxt(csv_path, delimiter=",", skiprows=1)
    except Exception as e:
        report["status"] = "INVALID"
        report["errors"].append(f"Cannot load CSV: {e}")
        return report

    if data.size == 0:
        report["status"] = "INVALID"
        report["errors"].append("Empty recording (0 samples)")
        return report

    if data.ndim == 1:
        data = data.reshape(-1, 1)

    n_samples, n_cols = data.shape
    report["n_samples"] = n_samples
    report["n_columns"] = n_cols

    # Check minimum sample count
    if n_samples < 10:
        report["status"] = "INVALID"
        report["errors"].append(f"Too few samples: {n_samples}")
        return report

    # Column 0 should be timestamps
    timestamps = data[:, 0]
    channels = data[:, 1:]
    n_channels = channels.shape[1]

    # NaN check
    nan_count = int(np.isnan(data).sum())
    if nan_count > 0:
        report["status"] = "WARNING"
        report["warnings"].append(f"{nan_count} NaN values found")

    # Timestamp checks
    if np.any(timestamps < 0):
        report["status"] = "WARNING"
        report["warnings"].append("Negative timestamps detected")

    dt = np.diff(timestamps)
    if np.any(dt <= 0):
        n_nonmono = int(np.sum(dt <= 0))
        report["warnings"].append(f"{n_nonmono} non-monotonic timestamp gaps")
        if report["status"] == "GOOD":
            report["status"] = "WARNING"

    # Sampling rate estimation
    if len(dt) > 0:
        dt_positive = dt[dt > 0]
        if len(dt_positive) > 0:
            mean_dt = float(np.mean(dt_positive))
            actual_rate = ts_per_second / mean_dt if mean_dt > 0 else 0
            report["actual_sampling_rate_hz"] = round(actual_rate, 1)
            # Timing jitter: with the ALRT/RDY interrupt this should be tight.
            report["dt_std"] = round(float(np.std(dt_positive)), 3)
            report["dt_max"] = round(float(np.max(dt_positive)), 3)
            if mean_dt > 0 and float(np.std(dt_positive)) / mean_dt > 0.25:
                report["warnings"].append(
                    f"High sampling jitter (dt std/mean = "
                    f"{np.std(dt_positive) / mean_dt:.2f}). Check the ALRT/RDY wire."
                )
                if report["status"] == "GOOD":
                    report["status"] = "WARNING"
            if expected_rate and abs(actual_rate - expected_rate) / expected_rate > 0.15:
                report["warnings"].append(
                    f"Sampling rate deviation: expected ~{expected_rate} Hz, got ~{actual_rate:.1f} Hz"
                )
                if report["status"] == "GOOD":
                    report["status"] = "WARNING"

    # Duration
    duration_sec = float(timestamps[-1] - timestamps[0]) / ts_per_second
    report["duration_sec"] = round(duration_sec, 2)
    if duration_sec < 0.5:
        report["warnings"].append(f"Very short recording: {duration_sec * 1000:.0f} ms")
        if report["status"] == "GOOD":
            report["status"] = "WARNING"

    # Per-channel quality
    for ch in range(n_channels):
        ch_data = channels[:, ch]
        ch_valid = ch_data[~np.isnan(ch_data)]
        if len(ch_valid) == 0:
            report["errors"].append(f"Channel {ch}: all NaN")
            report["status"] = "INVALID"
            continue

        # Flatline detection
        if np.std(ch_valid) < 1e-6:
            report["warnings"].append(f"Channel {ch}: flatline (zero variance)")
            if report["status"] == "GOOD":
                report["status"] = "WARNING"

        # Clipping / saturation (ADS1115 16-bit range)
        max_val = float(np.max(np.abs(ch_valid)))
        if max_val > 32000:  # near 16-bit max
            report["warnings"].append(f"Channel {ch}: possible saturation (max={max_val:.0f})")
            if report["status"] == "GOOD":
                report["status"] = "WARNING"

        report[f"ch{ch}_mean"] = round(float(np.mean(ch_valid)), 2)
        report[f"ch{ch}_std"] = round(float(np.std(ch_valid)), 2)
        report[f"ch{ch}_min"] = round(float(np.min(ch_valid)), 2)
        report[f"ch{ch}_max"] = round(float(np.max(ch_valid)), 2)

    # Metadata cross-check
    if meta_path and meta_path.exists():
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("is_simulated", False):
                report["warnings"].append("SIMULATED data — not for production training")
                if report["status"] == "GOOD":
                    report["status"] = "WARNING"
        except Exception:
            report["warnings"].append("Could not parse metadata JSON")

    return report


def validate_dataset(data_dir, expected_rate=None):
    """Walk the dataset directory and validate all trials."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return []

    reports = []
    csv_files = sorted(data_dir.rglob("*.csv"))
    if not csv_files:
        logger.warning(f"No CSV files found in {data_dir}")
        return []

    for csv_path in csv_files:
        # Skip non-trial files
        if csv_path.name.startswith("."):
            continue
        meta_path = csv_path.with_name(csv_path.stem + "_meta.json")
        report = validate_trial(
            csv_path,
            meta_path=meta_path if meta_path.exists() else None,
            expected_rate=expected_rate or settings.SAMPLING_RATE_HZ,
        )
        reports.append(report)

    return reports


def print_report(reports):
    """Print human-readable validation summary."""
    good = sum(1 for r in reports if r["status"] == "GOOD")
    warn = sum(1 for r in reports if r["status"] == "WARNING")
    invalid = sum(1 for r in reports if r["status"] == "INVALID")

    print(f"\n{'='*60}")
    print(f"  Dataset Validation Report")
    print(f"  Total files: {len(reports)}")
    print(f"  GOOD: {good}  |  WARNING: {warn}  |  INVALID: {invalid}")
    print(f"{'='*60}")

    for r in reports:
        status_icon = {"GOOD": "✓", "WARNING": "⚠", "INVALID": "✗"}.get(r["status"], "?")
        rel_path = Path(r["file"]).name
        print(f"\n  {status_icon} {rel_path}  [{r['status']}]")
        if r.get("n_samples"):
            rate = r.get("actual_sampling_rate_hz", "?")
            print(f"    Samples: {r['n_samples']}  Duration: {r.get('duration_sec', '?')}s  Rate: {rate} Hz")
        for w in r.get("warnings", []):
            print(f"    ⚠ {w}")
        for e in r.get("errors", []):
            print(f"    ✗ {e}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Validate ASV EMG dataset")
    parser.add_argument("--data-dir", default=str(settings.RAW_DATA_DIR))
    parser.add_argument("--rate", type=float, default=None, help="Expected sampling rate")
    args = parser.parse_args()
    reports = validate_dataset(args.data_dir, expected_rate=args.rate)
    if reports:
        print_report(reports)
        # Save JSON report
        report_path = settings.METADATA_DIR / "validation_report.json"
        with open(report_path, "w") as f:
            json.dump(reports, f, indent=2, default=str)
        print(f"Report saved to: {report_path}")
    else:
        print("No data files found to validate.")


if __name__ == "__main__":
    main()
