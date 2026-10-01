import pandas as pd
import numpy as np

# Load dataset
df = pd.read_csv("datasets/emg_dataset.csv")

# Feature functions
def mean_absolute_value(signal):
    return np.mean(np.abs(signal))

def root_mean_square(signal):
    return np.sqrt(np.mean(signal**2))

def zero_crossing_rate(signal):
    return np.sum(np.diff(np.sign(signal)) != 0)

def variance(signal):
    return np.var(signal)

def waveform_length(signal):
    return np.sum(np.abs(np.diff(signal)))

feature_rows = []

for index, row in df.iterrows():

    ch1 = row[[f"ch1_{i}" for i in range(200)]].values.astype(float)

    features = {
        "label": row["label"],
        "MAV": mean_absolute_value(ch1),
        "RMS": root_mean_square(ch1),
        "ZCR": zero_crossing_rate(ch1),
        "VAR": variance(ch1),
        "WL": waveform_length(ch1),
    }

    feature_rows.append(features)

feature_df = pd.DataFrame(feature_rows)

feature_df.to_csv("datasets/emg_features.csv", index=False)

print(feature_df.head())
print("\nFeature Extraction Completed!")
