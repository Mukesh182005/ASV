import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "datasets" / "custom_silent_speech"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"
SPLITS_DIR = DATA_DIR / "splits"
MODELS_DIR = BASE_DIR / "ml" / "models"
VOCABULARY_FILE = Path(__file__).resolve().parent / "vocabulary.txt"

# Ensure directories exist
for directory in [RAW_DATA_DIR, PROCESSED_DATA_DIR, METADATA_DIR, SPLITS_DIR, MODELS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Hardware & Acquisition Settings
# ---------------------------------------------------------------------------
# These MUST match firmware_arduino/ASV_Firmware/asv_config.h.
# The firmware prints its own values in the "# ASV_STREAM v2 ..." header line
# at the start of every stream - if the two disagree, trust the firmware and
# fix this file, because a train/inference sampling-rate mismatch silently
# destroys model accuracy.
# ---------------------------------------------------------------------------
SAMPLING_RATE_HZ = 860        # ADS1115 continuous max, hardware-paced via ALRT/RDY
SAMPLING_RATE_HZ_FALLBACK = 500  # firmware's software-paced mode (no ALRT wire)
NUM_CHANNELS = 1              # AD8232 OUTPUT -> ADS1115 A0
SERIAL_BAUD_RATE = 921600
TIMESTAMP_UNIT = "us"         # firmware v2 emits microsecond timestamps
ADC_UV_PER_LSB = 125.0        # gain index 1 = +/-4.096 V full scale
STREAM_START_CMD = b"s"       # firmware boots IDLE; this starts the CSV stream
STREAM_STOP_CMD = b"x"

# DSP & Filtering
NOTCH_FREQ_HZ = 50
NOTCH_QUALITY = 30
BANDPASS_LOW_HZ = 10
BANDPASS_HIGH_HZ = min(200, (SAMPLING_RATE_HZ / 2) - 1)

# Segmentation Settings
WINDOW_DURATION_MS = 256
OVERLAP_PERCENT = 0.5
WINDOW_SIZE = int(SAMPLING_RATE_HZ * (WINDOW_DURATION_MS / 1000.0))
STEP_SIZE = int(WINDOW_SIZE * (1.0 - OVERLAP_PERCENT))

# Vocabulary (loaded from file)
def load_vocabulary():
    """Load vocabulary from config file. One label per line, stripped, lowercased."""
    if VOCABULARY_FILE.exists():
        with open(VOCABULARY_FILE, 'r') as f:
            return [line.strip().lower() for line in f if line.strip()]
    return ["hello", "help", "yes", "no"]

VOCABULARY = load_vocabulary()

# Random state for reproducibility
RANDOM_STATE = 42
