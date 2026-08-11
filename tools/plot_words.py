#!/usr/bin/env python3
"""ASV — Live Word Plotter & OLED Alert (GUI)
==============================================
Plots the live EMG waveform in real time. Pressing the Spacebar captures an
utterance, runs it through the refined model, updates the GUI with the
predicted word and class probabilities, and sends the word over serial to
the ESP32 OLED.

Usage:
    python tools/plot_words.py --port COM8

Keys:
    SPACE   capture + classify (~2s, includes a pre-roll safety margin)
    S       save the last capture as unverified data (NOT auto-trusted)
    Q       quit

--------------------------------------------------------------------------
Why v2 (read this if predictions were stuck on "REST")
--------------------------------------------------------------------------
v1 parsed the serial port inside the matplotlib animation callback. If a
render frame took longer than expected (a slow machine, a big legend
redraw, etc.), the OS serial receive buffer could fill up while nobody was
draining it, and the "2 seconds" of capture ended up holding far fewer real
samples than that. A capture that's actually ~0.2-0.5s of real signal padded
to look like 2s classifies as "rest" almost every time, at a confidence
(~45-50%) that *looks* real but is barely above chance (20% for 5 classes) --
this was reproduced offline: truncating a real "yes" recording to 0.24s of
its own samples flips the model's answer to "rest" at 46% confidence.

v2 fixes this by moving serial ingestion to a background thread with its own
continuously-filled ring buffer (SerialStreamer below). The GUI just reads a
snapshot of that buffer to draw; a slow frame can never cause a dropped
sample. Capture windows are also sliced from that buffer, not accumulated
only while "recording" -- this adds free pre-roll so a keypress made a beat
late (or early) still gets the full utterance.

It also adds a live signal-health readout (baseline / peak-to-peak), because
the other realistic cause of "always rest" is bad electrode contact, not a
software bug -- see docs/CURRENT_SYSTEM_AUDIT.md and the debugging plots
from the first bring-up session (test.png, clench_test.png).
"""

import argparse
import sys
import time
import threading
import collections
import warnings
import json
from datetime import datetime
from pathlib import Path

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.refined.utterance_features import (
    extract, FS_DEFAULT, UV_PER_LSB, signal_health,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MODEL_DIR = REPO_ROOT / "refined_model"

PRE_ROLL_SEC = 0.4     # captured BEFORE the keypress (reaction-time safety margin)
POST_ROLL_SEC = 1.6    # captured AFTER the keypress
CAPTURE_SEC = PRE_ROLL_SEC + POST_ROLL_SEC   # ~2.0s total, matches training


# ============================================================================
# Background serial reader — decoupled from the GUI so a slow render frame
# can never starve the capture.
# ============================================================================
class SerialStreamer:
    def __init__(self, ser, maxlen_seconds=8, fs=FS_DEFAULT):
        self.ser = ser
        self.buf = collections.deque(maxlen=int(fs * maxlen_seconds))  # (recv_t, ts_us, ch0)
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self._rate_n = 0
        self._rate_t0 = time.time()
        self.measured_rate = 0.0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        line_buf = b""
        while self.running:
            try:
                n = self.ser.in_waiting
                chunk = self.ser.read(n or 1)
            except Exception:
                break
            if not chunk:
                continue
            line_buf += chunk
            while b"\n" in line_buf:
                raw, line_buf = line_buf.split(b"\n", 1)
                raw = raw.strip()
                if not raw or raw[:1] in (b"#", b"-", b"["):
                    continue
                try:
                    s = raw.decode("ascii", errors="ignore")
                    comma = s.index(",")
                    ts_us = int(s[:comma])
                    ch0 = int(s[comma + 1:])
                except Exception:
                    continue
                recv_t = time.time()
                with self.lock:
                    self.buf.append((recv_t, ts_us, ch0))
                self._rate_n += 1
            now = time.time()
            if now - self._rate_t0 >= 1.0:
                self.measured_rate = self._rate_n / (now - self._rate_t0)
                self._rate_n = 0
                self._rate_t0 = now

    def snapshot(self):
        with self.lock:
            return list(self.buf)

    def window(self, t_start, t_end):
        """All samples whose local receive time falls in [t_start, t_end]."""
        with self.lock:
            return [d for d in self.buf if t_start <= d[0] <= t_end]

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)


def counts_to_mv(counts):
    return (np.asarray(counts, dtype=float) * UV_PER_LSB) / 1000.0


def save_unverified(recorded, predicted_label, confidence):
    """Save a live capture WITHOUT touching the trusted training set.

    Trusted training data lives under datasets/custom_silent_speech/raw/ and
    is only ever written by ml/acquisition/collect_emg.py (a deliberate,
    ground-truth-labelled protocol). Auto-saving live GUI captures into that
    tree under the model's OWN prediction would silently poison future
    retraining with the model's mistakes. This writes to a separate
    live_unverified/ tree instead, tagged with the predicted label and
    confidence so a human can review and promote it later if it's correct.
    """
    label = predicted_label.lower()
    out_dir = REPO_ROOT / "datasets" / "custom_silent_speech" / "live_unverified" / label
    out_dir.mkdir(parents=True, exist_ok=True)

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"pred_{label}_conf{int(confidence*100):02d}_{ts_str}"
    csv_path = out_dir / f"{base}.csv"
    meta_path = out_dir / f"{base}_meta.json"

    with open(csv_path, "w", newline="") as fh:
        fh.write("timestamp_us,channel_0\n")
        for _, ts_us, ch0 in recorded:
            fh.write(f"{ts_us},{int(ch0)}\n")

    meta = {
        "predicted_label": label,
        "confidence": round(float(confidence), 4),
        "n_samples": len(recorded),
        "source": "plot_words.py v2 (live GUI, UNVERIFIED)",
        "verified": False,
        "note": "Not part of the trusted training set. Review and move into "
                "datasets/custom_silent_speech/raw/<subject>/<label>/ manually if correct.",
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved (unverified): {csv_path.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="Live EMG Word Plotter & OLED Alert")
    parser.add_argument("--port", help="COM port for ESP32 (e.g. COM8)")
    parser.add_argument("--window", type=float, default=4.0, help="Plot time window in seconds")
    parser.add_argument("--pre-roll", type=float, default=PRE_ROLL_SEC,
                        help="Seconds captured BEFORE the keypress")
    parser.add_argument("--post-roll", type=float, default=POST_ROLL_SEC,
                        help="Seconds captured AFTER the keypress")
    args = parser.parse_args()
    pre_roll, post_roll = args.pre_roll, args.post_roll

    clf_path = MODEL_DIR / "classifier.pkl"
    le_path = MODEL_DIR / "label_encoder.pkl"
    if not (clf_path.exists() and le_path.exists()):
        print(f"ERROR: Model files not found in {MODEL_DIR}")
        print("Please train a model first using: python ml/refined/train_refined.py")
        sys.exit(1)

    print("Loading refined model...")
    clf = joblib.load(clf_path)
    le = joblib.load(le_path)
    classes = list(le.classes_)
    print(f"Model loaded. Vocabulary: {classes}")

    port = args.port
    if not port:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("ERROR: No serial ports found. Connect the ESP32.")
            sys.exit(1)
        target = [p.device for p in ports if "Silicon Labs" in (p.description or "")]
        port = target[0] if target else ports[0].device
        print(f"Auto-selected port: {port}")

    print(f"Connecting to ESP32 on {port} at 921600 baud...")
    try:
        ser = serial.Serial(port, 921600, timeout=0)  # non-blocking; thread polls
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.write(b"s")
    except Exception as e:
        print(f"ERROR: {e}")
        print("Make sure no other serial monitor is using this port.")
        sys.exit(1)

    streamer = SerialStreamer(ser, maxlen_seconds=max(8, args.window + 4))
    streamer.start()

    # ---- state ----
    is_recording = False
    rec_trigger_t = 0.0
    rec_deadline_t = 0.0
    last_captured = None          # (recorded_list, pred_word, conf)

    pred_word, pred_conf = "", 0.0
    pred_probs = [0.0] * len(classes)
    pred_show_until = 0.0
    save_flash_until = 0.0

    # ---- GUI ----
    fig, (ax_raw, ax_probs) = plt.subplots(2, 1, figsize=(11, 7),
                                          gridspec_kw={"height_ratios": [3, 2]})
    fig.canvas.manager.set_window_title("ASV — Real-Time Word Detector (v2)")
    fig.patch.set_facecolor("#0a0a16")
    for ax in (ax_raw, ax_probs):
        ax.set_facecolor("#0f0f22")
        ax.tick_params(colors="#8888aa", labelsize=9)
        for sp in ax.spines.values():
            sp.set_color("#1c1c3c"); sp.set_linewidth(1.5)

    line_raw, = ax_raw.plot([], [], color="#00ffd2", linewidth=1.0, alpha=0.95, label="Live EMG (mV)")
    ax_raw.set_ylabel("mV", color="#8888aa", fontsize=10)
    ax_raw.set_xlabel("time (s)", color="#8888aa", fontsize=10)
    ax_raw.set_xlim(0, args.window)
    ax_raw.set_ylim(-200, 3500)
    ax_raw.axhline(1635, color="#ff6b35", linewidth=0.8, linestyle="--", label="expected baseline ~1635mV")
    ax_raw.legend(loc="upper right", facecolor="#0a0a16", edgecolor="#1c1c3c", labelcolor="#8888aa", fontsize=9)
    ax_raw.grid(True, color="#181832", linewidth=0.5)

    health_text = ax_raw.text(0.01, 0.95, "", transform=ax_raw.transAxes,
                              color="#8888aa", fontsize=9, va="top", fontfamily="monospace")

    rec_banner = ax_raw.text(0.5, 0.90, "", transform=ax_raw.transAxes,
                             color="#ff0055", fontsize=16, fontweight="bold", ha="center",
                             bbox=dict(facecolor="#0a0a16", edgecolor="#ff0055", boxstyle="round,pad=0.4", alpha=0.85))
    rec_banner.set_visible(False)

    pred_banner = ax_raw.text(0.5, 0.45, "", transform=ax_raw.transAxes,
                              color="#00ff66", fontsize=32, fontweight="bold", ha="center",
                              bbox=dict(facecolor="#0a0a16", edgecolor="#00ff66", boxstyle="round,pad=0.6", alpha=0.9))
    pred_banner.set_visible(False)

    save_banner = ax_raw.text(0.5, 0.08, "", transform=ax_raw.transAxes,
                              color="#ffcc00", fontsize=11, fontweight="bold", ha="center")

    y_pos = np.arange(len(classes))
    bars = ax_probs.barh(y_pos, pred_probs, align="center", color="#5a0099", height=0.6)
    ax_probs.set_yticks(y_pos)
    ax_probs.set_yticklabels(classes, fontsize=10, color="#8888aa", fontweight="bold")
    ax_probs.invert_yaxis()
    ax_probs.set_xlabel("Probability", color="#8888aa", fontsize=10)
    ax_probs.set_xlim(0, 1.0)
    ax_probs.grid(True, axis="x", color="#181832", linewidth=0.5)

    fig.text(0.5, 0.02,
             "[SPACE] capture & classify   |   [S] save last capture (unverified)   |   [Q] quit",
             transform=fig.transFigure, color="#8888aa", fontsize=10, ha="center", fontfamily="monospace")

    def on_key(event):
        nonlocal is_recording, rec_trigger_t, rec_deadline_t, pred_show_until, save_flash_until
        if event.key == " ":
            if not is_recording:
                print("\n[SPACE] Capturing utterance...")
                rec_trigger_t = time.time()
                rec_deadline_t = rec_trigger_t + post_roll
                is_recording = True
                pred_show_until = 0.0
                rec_banner.set_visible(True)
                pred_banner.set_visible(False)
        elif event.key in ("s", "S"):
            if last_captured is not None:
                recorded, lw, lc = last_captured
                save_unverified(recorded, lw, lc)
                save_flash_until = time.time() + 2.0
            else:
                print("Nothing to save yet — capture a word first (SPACE).")
        elif event.key in ("q", "Q"):
            plt.close()

    fig.canvas.mpl_connect("key_press_event", on_key)

    def update(frame):
        nonlocal is_recording, pred_word, pred_conf, pred_probs, pred_show_until, last_captured

        now = time.time()
        data = streamer.snapshot()

        # finalize a capture once the post-roll deadline passes
        if is_recording and now >= rec_deadline_t:
            is_recording = False
            rec_banner.set_visible(False)
            window = [d for d in data if (rec_trigger_t - pre_roll) <= d[0] <= rec_deadline_t]
            print(f"Captured {len(window)} samples "
                  f"(~{len(window)/FS_DEFAULT:.2f}s, expected ~{CAPTURE_SEC:.1f}s).")

            if len(window) >= 32:
                counts = [d[2] for d in window]
                health = signal_health(counts)
                x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
                pred_word = le.inverse_transform(clf.predict(x))[0].upper()
                if hasattr(clf, "predict_proba"):
                    probs = clf.predict_proba(x)[0]
                    pred_probs = list(probs)
                    pred_conf = float(np.max(probs))
                else:
                    pred_probs = [1.0 if c.upper() == pred_word else 0.0 for c in classes]
                    pred_conf = 1.0

                warn = "" if health["ok"] else f"  [WARNING: {health['status']} — check electrodes]"
                print(f"Prediction: {pred_word} (confidence {pred_conf:.0%}){warn}")
                if not health["ok"]:
                    print(f"  baseline={health['baseline_mv']}mV pp={health['pp_mv']}mV "
                          f"(expect ~1635mV baseline, >3mV pp)")

                last_captured = ([(0.0, ts, ch) for _, ts, ch in window], pred_word, pred_conf)

                try:
                    ser.write(f"w{pred_word}\n".encode())
                except Exception as e:
                    print(f"Warning: failed to send prediction to ESP32 OLED: {e}")

                pred_show_until = now + 4.0
            else:
                print("Capture too short to classify (serial not connected / no data).")

        # ---- draw waveform from the last `window` seconds of the buffer ----
        if data:
            t_end = data[-1][0]
            t_start = t_end - args.window
            recent = [d for d in data if d[0] >= t_start]
            t_arr = np.array([d[0] - t_start for d in recent])
            mv_arr = counts_to_mv([d[2] for d in recent])
            line_raw.set_data(t_arr, mv_arr)
            ax_raw.set_xlim(0, args.window)
            if len(mv_arr) > 1:
                baseline = float(np.mean(mv_arr[-int(FS_DEFAULT):]))
                ptp = float(np.ptp(mv_arr[-int(FS_DEFAULT):]))
                auto_min = max(-200, baseline - max(500, ptp * 1.3))
                auto_max = baseline + max(500, ptp * 1.3)
                ax_raw.set_ylim(auto_min, auto_max)

                last_1s = [d[2] for d in data if d[0] >= t_end - 1.0]
                health = signal_health(last_1s)
                color = "#00ff66" if health["ok"] else "#ff3355"
                status_msg = {"OK": "signal OK", "FLAT": "FLAT — check electrode contact",
                             "RAILED_OR_OFFSET": "RAILED — check RL electrode placement",
                             "NO_DATA": "no data"}[health["status"]]
                health_text.set_text(
                    f"rate={streamer.measured_rate:.0f} Hz  baseline={health['baseline_mv']:.0f} mV  "
                    f"pp={health['pp_mv']:.1f} mV  [{status_msg}]")
                health_text.set_color(color)
        else:
            health_text.set_text("waiting for data...")

        if is_recording:
            remaining = max(0.0, rec_deadline_t - now)
            rec_banner.set_text(f"● CAPTURING — SPEAK NOW  ({remaining:.1f}s)")

        if now < pred_show_until:
            pred_banner.set_text(f"{pred_word}\n{pred_conf:.0%}")
            pred_banner.set_visible(True)
        else:
            pred_banner.set_visible(False)

        save_banner.set_text("Saved (unverified) — press again after next capture" if now < save_flash_until else "")

        for i, bar in enumerate(bars):
            prob = pred_probs[i]
            bar.set_width(prob)
            bar.set_color("#00ffd2" if classes[i].upper() == pred_word and now < pred_show_until else "#5a0099")

        ax_raw.set_title("Live Stream", color="#dddddd", fontsize=11, fontweight="bold")
        return line_raw, rec_banner, pred_banner, health_text, bars

    ani = animation.FuncAnimation(fig, update, interval=40, blit=False, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

    print("\nClosing...")
    streamer.stop()
    try:
        ser.write(b"x")
        ser.close()
    except Exception:
        pass
    print("Closed.")


if __name__ == "__main__":
    main()
