"""Temporary Proof-of-Concept LIVE "HELLO vs REST" Detector with GUI.

Reads COM5 EMG stream at 500000 baud (or simulated stream) and performs
real-time filtering, windowing, feature extraction, and classification.
Displays a clean Tkinter GUI with the prediction.

Usage:
    python ml/inference/live_hello_demo.py --port COM5 --baud 500000
    python ml/inference/live_hello_demo.py --simulate
"""
import os
import sys
import time
import argparse
import logging
import threading
import tkinter as tk
import numpy as np
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ml.config import settings
from ml.acquisition.serial_reader import EMGSerialReader
from ml.utils.filters import apply_standard_emg_filter
from ml.utils.features import EMGFeatureExtractor
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEMO_MODEL_DIR = settings.MODELS_DIR / "demo_hello_rest"


class LiveHelloDetector:
    """Real-time proof-of-concept detector for COM5 EMG stream with GUI."""

    def __init__(self, port="COM5", baud_rate=500000, model_dir=None, simulate=False, duration=None):
        self.port = port
        self.baud_rate = baud_rate
        self.simulate = simulate
        self.model_dir = Path(model_dir) if model_dir else DEMO_MODEL_DIR
        self.duration = duration
        
        self.reader = EMGSerialReader(port=self.port, baud_rate=self.baud_rate, num_channels=settings.NUM_CHANNELS)
        self.classifier = None
        self.scaler = None
        self.label_encoder = None
        self.feature_extractor = EMGFeatureExtractor(fs=settings.SAMPLING_RATE_HZ)
        self.has_model = False
        
        self.filter_buffer_size = 2000
        self.sample_buffer = deque(maxlen=self.filter_buffer_size)
        self._load_model()

        # State for GUI
        self.current_prediction = "WAITING"
        self.current_signal_status = "WAITING"
        self.current_confidence = "0%"
        self.is_running = True
        
        # Debounce: hold HELLO on display for a short period after detection
        self.hello_hold_frames = 0

        self.root = None

    def _load_model(self):
        """Load SVM classifier, standalone scaler, and label encoder."""
        clf_path = self.model_dir / "classifier.pkl"
        le_path = self.model_dir / "label_encoder.pkl"
        scaler_path = self.model_dir / "scaler.pkl"

        if all(p.exists() for p in (clf_path, le_path, scaler_path)):
            try:
                self.classifier = joblib.load(clf_path)
                self.label_encoder = joblib.load(le_path)
                self.scaler = joblib.load(scaler_path)
                self.has_model = True
                logger.info(f"Loaded SVM demo model from {self.model_dir}")
            except Exception as e:
                logger.warning(f"Could not load demo model: {e}")
                self.has_model = False
        else:
            logger.warning(f"No trained SVM model found at {self.model_dir}. Run scratch/retrain_svm.py first.")

    def run(self):
        """Start GUI and the background inference thread."""
        if not self.simulate:
            logger.info(f"Connecting to hardware on {self.port} at {self.baud_rate} baud...")
            if not self.reader.connect():
                logger.error(f"Cannot connect to serial port {self.port}. Ensure ESP32 is plugged in.")
                logger.info("Tip: Pass --simulate to test live demo logic without physical hardware.")
                return
        else:
            logger.info("Running in SIMULATED mode for testing...")

        # Start inference thread
        self.thread = threading.Thread(target=self._inference_loop, daemon=True)
        self.thread.start()

        # Start GUI
        self._create_gui()

    def _inference_loop(self):
        start_time = time.time()
        last_pred_time = 0
        pred_interval = (settings.STEP_SIZE / settings.SAMPLING_RATE_HZ)

        try:
            while self.is_running:
                if self.duration and (time.time() - start_time) > self.duration:
                    # Time to exit
                    self.is_running = False
                    if self.root:
                        self.root.quit()
                    break

                read_duration = settings.STEP_SIZE / settings.SAMPLING_RATE_HZ
                result = self.reader.read_samples(read_duration, simulate=self.simulate)
                channels = result["channels"]

                if len(channels) == 0:
                    time.sleep(0.01)
                    continue

                for val in channels[:, 0]:
                    self.sample_buffer.append(val)

                if len(self.sample_buffer) >= settings.WINDOW_SIZE:
                    now = time.time()
                    if now - last_pred_time >= pred_interval:
                        last_pred_time = now
                        self._process_window()

        except Exception as e:
            logger.error(f"Inference thread error: {e}")
        finally:
            if not self.simulate:
                self.reader.disconnect()

    def _process_window(self):
        """Extract features from current buffer, classify with SVM, send to OLED."""
        if not self.has_model:
            self.current_prediction = "NO MODEL"
            self.current_confidence = "Run retrain_svm.py"
            return

        raw_window = np.array(self.sample_buffer).reshape(-1, 1)
        
        # Filter the full buffer to avoid IIR edge artifacts
        filtered = apply_standard_emg_filter(
            raw_window,
            fs=settings.SAMPLING_RATE_HZ,
            notch_freq=settings.NOTCH_FREQ_HZ,
            lowcut=settings.BANDPASS_LOW_HZ,
            highcut=settings.BANDPASS_HIGH_HZ
        )

        # Extract features from the last WINDOW_SIZE samples (cleanly filtered)
        actual_window = filtered[-settings.WINDOW_SIZE:]
        rms = float(np.sqrt(np.mean(actual_window**2)))

        feat_dict = self.feature_extractor.extract_features_vectorized(
            actual_window, include_frequency=True
        )
        flat, _ = self.feature_extractor.flatten_features(feat_dict)
        flat_scaled = self.scaler.transform([flat])[0]

        pred_idx = self.classifier.predict([flat_scaled])[0]
        pred_label = self.label_encoder.inverse_transform([pred_idx])[0].upper()
        
        # Get confidence probability
        try:
            prob = float(np.max(self.classifier.predict_proba([flat_scaled])))
        except AttributeError:
            prob = 1.0

        # Debounce: hold HELLO for ~0.5s after detection to prevent flickering
        if pred_label == "HELLO":
            self.hello_hold_frames = 5

        if self.hello_hold_frames > 0:
            self.current_prediction = "HELLO"
            self.current_signal_status = "ACTIVE"
            self.current_confidence = f"{prob*100:.0f}%"
            self.hello_hold_frames -= 1
            if not self.simulate and self.reader.serial_conn and self.reader.serial_conn.is_open:
                try: self.reader.serial_conn.write(b"H\n")
                except: pass
        else:
            self.current_prediction = "REST"
            self.current_signal_status = "REST"
            self.current_confidence = f"{prob*100:.0f}%"
            if not self.simulate and self.reader.serial_conn and self.reader.serial_conn.is_open:
                try: self.reader.serial_conn.write(b"R\n")
                except: pass

        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] RMS: {rms:6.1f} | SVM: {pred_label} ({prob*100:.0f}%) | Display: {self.current_prediction}", flush=True)

    def _create_gui(self):
        """Create and run the Tkinter GUI."""
        self.root = tk.Tk()
        self.root.title("ASV \u2014 SILENT SPEECH DEMO")
        self.root.geometry("400x350")
        self.root.configure(bg="#1e1e1e")

        # Fonts
        font_title = ("Helvetica", 16, "bold")
        font_label = ("Helvetica", 12)
        font_value = ("Helvetica", 24, "bold")

        tk.Label(self.root, text="ASV \u2014 SILENT SPEECH DEMO", font=font_title, fg="white", bg="#1e1e1e").pack(pady=20)

        # Frame for Prediction
        pred_frame = tk.Frame(self.root, bg="#1e1e1e")
        pred_frame.pack(pady=10)
        tk.Label(pred_frame, text="Current Prediction:", font=font_label, fg="#aaaaaa", bg="#1e1e1e").pack()
        self.lbl_pred = tk.Label(pred_frame, text="WAITING", font=("Helvetica", 32, "bold"), fg="#00ff00", bg="#1e1e1e")
        self.lbl_pred.pack()

        # Frame for Signal Status
        sig_frame = tk.Frame(self.root, bg="#1e1e1e")
        sig_frame.pack(pady=10)
        tk.Label(sig_frame, text="Signal Status:", font=font_label, fg="#aaaaaa", bg="#1e1e1e").pack()
        self.lbl_sig = tk.Label(sig_frame, text="WAITING", font=font_value, fg="white", bg="#1e1e1e")
        self.lbl_sig.pack()

        # Frame for Confidence
        conf_frame = tk.Frame(self.root, bg="#1e1e1e")
        conf_frame.pack(pady=10)
        tk.Label(conf_frame, text="Confidence:", font=font_label, fg="#aaaaaa", bg="#1e1e1e").pack()
        self.lbl_conf = tk.Label(conf_frame, text="0%", font=font_value, fg="white", bg="#1e1e1e")
        self.lbl_conf.pack()

        self._update_gui()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        if self.duration:
            # If duration is set (e.g. tests), close automatically
            self.root.after(int(self.duration * 1000), self._on_close)

        self.root.mainloop()

    def _update_gui(self):
        if not self.is_running:
            return
            
        # Update colors based on prediction
        if self.current_prediction == "HELLO":
            self.lbl_pred.config(text=self.current_prediction, fg="#00ff00")
            self.lbl_sig.config(text=self.current_signal_status, fg="#00ff00")
        else:
            self.lbl_pred.config(text=self.current_prediction, fg="#aaaaaa")
            self.lbl_sig.config(text=self.current_signal_status, fg="#aaaaaa")
            
        self.lbl_conf.config(text=self.current_confidence)
        
        self.root.after(100, self._update_gui)

    def _on_close(self):
        self.is_running = False
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Live HELLO vs REST Detector")
    parser.add_argument("--port", default="COM5", help="Serial port (default: COM5)")
    parser.add_argument("--baud", type=int, default=500000, help="Baud rate (default: 500000)")
    parser.add_argument("--model-dir", default=None, help="Directory containing demo model")
    parser.add_argument("--simulate", action="store_true", help="Simulate live EMG stream")
    parser.add_argument("--duration", type=float, default=None, help="Max run duration in seconds")
    args = parser.parse_args()

    detector = LiveHelloDetector(
        port=args.port,
        baud_rate=args.baud,
        model_dir=args.model_dir,
        simulate=args.simulate,
        duration=args.duration
    )
    detector.run()


if __name__ == "__main__":
    main()
