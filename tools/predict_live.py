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
from ml.refined.utterance_features import extract, FS_DEFAULT

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

    print("  >>> RECORDING — Speak/Articulate Now! <<<", flush=True)
    
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

    print("\n" + "="*50)
    print("  ASV Live Word Predictor (CLI)")
    print("  To exit, press Ctrl+C or type 'q' then Enter.")
    print("="*50)

    try:
        while True:
            inp = input("\nPress Enter to start recording (2 seconds)... ").strip()
            if inp.lower() == 'q':
                break

            # Countdown
            for i in range(3, 0, -1):
                print(f"  Prepare in {i}...", end="\r", flush=True)
                time.sleep(1)
            print("  Ready!          ", end="\r", flush=True)
            
            # Capture
            counts = capture_utterance(conn, seconds=args.seconds)
            print(f"  Captured {len(counts)} samples.")

            if len(counts) < 32:
                print("  [ERROR] Capture too short or empty! Check connections.")
                continue

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
