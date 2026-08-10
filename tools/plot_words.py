#!/usr/bin/env python3
"""ASV — Live Word Plotter & OLED Alert (GUI)
==============================================
Plots the live EMG waveform in real time.
Pressing the Spacebar records 2 seconds of EMG data, runs the SVM model,
updates the Matplotlib GUI with the predicted word and class probabilities,
and sends the word over serial to update the physical OLED screen.

Usage:
    python tools/plot_words.py --port COM8
"""

import argparse
import sys
import time
import collections
import warnings
import json
from datetime import datetime
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import joblib
    import serial
    import serial.tools.list_ports
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
except ImportError as e:
    print(f"ERROR: missing dependency: {e}")
    print("Please run: pip install numpy joblib pyserial scikit-learn scipy matplotlib")
    sys.exit(1)

# Add repo root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.refined.utterance_features import extract, preprocess, FS_DEFAULT, UV_PER_LSB

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MODEL_DIR = REPO_ROOT / "refined_model"

def save_trial_to_disk(recorded_counts, label):
    # Target directory: datasets/custom_silent_speech/raw/S01/{label}/
    label = label.lower()
    subject = "S01"
    trial_dir = REPO_ROOT / "datasets" / "custom_silent_speech" / "raw" / subject / label
    trial_dir.mkdir(parents=True, exist_ok=True)

    # Find the next repetition number by looking at existing files
    existing_reps = []
    for csv in trial_dir.glob("rep*.csv"):
        stem = csv.stem.split("_")[0]
        rep_str = "".join(c for c in stem if c.isdigit())
        if rep_str:
            existing_reps.append(int(rep_str))
    
    rep_num = max(existing_reps) + 1 if existing_reps else 1

    # Timestamps and filenames
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"rep{rep_num:03d}_{ts_str}"
    csv_path = trial_dir / f"{base_name}.csv"
    meta_path = trial_dir / f"{base_name}_meta.json"

    # Separate timestamps and counts
    timestamps = np.array([s[0] for s in recorded_counts], dtype=np.int64)
    counts = np.array([s[1] for s in recorded_counts], dtype=np.float64)

    # Write CSV
    with open(csv_path, "w", newline="") as fh:
        fh.write("timestamp_us,channel_0\n")
        for t, v in zip(timestamps, counts):
            fh.write(f"{t},{int(v)}\n")

    # Calculate actual sampling rate and timing jitter
    jitter = {}
    actual_rate = 0.0
    if len(timestamps) >= 2:
        dt = np.diff(timestamps.astype(float))
        mean_dt = float(np.mean(dt))
        actual_rate = 1e6 / mean_dt if mean_dt > 0 else 0.0
        jitter = {
            "dt_mean": round(mean_dt, 3),
            "dt_std": round(float(np.std(dt)), 3),
            "dt_min": round(float(np.min(dt)), 3),
            "dt_max": round(float(np.max(dt)), 3),
            "unit": "us",
        }

    # Write Meta JSON
    meta = {
        "subject": subject,
        "label": label,
        "repetition": rep_num,
        "timestamp": ts_str,
        "n_samples": len(recorded_counts),
        "duration_sec": len(recorded_counts) / FS_DEFAULT,
        "configured_sampling_rate_hz": FS_DEFAULT,
        "actual_sampling_rate_hz": round(actual_rate, 2),
        "num_channels": 1,
        "timestamp_unit": "us",
        "timing_jitter": jitter,
        "source": "plot_words.py (live GUI)",
        "file": csv_path.name,
    }
    
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved trial to: {csv_path.relative_to(REPO_ROOT)}")

def counts_to_mv(counts):
    return (counts * UV_PER_LSB) / 1000.0

def main():
    parser = argparse.ArgumentParser(description="Live EMG Word Plotter & OLED Alert")
    parser.add_argument("--port", help="COM port for ESP32 (e.g. COM8)")
    parser.add_argument("--window", type=float, default=4.0, help="Live view time window in seconds")
    args = parser.parse_args()

    # 1. Load model artifacts
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
        classes = list(le.classes_)
        print(f"Model loaded successfully! Vocabulary: {classes}")
    except Exception as e:
        print(f"ERROR loading model: {e}")
        sys.exit(1)

    # 2. Select port
    port = args.port
    if not port:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("ERROR: No serial ports found. Connect the ESP32.")
            sys.exit(1)
        target_ports = [p.device for p in ports if "Silicon Labs" in (p.description or "")]
        if target_ports:
            port = target_ports[0]
        else:
            port = ports[0].device
        print(f"Auto-selected port: {port}")

    # 3. Open Serial
    print(f"Connecting to ESP32 on {port} at 921600 baud...")
    try:
        ser = serial.Serial(port, 921600, timeout=1)
        time.sleep(1.5)  # Wait for ESP32 reset
        ser.reset_input_buffer()
        ser.write(b's')  # Start streaming
    except Exception as e:
        print(f"ERROR: {e}")
        print("Make sure no other serial monitor is using this port.")
        sys.exit(1)

    # 4. Set up live data buffers
    window_sec = args.window
    buf_size = int(FS_DEFAULT * window_sec)
    live_times = collections.deque([0.0] * buf_size, maxlen=buf_size)
    live_values = collections.deque([0.0] * buf_size, maxlen=buf_size)

    # State variables for recording
    is_recording = False
    rec_start_time = 0.0
    recorded_counts = []
    
    # Prediction display state
    pred_word = ""
    pred_conf = 0.0
    pred_probs = [0.0] * len(classes)
    pred_show_until = 0.0

    # 5. Build Matplotlib GUI
    fig, (ax_raw, ax_probs) = plt.subplots(2, 1, figsize=(11, 7), 
                                          gridspec_kw={'height_ratios': [3, 2]})
    fig.canvas.manager.set_window_title("ASV — Real-Time Word Detector")
    fig.patch.set_facecolor('#0a0a16')

    # Apply styling to axes
    for ax in (ax_raw, ax_probs):
        ax.set_facecolor('#0f0f22')
        ax.tick_params(colors='#8888aa', labelsize=9)
        for spine in ax.spines.values():
            spine.set_color('#1c1c3c')
            spine.set_linewidth(1.5)

    # Waveform Plot config
    line_raw, = ax_raw.plot([], [], color='#00ffd2', linewidth=1.0, alpha=0.95, label='Live EMG (mV)')
    ax_raw.set_ylabel('mV', color='#8888aa', fontsize=10)
    ax_raw.set_xlabel('time (s)', color='#8888aa', fontsize=10)
    ax_raw.set_xlim(0, window_sec)
    ax_raw.set_ylim(-200, 3500)
    ax_raw.axhline(1635, color='#ff6b35', linewidth=0.8, linestyle='--', label='expected baseline ~1635mV')
    ax_raw.legend(loc='upper right', facecolor='#0a0a16', edgecolor='#1c1c3c', labelcolor='#8888aa', fontsize=9)
    ax_raw.grid(True, color='#181832', linewidth=0.5)

    # Overlay texts on Raw plot
    rec_banner = ax_raw.text(0.5, 0.90, '', transform=ax_raw.transAxes,
                              color='#ff0055', fontsize=16, fontweight='bold', ha='center',
                              bbox=dict(facecolor='#0a0a16', edgecolor='#ff0055', boxstyle='round,pad=0.4', alpha=0.85))
    rec_banner.set_visible(False)

    pred_banner = ax_raw.text(0.5, 0.45, '', transform=ax_raw.transAxes,
                               color='#00ff66', fontsize=32, fontweight='bold', ha='center',
                               bbox=dict(facecolor='#0a0a16', edgecolor='#00ff66', boxstyle='round,pad=0.6', alpha=0.9))
    pred_banner.set_visible(False)

    # Horizontal Bar Chart for probabilities
    y_pos = np.arange(len(classes))
    bars = ax_probs.barh(y_pos, pred_probs, align='center', color='#5a0099', height=0.6)
    ax_probs.set_yticks(y_pos)
    ax_probs.set_yticklabels(classes, fontsize=10, color='#8888aa', fontweight='bold')
    ax_probs.invert_yaxis()  # top-down list
    ax_probs.set_xlabel('Probability', color='#8888aa', fontsize=10)
    ax_probs.set_xlim(0, 1.0)
    ax_probs.grid(True, axis='x', color='#181832', linewidth=0.5)
    
    # Instruction text
    instruction_text = fig.text(0.5, 0.02, "Press [Spacebar] to record (2 seconds)  |  Press [Q] or close window to quit",
                                transform=fig.transFigure, color='#8888aa', fontsize=10, ha='center', fontfamily='monospace')

    # Serial parsing
    t0 = None
    line_buf = b''
    last_stat_time = time.time()
    sample_count = 0
    measured_rate = 0.0

    def parse_serial():
        nonlocal line_buf, t0, sample_count, measured_rate, last_stat_time
        if ser.in_waiting == 0:
            return
        
        chunk = ser.read(ser.in_waiting)
        line_buf += chunk
        
        while b'\n' in line_buf:
            raw, line_buf = line_buf.split(b'\n', 1)
            raw = raw.strip()
            
            # Skip comments/metadata lines
            if not raw or raw.startswith(b'#') or raw.startswith(b'-') or raw.startswith(b'['):
                continue
                
            try:
                parts = raw.decode('ascii', errors='ignore').split(',')
                if len(parts) >= 2:
                    ts_us = int(parts[0])
                    ch0 = int(parts[1])
                    
                    if t0 is None:
                        t0 = ts_us
                        
                    t_rel = (ts_us - t0) / 1e6
                    mv = counts_to_mv(ch0)
                    
                    live_times.append(t_rel)
                    live_values.append(mv)
                    sample_count += 1
                    
                    if is_recording:
                        recorded_counts.append((ts_us, ch0))
            except Exception:
                pass

        # Update sample rate statistics
        now = time.time()
        elapsed = now - last_stat_time
        if elapsed >= 1.0:
            measured_rate = sample_count / elapsed
            sample_count = 0
            last_stat_time = now

    # Key press handler
    def on_key(event):
        nonlocal is_recording, rec_start_time, recorded_counts, pred_show_until
        if event.key == ' ':
            if not is_recording:
                print("\nSpacebar pressed. Starting 2-second capture...")
                recorded_counts = []
                rec_start_time = time.time()
                is_recording = True
                pred_show_until = 0.0  # Hide previous prediction
                rec_banner.set_visible(True)
                pred_banner.set_visible(False)
        elif event.key in ('q', 'Q'):
            plt.close()

    fig.canvas.mpl_connect('key_press_event', on_key)

    # Animation update loop
    def update(frame):
        nonlocal is_recording, pred_word, pred_conf, pred_probs, pred_show_until
        
        parse_serial()
        now = time.time()

        # Handle recording completion
        if is_recording and (now - rec_start_time >= 2.0):
            is_recording = False
            rec_banner.set_visible(False)
            print(f"Recording finished. Captured {len(recorded_counts)} samples.")
            
            if len(recorded_counts) >= 32:
                # Extract counts for classification
                counts = [s[1] for s in recorded_counts]
                x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
                pred_word = le.inverse_transform(clf.predict(x))[0].upper()
                
                if hasattr(clf, "predict_proba"):
                    probs = clf.predict_proba(x)[0]
                    pred_probs = list(probs)
                    pred_conf = float(np.max(probs))
                else:
                    pred_probs = [0.0] * len(classes)
                    # Set 1.0 for the predicted class, 0.0 for others
                    pred_probs[classes.index(pred_word.lower())] = 1.0
                    pred_conf = 1.0
                
                print(f"Prediction: {pred_word} (confidence {pred_conf:.0%})")
                
                # Save the captured trial to the raw datasets folder
                try:
                    save_trial_to_disk(recorded_counts, pred_word)
                except Exception as e:
                    print(f"Error saving trial to disk: {e}")
                
                # Send predicted word over Serial to the ESP32 OLED
                # Command format is 'w[WORD]\n'
                try:
                    ser.write(f"w{pred_word}\n".encode())
                    print(f"Sent 'w{pred_word}\\n' to ESP32 OLED.")
                except Exception as e:
                    print(f"Warning: failed to send prediction to ESP32: {e}")
                
                pred_show_until = now + 4.0  # Display for 4 seconds
            else:
                print("Error: Capture too short to classify!")

        # Update GUI elements
        t_arr = np.array(live_times)
        mv_arr = np.array(live_values)

        if len(mv_arr) > 1:
            t_end = t_arr[-1]
            t_start = max(t_end - window_sec, 0.0)
            mask = t_arr >= t_start
            
            # Shift x axis relative to window start
            line_raw.set_data(t_arr[mask] - t_start, mv_arr[mask])
            ax_raw.set_xlim(0, window_sec)
            
            # Auto scale raw amplitude axis
            baseline = np.mean(mv_arr[-buf_size:])
            ptp = np.ptp(mv_arr[-buf_size:])
            auto_min = max(-200, baseline - max(500, ptp * 1.3))
            auto_max = baseline + max(500, ptp * 1.3)
            ax_raw.set_ylim(auto_min, auto_max)

        # Pulsing recording text
        if is_recording:
            elapsed_rec = now - rec_start_time
            # Pulse text opacity or draw a countdown progress bar
            rec_banner.set_text(f"● RECORDING — SPEAK NOW  ({2.0 - elapsed_rec:.1f}s)")

        # Show/Hide prediction overlay
        if now < pred_show_until:
            pred_banner.set_text(f"{pred_word}\n{pred_conf:.0%}")
            pred_banner.set_visible(True)
        else:
            pred_banner.set_visible(False)

        # Update bar chart heights
        for i, bar in enumerate(bars):
            prob = pred_probs[i]
            bar.set_width(prob)
            # Make the predicted bar cyan, and others purple
            if classes[i].upper() == pred_word and now < pred_show_until:
                bar.set_color('#00ffd2')
            else:
                bar.set_color('#5a0099')

        ax_raw.set_title(f"Live Stream: {measured_rate:.0f} Hz  |  Baseline: {np.mean(mv_arr[-100:] if len(mv_arr) > 0 else 0):.0f} mV", 
                         color='#dddddd', fontsize=11, fontweight='bold')
        
        return line_raw, rec_banner, pred_banner, bars

    # Run matplotlib animation
    ani = animation.FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

    # Cleanup on exit
    print("\nClosing serial port...")
    try:
        ser.write(b'x')  # Stop streaming
        ser.close()
    except:
        pass
    print("Closed.")

if __name__ == '__main__':
    main()
