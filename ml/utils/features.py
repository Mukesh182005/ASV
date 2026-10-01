"""
EMG Feature Extraction Utilities
Extracts time-domain and frequency-domain features from EMG signals
"""

import numpy as np
from scipy import fftpack
import logging
from ml.config import settings

logger = logging.getLogger(__name__)

class EMGFeatureExtractor:
    def __init__(self, fs=settings.SAMPLING_RATE_HZ):
        self.fs = fs
    
    def extract_features_vectorized(self, signal_window, include_frequency=False):
        """
        Extract features from a window of multi-channel EMG data.
        signal_window: ndarray of shape (n_samples, n_channels)
        
        Returns:
        Dictionary of features, where keys are feature names and values are 1D arrays
        of length n_channels.
        """
        # Ensure 2D
        if signal_window.ndim == 1:
            signal_window = signal_window.reshape(-1, 1)
            
        n_samples, n_channels = signal_window.shape
        features = {}
        
        # MAV: Mean Absolute Value
        features['MAV'] = np.mean(np.abs(signal_window), axis=0)
        
        # RMS: Root Mean Square
        features['RMS'] = np.sqrt(np.mean(signal_window ** 2, axis=0))
        
        # VAR: Variance
        features['VAR'] = np.var(signal_window, axis=0)
        
        # STD: Standard Deviation
        features['STD'] = np.std(signal_window, axis=0)
        
        # WL: Waveform Length
        features['WL'] = np.sum(np.abs(np.diff(signal_window, axis=0)), axis=0)
        
        # ZCR: Zero Crossing Rate
        # Vectorized ZCR calculation
        signs = np.sign(signal_window)
        # Handle zeros by keeping previous sign (simplified here by considering zeros as positive)
        signs[signs == 0] = 1 
        features['ZCR'] = np.sum(np.abs(np.diff(signs, axis=0)) > 0, axis=0) / (n_samples - 1)
        
        # SSC: Slope Sign Changes
        diffs = np.diff(signal_window, axis=0)
        diff_signs = np.sign(diffs)
        diff_signs[diff_signs == 0] = 1
        features['SSC'] = np.sum(np.abs(np.diff(diff_signs, axis=0)) > 0, axis=0) / (n_samples - 2)

        # Frequency features
        # Only meaningful if we have enough samples
        if include_frequency and n_samples >= 32:
            try:
                # Use real FFT
                fft_vals = np.abs(np.fft.rfft(signal_window, axis=0))
                freqs = np.fft.rfftfreq(n_samples, d=1.0/self.fs)
                
                # Mean Frequency (MF)
                # Weighted average of frequencies
                total_power = np.sum(fft_vals, axis=0)
                # Avoid division by zero
                total_power[total_power == 0] = 1e-10 
                
                # np.average with weights expects 1D arrays for weights if axes aren't properly aligned,
                # manual calculation:
                mf = np.sum(freqs[:, np.newaxis] * fft_vals, axis=0) / total_power
                features['MF'] = mf
                
                # Median Frequency (MEDF)
                cumsum_power = np.cumsum(fft_vals, axis=0)
                medf = np.zeros(n_channels)
                for ch in range(n_channels):
                    half_power = total_power[ch] / 2.0
                    idx = np.where(cumsum_power[:, ch] >= half_power)[0]
                    if len(idx) > 0:
                        medf[ch] = freqs[idx[0]]
                    else:
                        medf[ch] = 0
                features['MEDF'] = medf
                
            except Exception as e:
                logger.error(f"Error computing frequency features: {e}")
                features['MF'] = np.zeros(n_channels)
                features['MEDF'] = np.zeros(n_channels)
                
        return features

    def flatten_features(self, features_dict):
        """
        Flattens the feature dictionary into a 1D array suitable for ML models.
        """
        # Sort keys to ensure consistent order
        flat = []
        feature_names = []
        for key in sorted(features_dict.keys()):
            vals = features_dict[key]
            flat.extend(vals)
            feature_names.extend([f"{key}_ch{i}" for i in range(len(vals))])
        return np.array(flat), feature_names
