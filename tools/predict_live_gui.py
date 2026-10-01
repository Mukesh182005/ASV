#!/usr/bin/env python3
"""ASV — Live Word Tester (GUI)
==============================
Tkinter front-end for the refined utterance model. Speak/articulate a word
while wired up and see YES / NO / HELLO / HELP / REST predicted live.

Usage:
    python tools/predict_live_gui.py --port COM5
    python tools/predict_live_gui.py            # auto-detects the port
"""
import argparse
import sys
import threading
import time
import tkinter as tk
import warnings
from pathlib import Path

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.refined.utterance_features import extract, FS_DEFAULT, signal_health
from ml.acquisition.serial_reader import EMGSerialReader

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "refined_model"

RECORD_SECONDS = 5.0
COUNTDOWN_SECONDS = 3

WORD_COLORS = {
    "yes": "#00ff6a",
    "no": "#ff4d4d",
    "hi": "#00bfff",
    "help": "#ffaa00",
    "rest": "#888888",
}
DEFAULT_COLOR = "#e0e0e0"


def auto_select_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    silabs = [p.device for p in ports if "Silicon Labs" in (p.description or "")]
    return silabs[0] if silabs else ports[0].device


class WordTesterGUI:
    def __init__(self, port=None, baud=921600):
        self.port = port or auto_select_port()
        self.baud = baud
        self.reader = None
        self.connected = False
        self.busy = False

        self.classifier = None
        self.label_encoder = None
        self.model_error = None
        self._load_model()

        self.root = tk.Tk()
        self.root.title("ASV — Live Word Tester")
        self.root.geometry("460x560")
        self.root.configure(bg="#141414")
        self._build_ui()

        if self.model_error:
            self._set_status(self.model_error, "#ff4d4d")
            self.btn_record.config(state="disabled")
        elif not self.port:
            self._set_status("No serial port found. Plug in the ESP32.", "#ff4d4d")
            self.btn_record.config(state="disabled")
        else:
            self._set_status(f"Ready — port {self.port}", "#888888")
            threading.Thread(target=self._connect_and_check_baseline, daemon=True).start()

    # ------------------------------------------------------------------ model
    def _load_model(self):
        clf_path = MODEL_DIR / "classifier.pkl"
        le_path = MODEL_DIR / "label_encoder.pkl"
        if not (clf_path.exists() and le_path.exists()):
            self.model_error = f"No model found in {MODEL_DIR}"
            return
        try:
            self.classifier = joblib.load(clf_path)
            self.label_encoder = joblib.load(le_path)
        except Exception as e:
            self.model_error = f"Failed to load model: {e}"

    # -------------------------------------------------------------------- UI
    def _build_ui(self):
        font_title = ("Helvetica", 15, "bold")
        font_label = ("Helvetica", 11)
        font_pred = ("Helvetica", 40, "bold")
        font_status = ("Helvetica", 12)

        tk.Label(self.root, text="ASV — LIVE WORD TESTER", font=font_title,
                 fg="white", bg="#141414").pack(pady=(18, 4))

        vocab = ", ".join(self.label_encoder.classes_) if self.label_encoder is not None else "?"
        tk.Label(self.root, text=f"vocabulary: {vocab}", font=("Helvetica", 9),
                 fg="#666666", bg="#141414").pack()

        self.lbl_status = tk.Label(self.root, text="", font=font_status,
                                    fg="#888888", bg="#141414", wraplength=420)
        self.lbl_status.pack(pady=(10, 0))

        self.lbl_countdown = tk.Label(self.root, text="", font=("Helvetica", 22, "bold"),
                                       fg="#ffcc00", bg="#141414")
        self.lbl_countdown.pack(pady=(6, 0))

        pred_frame = tk.Frame(self.root, bg="#141414")
        pred_frame.pack(pady=(20, 6))
        tk.Label(pred_frame, text="PREDICTION", font=font_label,
                 fg="#aaaaaa", bg="#141414").pack()
        self.lbl_pred = tk.Label(pred_frame, text="—", font=font_pred,
                                  fg=DEFAULT_COLOR, bg="#141414")
        self.lbl_pred.pack()

        self.lbl_conf = tk.Label(self.root, text="", font=("Helvetica", 13),
                                  fg="#cccccc", bg="#141414")
        self.lbl_conf.pack(pady=(0, 10))

        self.ranking_frame = tk.Frame(self.root, bg="#141414")
        self.ranking_frame.pack(pady=(0, 16))
        self.ranking_labels = []

        self.btn_record = tk.Button(self.root, text="●  RECORD (speak the word)",
                                     font=("Helvetica", 13, "bold"), bg="#c02020", fg="white",
                                     activebackground="#e03030", relief="flat",
                                     padx=14, pady=10, command=self._on_record_clicked)
        self.btn_record.pack(pady=(4, 10))

        tk.Label(self.root, text="Log", font=("Helvetica", 10, "bold"),
                 fg="#888888", bg="#141414").pack(anchor="w", padx=16)
        log_frame = tk.Frame(self.root, bg="#141414")
        log_frame.pack(fill="both", expand=True, padx=16, pady=(2, 16))
        self.txt_log = tk.Text(log_frame, height=8, bg="#1e1e1e", fg="#cccccc",
                                font=("Consolas", 9), relief="flat", wrap="word")
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.config(state="disabled")

    def _set_status(self, text, color="#888888"):
        self.lbl_status.config(text=text, fg=color)

    def _log(self, text):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", text + "\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    # --------------------------------------------------------------- serial
    # NOTE: the stream is opened ONCE here and left running for the whole
    # session (reader.read_samples() just drains it) — this must match
    # collect_emg.py's protocol exactly. An earlier version of this tool sent
    # 'x' then 's' before every single capture; that stop/restart added
    # latency right after the "SPEAK NOW" cue (clipping short words) and put
    # a startup transient at the front of every window that the classifier
    # read as a burst, so silence never scored as REST. Training data was
    # never affected — only this live-capture path was wrong.
    def _connect_and_check_baseline(self):
        self.reader = EMGSerialReader(self.port, baud_rate=self.baud, num_channels=1)
        if not self.reader.connect():
            self._async(lambda: self._set_status(
                f"Could not open {self.port}. Check the port / that nothing else has it open.",
                "#ff4d4d"))
            return
        self.connected = True
        self._async(lambda: self._set_status("Checking electrode contact...", "#888888"))
        result = self.reader.read_samples(1.0)
        samples = result["channels"][:, 0] if len(result["channels"]) else []
        health = signal_health(samples)
        if health["status"] == "NO_DATA":
            self._async(lambda: self._set_status(
                "No data from board — check port / firmware self-test.", "#ff4d4d"))
            return
        msg = f"baseline={health['baseline_mv']}mV  pp={health['pp_mv']}mV → {health['status']}"
        color = "#5fd35f" if health["ok"] else "#ffcc00"
        self._async(lambda: self._set_status(msg, color))
        if health["status"] == "SATURATED_OR_HUM":
            self._async(lambda: self._log(
                "[STOP] Peak-to-peak is far above the range the model was trained on "
                "(good data is 56-498 mV). This is almost always 50 Hz mains hum, not muscle. "
                "Predictions will be meaningless. Run: python tools/check_interference.py"))
        elif not health["ok"]:
            self._async(lambda: self._log("[WARNING] Signal unhealthy — predictions may be unreliable."))

    def _capture_utterance(self, seconds):
        result = self.reader.read_samples(seconds)
        channels = result["channels"]
        return channels[:, 0] if len(channels) else []

    # ------------------------------------------------------------- actions
    def _async(self, fn):
        self.root.after(0, fn)

    def _on_record_clicked(self):
        if self.busy:
            return
        if not self.connected:
            self._set_status("Not connected to the board.", "#ff4d4d")
            return
        self.busy = True
        self.btn_record.config(state="disabled")
        self.lbl_pred.config(text="—", fg=DEFAULT_COLOR)
        self.lbl_conf.config(text="")
        self._clear_ranking()
        threading.Thread(target=self._record_flow, daemon=True).start()

    def _record_flow(self):
        for i in range(COUNTDOWN_SECONDS, 0, -1):
            self._async(lambda i=i: self.lbl_countdown.config(text=f"prepare... {i}"))
            time.sleep(1)
        self._async(lambda: self.lbl_countdown.config(text="\U0001f5e3  SPEAK NOW", fg="#ff4444"))

        counts = self._capture_utterance(RECORD_SECONDS)

        self._async(lambda: self.lbl_countdown.config(text="processing...", fg="#ffcc00"))

        if len(counts) < 32:
            self._async(lambda: self._finish_with_error("Capture too short/empty — check connections."))
            return

        cap_health = signal_health(counts)
        if not cap_health["ok"]:
            err_msg = f"{cap_health['status']}: pp={cap_health['pp_mv']:.0f}mV (check electrodes/unplug charger)"
            self._async(lambda: self._finish_with_error(err_msg))
            return

        x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)
        pred = self.label_encoder.inverse_transform(self.classifier.predict(x))[0]
        ranking = None
        conf = None
        if hasattr(self.classifier, "predict_proba"):
            p = self.classifier.predict_proba(x)[0]
            conf = float(np.max(p))
            ranking = sorted(zip(self.label_encoder.classes_, p), key=lambda t: -t[1])

        # Hand the word to the firmware as "w<word>\n". It lands on the OLED and
        # goes out over BLE in the same step, so the phone shows exactly what the
        # display shows. Nothing on the ESP32 classifies -- this is the route.
        self._send_word_to_board(pred)

        self._async(lambda: self._finish_with_result(pred, conf, ranking, len(counts)))

    def _send_word_to_board(self, word):
        conn = getattr(self.reader, "serial_conn", None)
        if not conn or not word:
            return
        try:
            conn.write(f"w{word}\n".encode("ascii", errors="ignore"))
        except Exception as e:
            self._async(lambda: self._log(f"[WARNING] could not send word to board: {e}"))

    def _finish_with_error(self, msg):
        self.lbl_countdown.config(text="")
        self._set_status(msg, "#ff4d4d")
        self._log(f"[ERROR] {msg}")
        self.busy = False
        self.btn_record.config(state="normal")

    def _finish_with_result(self, pred, conf, ranking, n_samples):
        self.lbl_countdown.config(text="", fg="#ffcc00")
        color = WORD_COLORS.get(pred, DEFAULT_COLOR)
        self.lbl_pred.config(text=pred.upper(), fg=color)
        if conf is not None:
            self.lbl_conf.config(text=f"confidence {conf:.0%}  ({n_samples} samples)")
        self._clear_ranking()
        if ranking:
            for word, prob in ranking:
                bar = tk.Frame(self.ranking_frame, bg="#141414")
                bar.pack(fill="x", pady=2, padx=20)
                c = WORD_COLORS.get(word, "#aaaaaa")
                tk.Label(bar, text=f"{word.upper():6s}", font=("Consolas", 10, "bold"), fg=c,
                         bg="#141414", width=7, anchor="w").pack(side="left")
                
                # Visual probability meter canvas
                canvas = tk.Canvas(bar, width=150, height=12, bg="#222222", highlightthickness=0)
                canvas.pack(side="left", padx=8)
                fill_w = int(150 * prob)
                if fill_w > 0:
                    canvas.create_rectangle(0, 0, fill_w, 12, fill=c, width=0)

                tk.Label(bar, text=f"{prob:5.1%}", font=("Consolas", 10), fg="#cccccc",
                         bg="#141414").pack(side="left")
                self.ranking_labels.append(bar)
        self._log(f"[{time.strftime('%H:%M:%S')}] prediction={pred}  "
                   f"conf={conf:.0%}" if conf is not None else f"prediction={pred}")
        self.busy = False
        self.btn_record.config(state="normal")

    def _clear_ranking(self):
        for w in self.ranking_labels:
            w.destroy()
        self.ranking_labels = []

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        try:
            if self.reader:
                self.reader.disconnect()
        except Exception:
            pass
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Live Word Tester (GUI)")
    parser.add_argument("--port", default=None, help="Serial port (auto-detected if omitted)")
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate (default: 921600)")
    args = parser.parse_args()

    app = WordTesterGUI(port=args.port, baud=args.baud)
    app.run()


if __name__ == "__main__":
    main()
