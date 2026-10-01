"""
backend/live_bridge.py
======================
Hardware serial bridge for ASV — directly replicates the logic and behavior
of tools/predict_live_gui.py for the web application.

Communicates with ESP32 over serial (default COM8, 921600 baud), verifies
electrode baseline and peak-to-peak health, captures utterance windows,
extracts features, performs ML classification, and transmits the recognised
word back to the hardware OLED display.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import serial.tools.list_ports

from ml.acquisition.serial_reader import EMGSerialReader
from ml.config import settings
from ml.refined.utterance_features import FS_DEFAULT, extract, signal_health, load_counts_csv

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "refined_model"
RAW_DIR = settings.RAW_DATA_DIR


def auto_select_port() -> Optional[str]:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    silabs = [p.device for p in ports if "Silicon Labs" in (p.description or "")]
    return silabs[0] if silabs else ports[0].device


class LiveHardwareBridge:
    def __init__(self, default_port: str = "COM8", baud: int = 921600):
        self.default_port = default_port
        self.baud = baud
        self.port: Optional[str] = default_port
        self.reader: Optional[EMGSerialReader] = None
        self.connected: bool = False
        self.last_health: Optional[Dict[str, Any]] = None
        self.busy: bool = False
        self.lock = threading.Lock()

        self.classifier = None
        self.label_encoder = None
        self.model_error: Optional[str] = None
        self.load_model()

        # Connect in background just like tools/predict_live_gui.py
        threading.Thread(target=self._background_initial_connect, daemon=True).start()

    def _background_initial_connect(self) -> None:
        time.sleep(1.0)
        self.connect()

    def load_model(self) -> None:
        clf_path = MODEL_DIR / "classifier.pkl"
        le_path = MODEL_DIR / "label_encoder.pkl"
        if not (clf_path.exists() and le_path.exists()):
            self.model_error = f"No model found in {MODEL_DIR}"
            return
        try:
            self.classifier = joblib.load(clf_path)
            self.label_encoder = joblib.load(le_path)
            self.model_error = None
            logger.info(
                f"[LiveBridge] Loaded model with classes: {list(self.label_encoder.classes_)}"
            )
        except Exception as e:
            self.model_error = f"Failed to load model: {e}"
            logger.error(f"[LiveBridge] {self.model_error}")

    def get_vocabulary(self) -> List[str]:
        if self.label_encoder is not None:
            return [str(c) for c in self.label_encoder.classes_]
        return ["hello", "help", "rest", "water", "yes"]

    def connect(self, port: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            target_port = port or self.port or auto_select_port() or self.default_port
            self.port = target_port

            if self.reader and self.connected:
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
                self.connected = False

            try:
                self.reader = EMGSerialReader(
                    self.port, baud_rate=self.baud, num_channels=1
                )
                if not self.reader.connect():
                    self.connected = False
                    return {
                        "ok": False,
                        "port": self.port,
                        "error": f"Could not connect to {self.port}. Ensure port is not busy.",
                    }

                self.connected = True
                # Check baseline contact once on connect
                try:
                    result = self.reader.read_samples(1.0)
                    samples = (
                        result["channels"][:, 0] if len(result["channels"]) else []
                    )
                    self.last_health = signal_health(samples)
                except Exception:
                    self.last_health = None

                logger.info(
                    f"[LiveBridge] Connected to {self.port}. Baseline health: {self.last_health}"
                )
                return {
                    "ok": True,
                    "port": self.port,
                    "connected": True,
                    "health": self.last_health,
                    "vocabulary": self.get_vocabulary(),
                }
            except Exception as e:
                self.connected = False
                err_str = str(e)
                if "PermissionError" in err_str or "Access is denied" in err_str:
                    err_str = f"Port {self.port} is busy. Close predict_live_gui.py to use the web app on this port."
                return {"ok": False, "port": self.port, "error": err_str}

    def disconnect(self) -> Dict[str, Any]:
        with self.lock:
            if self.reader:
                try:
                    self.reader.disconnect()
                except Exception:
                    pass
            self.reader = None
            self.connected = False
            return {"ok": True, "connected": False}

    def get_status(self) -> Dict[str, Any]:
        port_to_check = self.port or self.default_port

        return {
            "connected": self.connected,
            "port": port_to_check,
            "vocabulary": self.get_vocabulary(),
            "model_loaded": self.classifier is not None,
            "model_error": self.model_error,
            "health": self.last_health,
            "busy": self.busy,
        }

    def _predict_counts(self, counts: np.ndarray) -> Dict[str, Any]:
        # Signal quality gate (detect 50Hz mains hum or disconnect)
        cap_health = signal_health(counts)
        if not cap_health["ok"]:
            msg = f"{cap_health['status']}: pp={cap_health['pp_mv']:.0f}mV (check electrodes/unplug laptop charger)"
            return {
                "ok": False,
                "error": msg,
                "health": cap_health,
                "n_samples": len(counts),
            }

        # Feature extraction
        x = extract(counts, fs=FS_DEFAULT).reshape(1, -1)

        # Prediction
        pred = self.label_encoder.inverse_transform(
            self.classifier.predict(x)
        )[0]
        ranking = []
        conf = 0.0

        if hasattr(self.classifier, "predict_proba"):
            probs = self.classifier.predict_proba(x)[0]
            conf = float(np.max(probs))
            for word, prob in sorted(
                zip(self.label_encoder.classes_, probs),
                key=lambda item: -item[1],
            ):
                ranking.append({"word": str(word), "prob": round(float(prob), 4)})
        else:
            ranking.append({"word": str(pred), "prob": 1.0})
            conf = 1.0

        # Transmit recognised word back to firmware OLED display
        self._send_word_to_board(str(pred))

        self.last_health = cap_health
        return {
            "ok": True,
            "prediction": str(pred),
            "confidence": round(conf, 4),
            "ranking": ranking,
            "health": cap_health,
            "n_samples": len(counts),
            "log": f"[{time.strftime('%H:%M:%S')}] {pred.upper()} ({conf:.1%} conf) — pp={cap_health['pp_mv']:.0f}mV baseline={cap_health['baseline_mv']:.0f}mV",
        }

    def record_and_predict(self, seconds: float = 5.0) -> Dict[str, Any]:
        if not self.classifier or not self.label_encoder:
            self.load_model()
            if not self.classifier:
                return {
                    "ok": False,
                    "error": self.model_error or "Model not loaded",
                }

        with self.lock:
            if self.busy:
                return {"ok": False, "error": "Hardware capture already busy"}

            # Auto-connect if not currently connected
            if not self.connected or not self.reader:
                res = self.connect()
                if not res.get("ok"):
                    return res

            self.busy = True

        try:
            # Drain buffer to eliminate stale readings
            try:
                if self.reader and self.reader.serial_conn:
                    self.reader.serial_conn.reset_input_buffer()
            except Exception:
                pass

            # Capture utterance window
            capture_res = self.reader.read_samples(seconds)
            channels = capture_res["channels"]
            counts = channels[:, 0] if len(channels) else np.array([])

            if len(counts) < 32:
                logger.warning(
                    f"[LiveBridge] Capture too short ({len(counts)} samples). Attempting auto-reconnect..."
                )
                self.disconnect()
                time.sleep(0.4)
                rec = self.connect()
                if rec.get("ok") and self.reader:
                    capture_res = self.reader.read_samples(seconds)
                    channels = capture_res["channels"]
                    counts = channels[:, 0] if len(channels) else np.array([])

            if len(counts) < 32:
                self.disconnect()
                return {
                    "ok": False,
                    "error": f"No data received on {self.port}. Ensure cable is connected and predict_live_gui.py is closed.",
                }

            return self._predict_counts(counts)
        except Exception as e:
            logger.error(f"[LiveBridge] Record error: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}
        finally:
            self.busy = False

    def test_sample(self, word: str = "help") -> Dict[str, Any]:
        """Classify a genuine recording from datasets/custom_silent_speech/raw to test the pipeline."""
        if not self.classifier or not self.label_encoder:
            self.load_model()
            if not self.classifier:
                return {"ok": False, "error": self.model_error or "Model not loaded"}

        word = word.lower()
        search_dirs = [
            RAW_DIR / "S01" / word,
            RAW_DIR / word,
        ]
        target_csv = None
        for d in search_dirs:
            if d.exists():
                csvs = sorted(d.glob("rep*.csv"))
                if csvs:
                    target_csv = csvs[-1]  # Pick newest recording
                    break

        if not target_csv:
            # Fallback to any recording in raw dir
            all_csvs = list(RAW_DIR.rglob(f"*{word}*.csv"))
            if all_csvs:
                target_csv = sorted(all_csvs)[-1]

        if not target_csv or not target_csv.exists():
            return {"ok": False, "error": f"No recording found for '{word}'"}

        try:
            counts = load_counts_csv(target_csv)
            res = self._predict_counts(counts)
            res["source_file"] = target_csv.name
            res["log"] = f"[{time.strftime('%H:%M:%S')}] TEST ({target_csv.name}): {res.get('prediction', '').upper()} ({res.get('confidence', 0):.1%} conf)"
            return res
        except Exception as e:
            return {"ok": False, "error": f"Failed to test sample: {e}"}

    def _send_word_to_board(self, word: str) -> None:
        conn = getattr(self.reader, "serial_conn", None)
        if not conn or not word:
            return
        try:
            conn.write(f"w{word}\n".encode("ascii", errors="ignore"))
            logger.info(f"[LiveBridge] Sent 'w{word}' to firmware OLED")
        except Exception as e:
            logger.warning(
                f"[LiveBridge] Could not send word to firmware: {e}"
            )


# Global singleton instance
live_bridge = LiveHardwareBridge(default_port="COM8", baud=921600)
