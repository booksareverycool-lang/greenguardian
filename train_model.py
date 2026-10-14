import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

BASE_DIR = Path(__file__).resolve().parent

# Credits for dataset: https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset
df = pd.read_csv(BASE_DIR / "Crop_recommendation.csv")

X = df[['temperature', 'humidity', 'rainfall']]
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Save the trained model
joblib.dump(model, BASE_DIR / "crop_model.pkl")
print("Model created: crop_model.pkl")