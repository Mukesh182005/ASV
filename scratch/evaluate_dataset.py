import glob
import pandas as pd
import numpy as np
from pathlib import Path
import sys, warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from ml.refined.utterance_features import extract, FS_DEFAULT, FEATURE_NAMES
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import LeaveOneOut, cross_val_predict, cross_val_score, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Load recordings
files = sorted(glob.glob('datasets/custom_silent_speech/raw/**/*.csv', recursive=True))
print(f"Total recordings: {len(files)}")

X, y = [], []
for f in files:
    label = Path(f).parent.name
    df = pd.read_csv(f)
    ch_col = [c for c in df.columns if 'channel' in c or 'ch' in c][0]
    counts = df[ch_col].values
    X.append(extract(counts, fs=FS_DEFAULT))
    y.append(label)

X = np.array(X)
y = np.array(y)

le = LabelEncoder()
yi = le.fit_transform(y)
classes = le.classes_

print(f"Classes: {classes}")
print(f"Feature matrix shape: {X.shape}")

models = {
    "SVM_rbf": make_pipeline(StandardScaler(), SVC(kernel="rbf", C=10, gamma="scale", probability=True)),
    "SVM_linear": make_pipeline(StandardScaler(), SVC(kernel="linear", C=1.0, probability=True)),
    "RandomForest": RandomForestClassifier(n_estimators=300, random_state=42),
    "KNN": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=3)),
    "GradientBoosting": GradientBoostingClassifier(n_estimators=100, random_state=42),
}

for name, clf in models.items():
    loo_pred = cross_val_predict(clf, X, yi, cv=LeaveOneOut())
    loo_acc = accuracy_score(yi, loo_pred)
    print(f"\nModel: {name:18s} | LOO Out-Of-Fold Accuracy: {loo_acc:.1%}")
    
    if name == "SVM_rbf":
        cm = confusion_matrix(yi, loo_pred)
        print("Confusion Matrix (LOO):")
        print(f"Labels: {classes.tolist()}")
        print(cm)
        print("\nClassification Report:")
        print(classification_report(yi, loo_pred, target_names=classes, zero_division=0))
