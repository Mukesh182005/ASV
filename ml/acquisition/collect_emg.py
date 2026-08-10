"""CLI tool for collecting labeled EMG trials.

Usage:
    python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 20
    python ml/acquisition/collect_emg.py --subject S01 --label hello --reps 5 --simulate
"""
import os
import sys
import json
import time
import argparse
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.config import settings
from ml.acquisition.serial_reader import EMGSerialReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def countdown(seconds, message=""):
    for i in range(seconds, 0, -1):
        print(f"  {message}{i}...", flush=True)
        time.sleep(1)


def save_trial(trial_dir, rep_num, result, subject, label, duration, sampling_rate, num_channels):
    """Save a single trial recording + metadata JSON."""
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"rep{rep_num:03d}_{ts_str}"
    csv_path = trial_dir / f"{base_name}.csv"
    meta_path = trial_dir / f"{base_name}_meta.json"

    timestamps = result["timestamps"]
    channels = result["channels"]
    n_samples = len(timestamps)

    # Firmware v2 timestamps are microseconds; older builds used milliseconds.
    ts_unit = result.get("timestamp_unit", "us")
    per_second = 1e6 if ts_unit == "us" else 1e3

    # Build CSV: timestamp_us,channel_0[,channel_1,...]
    header_parts = [f"timestamp_{ts_unit}"] + [f"channel_{i}" for i in range(channels.shape[1] if channels.ndim > 1 else 1)]
    header = ",".join(header_parts)

    if channels.ndim == 1:
        channels = channels.reshape(-1, 1)

    fmt = ["%d"] + ["%g"] * channels.shape[1]
    data = np.column_stack([timestamps, channels])
    np.savetxt(csv_path, data, delimiter=",", header=header, comments="", fmt=fmt)

    # Compute actual sampling rate and timing jitter
    jitter = {}
    if n_samples >= 2:
        dt = np.diff(timestamps.astype(float))
        mean_dt = float(np.mean(dt))
        actual_rate = per_second / mean_dt if mean_dt > 0 else 0
        jitter = {
            "dt_mean": round(mean_dt, 3),
            "dt_std": round(float(np.std(dt)), 3),
            "dt_min": round(float(np.min(dt)), 3),
            "dt_max": round(float(np.max(dt)), 3),
            "unit": ts_unit,
        }
    else:
        actual_rate = 0

    meta = {
        "subject": subject,
        "label": label,
        "repetition": rep_num,
        "timestamp": ts_str,
        "n_samples": n_samples,
        "duration_sec": duration,
        "configured_sampling_rate_hz": sampling_rate,
        "actual_sampling_rate_hz": round(actual_rate, 2),
        "num_channels": num_channels,
        "timestamp_unit": ts_unit,
        "timing_jitter": jitter,
        "firmware_header": result.get("firmware_header", {}),
        "is_simulated": result.get("is_simulated", False),
        "serial_stats": result.get("stats", {}),
        "source": "collect_emg.py",
        "file": csv_path.name,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return csv_path, meta


def run_collection(args):
    num_channels = args.channels or settings.NUM_CHANNELS
    baud = args.baud or settings.SERIAL_BAUD_RATE
    duration = args.duration
    subject = args.subject
    label = args.label.lower()
    reps = args.reps
    simulate = args.simulate
    rest = args.rest

    # Create output directory: raw/{subject}/{label}/
    trial_dir = Path(args.output) / subject / label
    trial_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing reps to avoid overwriting
    existing = list(trial_dir.glob("rep*.csv"))
    if existing:
        logger.info(f"Found {len(existing)} existing recordings in {trial_dir}")

    reader = EMGSerialReader(args.port, baud_rate=baud, num_channels=num_channels)

    if not simulate:
        if not args.port:
            ports = EMGSerialReader.list_ports()
            print(f"Available serial ports: {ports}")
            if not ports:
                logger.error("No serial ports found. Connect ESP32 and retry.")
                return
            args.port = input("Enter serial port: ").strip()
            reader.port = args.port
        if not reader.connect():
            logger.error("Cannot connect to ESP32. Aborting.")
            return
        # Wait for data stream to stabilize
        print("Waiting for data stream to stabilize...")
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"  ASV Data Collection")
    print(f"  Subject: {subject}")
    print(f"  Label: {label}")
    print(f"  Repetitions: {reps}")
    print(f"  Duration: {duration}s per trial")
    print(f"  Channels: {num_channels}")
    print(f"  Mode: {'SIMULATED' if simulate else 'LIVE HARDWARE'}")
    print(f"  Output: {trial_dir}")
    print(f"{'='*50}\n")

    try:
        for rep in range(1, reps + 1):
            print(f"\n--- Trial {rep}/{reps}: '{label}' ---")
            countdown(3, "Prepare in ")
            print("  >>> RECORDING — articulate now! <<<", flush=True)

            result = reader.read_samples(duration, simulate=simulate)
            n = len(result["timestamps"])
            stats = result.get("stats", {})

            csv_path, meta = save_trial(
                trial_dir, rep, result,
                subject, label, duration,
                settings.SAMPLING_RATE_HZ, num_channels,
            )
            actual = meta.get("actual_sampling_rate_hz", 0)
            print(f"  Saved: {csv_path.name} ({n} samples @ {actual} Hz, "
                  f"{stats.get('malformed', 0)} malformed packets)")

            # Guard against the silent killer: a train/inference rate mismatch.
            expected = settings.SAMPLING_RATE_HZ
            if n == 0:
                logger.error(
                    "NO SAMPLES RECEIVED. The firmware boots IDLE - check that "
                    "the serial handshake ('s') succeeded, and that the self-test "
                    "passes in the Arduino Serial Monitor."
                )
            elif actual and abs(actual - expected) / expected > 0.10:
                logger.warning(
                    f"Sampling rate {actual} Hz differs from settings.SAMPLING_RATE_HZ "
                    f"({expected} Hz) by more than 10%. Fix ml/config/settings.py to "
                    f"match the firmware BEFORE collecting the rest of the dataset."
                )

            if rep < reps:
                print(f"  Rest for {rest}s...")
                time.sleep(rest)
    except KeyboardInterrupt:
        print("\n  Collection interrupted by user.")
    finally:
        if not simulate:
            reader.disconnect()

    print(f"\nCollection complete. Files in: {trial_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="ASV EMG Data Collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--subject", required=True, help="Subject ID (e.g., S01)")
    parser.add_argument("--label", required=True, help="Word label (e.g., hello, yes)")
    parser.add_argument("--reps", type=int, default=20, help="Number of repetitions")
    parser.add_argument("--duration", type=float, default=2.0, help="Recording duration per trial (seconds)")
    parser.add_argument("--port", default=None, help="Serial port (e.g., COM3)")
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate (default: 921600)")
    parser.add_argument("--channels", type=int, default=None, help="Number of ADC channels (default from settings)")
    parser.add_argument("--rest", type=float, default=3.0, help="Rest between trials (seconds)")
    parser.add_argument("--output", default=str(settings.RAW_DATA_DIR), help="Output base directory")
    parser.add_argument("--simulate", action="store_true", help="Simulate data (testing only)")
    args = parser.parse_args()
    run_collection(args)


if __name__ == "__main__":
    main()
