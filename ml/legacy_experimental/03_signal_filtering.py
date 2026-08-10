import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

# Load dataset
df = pd.read_csv("datasets/emg_dataset.csv")

# Select first sample
sample = df.iloc[0]

# Extract channel
signal = sample[[f"ch1_{i}" for i in range(200)]].values.astype(float)

# Sampling frequency
FS = 1000

# Butterworth Bandpass Filter
LOWCUT = 1
HIGHCUT = 50

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def apply_filter(data):
    b, a = butter_bandpass(LOWCUT, HIGHCUT, FS)
    return filtfilt(b, a, data)

filtered_signal = apply_filter(signal)

# Plot comparison
plt.figure(figsize=(12,5))

plt.plot(signal, label="Raw Signal", alpha=0.7)
plt.plot(filtered_signal, label="Filtered Signal", linewidth=2)

plt.title("EMG Signal Filtering")
plt.xlabel("Time")
plt.ylabel("Amplitude")

plt.legend()
plt.grid(True)

plt.show()
