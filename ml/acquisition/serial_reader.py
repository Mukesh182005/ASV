"""Serial EMG reader for ESP32 + ADS1115 acquisition."""
import serial
import serial.tools.list_ports
import time
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EMGSerialReader:
    """Reads structured CSV EMG packets from ESP32 over serial."""

    # First characters that mark a firmware log/banner/metadata line rather
    # than a data row. Kept as a class attribute so tests and tools can see it.
    LOG_PREFIX_CHARS = "[#-=═>*!+"

    # Firmware v2 emits microsecond timestamps. Older builds emitted
    # milliseconds; `timestamp_unit="auto"` figures it out from the header line
    # or, failing that, from the observed sample spacing.
    def __init__(self, port, baud_rate=921600, num_channels=1,
                 timestamp_unit="auto"):
        self.port = port
        self.baud_rate = baud_rate
        self.num_channels = num_channels
        self.timestamp_unit = timestamp_unit
        self.firmware_header = {}
        self.serial_conn = None
        self.stats = {"total_lines": 0, "valid_packets": 0, "malformed": 0}

    def connect(self, start_stream=True):
        """Open serial connection and put the firmware into streaming mode.

        ASV firmware v2 boots into an interactive IDLE state and only emits CSV
        after receiving 's'. Without this handshake you get zero samples.
        """
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baud_rate, timeout=1
            )
            time.sleep(2)  # ESP32 resets when the port is opened
            self.serial_conn.reset_input_buffer()
            logger.info(f"Connected to {self.port} at {self.baud_rate} baud")
            if start_stream:
                self.start_stream()
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {self.port}: {e}")
            return False

    def start_stream(self, timeout_sec=5.0):
        """Send 's' and wait for the firmware's stream header.

        Also captures the '# ASV_STREAM v2 ...' metadata so the host always
        knows the real sampling rate and timestamp unit of the device it is
        talking to, instead of assuming.
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("Serial connection not open")

        self.serial_conn.reset_input_buffer()
        self.serial_conn.write(b"x")   # make sure we are idle first
        time.sleep(0.2)
        self.serial_conn.reset_input_buffer()
        self.serial_conn.write(b"s")

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            raw = self.serial_conn.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("# ASV_STREAM"):
                for token in line.replace("# ASV_STREAM", "").split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        self.firmware_header[k] = v
                if self.timestamp_unit == "auto":
                    self.timestamp_unit = self.firmware_header.get("ts_unit", "us")
                logger.info(f"Firmware stream header: {self.firmware_header}")
            if line.startswith("--- START DATA ---"):
                logger.info("Stream started")
                return True

        logger.warning(
            "No '--- START DATA ---' from firmware. Either it is an older build "
            "that streams automatically, or the board is not responding."
        )
        if self.timestamp_unit == "auto":
            self.timestamp_unit = "us"
        return False

    def stop_stream(self):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(b"x")
            except serial.SerialException:
                pass

    @property
    def timestamp_divisor_to_ms(self):
        """Divide a raw timestamp by this to get milliseconds."""
        return 1000.0 if self.timestamp_unit == "us" else 1.0

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_stream()
            time.sleep(0.1)
            self.serial_conn.close()
            logger.info("Serial disconnected")

    @staticmethod
    def list_ports():
        """Return list of available serial port device names."""
        return [p.device for p in serial.tools.list_ports.comports()]

    def parse_line(self, raw_line):
        """Parse a single CSV line from ESP32.
        Supports both new format (timestamp_ms,ch0,...) and legacy format (ch0).
        Returns (timestamp_ms, [channel_values]) or None on failure.
        """
        self.stats["total_lines"] += 1
        try:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                return None

            # Firmware log/banner/metadata lines all start with punctuation:
            #   [BOOT]..  # ASV_STREAM..  --- START DATA ---  ====  >>> ..
            # Anything else is expected to be a data row. If it fails to parse
            # it is counted as malformed rather than silently dropped, so serial
            # corruption during collection is visible instead of invisible.
            # (A data row always begins with a digit - the timestamp is unsigned.)
            if line[0] in self.LOG_PREFIX_CHARS:
                return None

            parts = line.split(",")

            # Legacy format: Just a single ADC value (e.g., "14567")
            if len(parts) == 1:
                # Fallback timestamp using PC time, in the reader's own unit
                scale = 1e6 if self.timestamp_unit == "us" else 1e3
                timestamp = int(time.time() * scale)
                channels = [float(parts[0])]
                
                if self.num_channels > 1:
                    # Pad with zeros if we're expecting more channels
                    channels.extend([0.0] * (self.num_channels - 1))
                    
                self.stats["valid_packets"] += 1
                return timestamp, channels
                
            # New format: timestamp_ms,ch0[,ch1...]
            timestamp = int(parts[0])
            channels = []
            for i in range(1, min(len(parts), self.num_channels + 1)):
                channels.append(float(parts[i]))
            if len(channels) < self.num_channels:
                self.stats["malformed"] += 1
                return None
            self.stats["valid_packets"] += 1
            return timestamp, channels
        except (ValueError, UnicodeDecodeError):
            self.stats["malformed"] += 1
            return None

    def read_samples(self, duration_sec, simulate=False):
        """Read EMG samples for a specified duration.
        Returns dict with 'timestamps' and 'channels' numpy arrays.
        """
        if simulate:
            return self._simulate_samples(duration_sec)

        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("Serial connection not open")

        self.stats = {"total_lines": 0, "valid_packets": 0, "malformed": 0}
        timestamps = []
        channel_data = [[] for _ in range(self.num_channels)]

        self.serial_conn.reset_input_buffer()
        end_time = time.time() + duration_sec

        while time.time() < end_time:
            try:
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                result = self.parse_line(raw)
                if result is None:
                    continue
                ts, channels = result
                timestamps.append(ts)
                for i, val in enumerate(channels):
                    channel_data[i].append(val)
            except serial.SerialException as e:
                logger.warning(f"Serial error during read: {e}")
                break

        return {
            "timestamps": np.array(timestamps, dtype=np.int64),
            "channels": np.array(channel_data, dtype=np.float64).T,  # (n_samples, n_channels)
            "stats": dict(self.stats),
            "timestamp_unit": self.timestamp_unit,
            "firmware_header": dict(self.firmware_header),
        }

    def _simulate_samples(self, duration_sec):
        """Generate clearly-marked simulated test data. NOT for production training."""
        from ml.config import settings
        logger.warning("SIMULATED_TEST_DATA — not for production use")
        n = int(duration_sec * settings.SAMPLING_RATE_HZ)
        t = np.linspace(0, duration_sec, n)
        scale = 1e6 if self.timestamp_unit != "ms" else 1e3
        timestamps = (t * scale).astype(np.int64)
        channels = np.zeros((n, self.num_channels))
        for ch in range(self.num_channels):
            channels[:, ch] = (
                np.sin(2 * np.pi * 20 * t) * 500
                + np.random.normal(0, 50, n)
            )
        return {
            "timestamps": timestamps,
            "channels": channels,
            "stats": {"total_lines": n, "valid_packets": n, "malformed": 0},
            "timestamp_unit": "us" if scale == 1e6 else "ms",
            "firmware_header": {},
            "is_simulated": True,
        }
