#!/usr/bin/env python3
"""ASV — Live Word Predictor (CLI)
==================================
Usage:
    python tools/predict_live.py --port COM8
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import joblib
    import serial
    import serial.tools.list_ports
except ImportError as e:
    print(f"ERROR: missing dependency: {e}")
    print("Please run: pip install numpy joblib pyserial scikit-learn scipy")
    sys.exit(1)

# Add repo root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.refined.utterance_features import extract, FS_DEFAULT, signal_health

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MODEL_DIR = REPO_ROOT / "refined_model"

def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    print(f"{'PORT':<12} {'DESCRIPTION':<40}")
    for p in ports:
        print(f"{p.device:<12} {(p.description or ''):<40}")

def open_port(port, baud=921600):
    try:
        conn = serial.Serial(port, baud, timeout=0.1)
        time.sleep(1.5) # Wait for ESP32 reset
        conn.reset_input_buffer()
        return conn
    except serial.SerialException as e:
        print(f"\nERROR: Could not open port {port}: {e}")
        print("Make sure no other serial monitor (like plot_emg.py or Arduino IDE) is using it.")
        return None

def countdown(seconds, message=""):
    """Same 3-2-1 protocol used by collect_emg.py to build the training set.
    Matching it here matters: EMG onset timing relative to a countdown cue is
    part of what the model learned, so a different capture rhythm is a real
    (if subtle) train/inference mismatch."""
    for i in range(seconds, 0, -1):
        print(f"  {message}{i}...", flush=True)
        time.sleep(1)


def read_baseline(conn, seconds=1.0):
    """Read ~1s of idle stream to report signal health before trials start."""
    samples = []
    end_time = time.time() + seconds
    while time.time() < end_time:
        raw = conn.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line[0].isdigit():
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            samples.append(int(parts[1]))
        except ValueError:
            continue
    return samples


def capture_utterance(conn, seconds=2.0):
    samples = []
    # Send start stream command
    conn.write(b"x")
    time.sleep(0.1)
    conn.reset_input_buffer()
    conn.write(b"s")

    # Read stream header
    deadline = time.time() + 1.0
    started = False
    while time.time() < deadline and not started:
        line = conn.readline().decode('utf-8', errors='ignore').strip()
        if "START DATA" in line:
            started = True
            break

    end_time = time.time() + seconds
    while time.time() < end_time:
        raw = conn.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or not line[0].isdigit():
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            samples.append(int(parts[1]))
        except ValueError:
            continue

    # Send stop command
    conn.write(b"x")
    return samples

def main():
    parser = argparse.ArgumentParser(description="Live Word Predictor (CLI)")
    parser.add_argument("--port", help="COM port for ESP32 (e.g. COM8)")
    parser.add_argument("--seconds", type=float, default=2.0, help="Recording window size in seconds")
    parser.add_argument("--list", action="store_true", help="List available serial ports and exit")
    args = parser.parse_args()

    if args.list:
        list_ports()
        sys.exit(0)

    # Load model
    clf_path = MODEL_DIR / "classifier.pkl"
    le_path = MODEL_DIR / "label_encoder.pkl"
    
    if not (clf_path.exists() and le_path.exists()):
        print(f"ERROR: Model files not found in {MODEL_DIR}")
        print("Please train a model first using: python ml/refined/train_refined.py")
        sys.exit(1)

    print("Loading refined SVM model...")
    try:
        clf = joblib.load(clf_path)
        le = joblib.load(le_path)
        print(f"Model loaded successfully! Vocabulary: {list(le.classes_)}")
    except Exception as e:
        print(f"ERROR loading model: {e}")
        sys.exit(1)

    port = args.port
    if not port:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("ERROR: No serial ports found. Connect the ESP32.")
            sys.exit(1)
        # Select first USB bridge/silicon labs or default to COM8 if present
        target_ports = [p.device for p in ports if "Silicon Labs" in (p.description or "")]
        if target_ports:
            port = target_ports[0]
        else:
            port = ports[0].device
        print(f"Auto-selected port: {port}")

    print(f"Connecting to ESP32 on {port}...")
    conn = open_port(port)
    if not conn:
        sys.exit(1)
    conn.write(b"s")

    print("Checking electrode contact (1s idle read)...")
    baseline_counts = read_baseline(conn, seconds=1.0)
    health = signal_health(baseline_counts)
    if health["status"] == "NO_DATA":
        print("  [WARNING] No data received. Check the firmware self-test and port.")
    else:
        print(f"  baseline={health['baseline_mv']}mV  pp={health['pp_mv']}mV  -> {health['status']}")
        if not health["ok"]:
            print("  [WARNING] Signal looks unhealthy — expect ~1635mV baseline and >3mV pp.")
            print("  Predictions below may be unreliable until this is fixed.")

    print("\n" + "="*50)
    print("  ASV Live Word Predictor (CLI)")
    print("  To exit, press Ctrl+C or type 'q' then Enter.")
    print("="*50)

    try:
        while True:
            inp = input("\nPress Enter to start recording (2 seconds)... ").strip()
            if inp.lower() == 'q':
                break

            # Same 3-2-1 countdown protocol used when the training set was
            # collected (ml/acquisition/collect_emg.py) — matching it avoids a
            # subtle train/inference timing mismatch.
            countdown(3, "Prepare in ")
            print("  >>> RECORDING — articulate now! <<<", flush=True)

            # Capture
            counts = capture_utterance(conn, seconds=args.seconds)
            print(f"  Captured {len(counts)} samples (~{len(counts)/FS_DEFAULT:.2f}s, "
                  f"expected ~{args.seconds:.1f}s).")

            if len(counts) < 32:
                print("  [ERROR] Capture too short or empty! Check connections.")
                continue
            if len(counts) < 0.7 * args.seconds * FS_DEFAULT:
                print("  [WARNING] Capture is shorter than expected — the serial link may be "
                      "dropping data. The prediction below may default to 'rest'.")

            cap_health = signal_health(counts)
            if not cap_health["ok"]:
                print(f"  [WARNING] {cap_health['status']} during capture "
                      f"(baseline={cap_health['baseline_mv']}mV, pp={cap_health['pp_mv']}mV) "
                      f"— check electrode contact.")

            # Classify
            x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
            pred = le.inverse_transform(clf.predict(x))[0]
            conf = None
            if hasattr(clf, "predict_proba"):
                p = clf.predict_proba(x)[0]
                conf = float(np.max(p))
                ranking = sorted(zip(le.classes_, p), key=lambda t: -t[1])

            # Output results
            print("\n" + "-"*35)
            print(f"Prediction: {pred.upper()}" + (f"  (confidence {conf:.0%})" if conf is not None else ""))
            if conf is not None:
                print("Probability Ranking:")
                for w, pr in ranking:
                    indicator = "-> " if w == pred else "   "
                    print(f" {indicator} {w:8s} {pr:5.1%}")
            print("-"*35)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        try:
            conn.write(b"x")
        except:
            pass
        conn.close()
        print("Serial port closed.")

if __name__ == "__main__":
    main()
