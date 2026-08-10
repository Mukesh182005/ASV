import pandas as pd
import matplotlib.pyplot as plt

# Load dataset
df = pd.read_csv("datasets/emg_dataset.csv")

# Select first sample
sample = df.iloc[0]

# Extract channel values
ch1 = sample[[f"ch1_{i}" for i in range(200)]].values
ch2 = sample[[f"ch2_{i}" for i in range(200)]].values

# Plot signals
plt.figure(figsize=(12,5))

plt.plot(ch1, label="Jaw Muscle Signal")
plt.plot(ch2, label="Suprahyoid Signal")

plt.title(f"EMG Signals for Word: {sample['label']}")
plt.xlabel("Time")
plt.ylabel("Amplitude")

plt.legend()

plt.grid(True)

plt.show()
