import numpy as np
import pandas as pd
import os

# Vocabulary words
VOCABULARY = {
    "hello": {"mass_peak": 0.8, "supra_peak": 0.6},
    "help": {"mass_peak": 0.5, "supra_peak": 0.9},
    "yes": {"mass_peak": 0.3, "supra_peak": 0.4},
    "no": {"mass_peak": 0.2, "supra_peak": 0.3},
}

FS = 1000
DURATION = 0.2
N_SAMPLES = 100
N_POINTS = int(FS * DURATION)

def generate_emg_signal(peak):
    t = np.linspace(0, DURATION, N_POINTS)

    signal = peak * np.exp(-((t - 0.1) ** 2) / 0.001)

    noise = np.random.normal(0, 0.02, N_POINTS)

    return signal + noise

all_samples = []

for word in VOCABULARY:
    for i in range(N_SAMPLES):

        ch1 = generate_emg_signal(VOCABULARY[word]["mass_peak"])
        ch2 = generate_emg_signal(VOCABULARY[word]["supra_peak"])

        sample = {"label": word}

        for j, val in enumerate(ch1):
            sample[f"ch1_{j}"] = val

        for j, val in enumerate(ch2):
            sample[f"ch2_{j}"] = val

        all_samples.append(sample)

df = pd.DataFrame(all_samples)

os.makedirs("datasets", exist_ok=True)

df.to_csv("datasets/emg_dataset.csv", index=False)

print("Dataset Generated Successfully!")
print(df.head())
