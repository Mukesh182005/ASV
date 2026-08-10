import pandas as pd

# Load dataset
df = pd.read_csv("datasets/ninapro_db1/Ninapro_DB1.csv")

# Display basic info
print("\n===== DATASET PREVIEW =====\n")
print(df.head())

print("\n===== DATASET SHAPE =====\n")
print(df.shape)

print("\n===== COLUMN NAMES =====\n")
print(df.columns)

print("\n===== MISSING VALUES =====\n")
print(df.isnull().sum())
