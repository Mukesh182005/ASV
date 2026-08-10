"""
EMG Signal Filtering Utilities
Implements various filtering techniques for EMG signal preprocessing
Compatible with biomedical signal processing standards
"""

import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt, medfilt, savgol_filter
import logging

# Configure logging
logger = logging.getLogger(__name__)


def bandpass_filter(data, lowcut, highcut, fs, order=4):
    """
    Apply Butterworth bandpass filter to EMG signal.
    """
    try:
        nyquist_freq = fs / 2
        
        # Validate and adjust cutoff frequencies safely
        if lowcut >= highcut:
            raise ValueError(f"lowcut ({lowcut}) must be less than highcut ({highcut})")
            
        if highcut >= nyquist_freq:
            logger.warning(f"highcut ({highcut}) >= Nyquist frequency ({nyquist_freq}). Adjusting to {nyquist_freq - 1}")
            highcut = nyquist_freq - 1
            
        if lowcut <= 0:
            lowcut = 1
            
        # Normalize frequencies to Nyquist frequency
        low = lowcut / nyquist_freq
        high = highcut / nyquist_freq
        
        b, a = butter(order, [low, high], btype='band')
        
        # Ensure data is contiguous and correct shape for filtfilt
        # Using axis=0 if it's a 2D array
        filtered_data = filtfilt(b, a, data, axis=0)
        
        return filtered_data
        
    except Exception as e:
        logger.error(f"Error applying bandpass filter: {str(e)}")
        raise


def notch_filter(data, notch_freq, fs, Q=30):
    """
    Apply notch filter to remove powerline interference.
    """
    try:
        nyquist_freq = fs / 2
        
        if notch_freq >= nyquist_freq:
            logger.warning(f"Notch frequency ({notch_freq} Hz) >= Nyquist frequency ({nyquist_freq} Hz). Skipping notch.")
            return data
            
        w0 = notch_freq / nyquist_freq
        b, a = signal.iirnotch(w0, Q)
        
        filtered_data = filtfilt(b, a, data, axis=0)
        return filtered_data
        
    except Exception as e:
        logger.error(f"Error applying notch filter: {str(e)}")
        raise


def apply_standard_emg_filter(data, fs, notch_freq=50, lowcut=10, highcut=400):
    """
    Apply standard EMG preprocessing filter chain safely derived from sampling rate.
    """
    try:
        # 1. Remove DC offset
        data = data - np.mean(data, axis=0)
        
        # 2. Notch filter
        step1 = notch_filter(data, notch_freq, fs)
        
        # 3. Bandpass filter
        step2 = bandpass_filter(step1, lowcut=lowcut, highcut=highcut, fs=fs, order=4)
        
        return step2
        
    except Exception as e:
        logger.error(f"Error in standard EMG filter chain: {str(e)}")
        raise
