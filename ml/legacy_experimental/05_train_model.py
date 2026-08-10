import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report

# Load features
df = pd.read_csv("datasets/emg_features.csv")

# Inputs and labels
X = df[["MAV", "RMS", "ZCR", "VAR", "WL"]]
y = df["label"]

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train model
model = SVC(kernel='rbf')

model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)

# Accuracy
accuracy = accuracy_score(y_test, y_pred)

print(f"\nModel Accuracy: {accuracy * 100:.2f}%\n")

print("Classification Report:\n")
print(classification_report(y_test, y_pred))
