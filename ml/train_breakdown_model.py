import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score
# 1. Load the training table from script 2
df = pd.read_csv("breakdown_training_table.csv", parse_dates=["Log_Date"])

# 2. Drop the first weeks with no service record yet (Days_Since_Service is empty)
df = df.dropna(subset=["Days_Since_Service"])

# 3. Choose the inputs and the output
INPUTS = ["Age_Years", "Hours_Last_4W", "Cumulative_Hours", "Days_Since_Service"]
OUTPUT = "Breakdown_Next_30D"

# 4. Split by TIME: oldest 75% of weeks = training, newest 25% = testing
df = df.sort_values("Log_Date")
cutoff = df["Log_Date"].quantile(0.75)
train = df[df["Log_Date"] <= cutoff]
test = df[df["Log_Date"] > cutoff]
print("Cut-off date:", cutoff.date())
print("Train rows:", len(train), " Test rows:", len(test))

# 5. Train the baseline model
model = LogisticRegression(max_iter=3000, class_weight="balanced")
model.fit(train[INPUTS], train[OUTPUT])

# 6. Predict on the test weeks (the model has never seen these)
prob = model.predict_proba(test[INPUTS])[:, 1]     # chance of breakdown, 0 to 1
pred = (prob >= 0.5).astype(int)                   # turn the chance into a yes/no warning

# 7. Measure
print("Share of 1s in test (what guessing gets for PR-AUC):", round(test[OUTPUT].mean(), 3))
print("ROC-AUC :", round(roc_auc_score(test[OUTPUT], prob), 3))
print("PR-AUC  :", round(average_precision_score(test[OUTPUT], prob), 3))
print("Precision:", round(precision_score(test[OUTPUT], pred), 3))
print("Recall   :", round(recall_score(test[OUTPUT], pred), 3))


# Train a Random Forest: many decision trees that vote together
rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=20,
                            class_weight="balanced", random_state=0)
rf.fit(train[INPUTS], train[OUTPUT])
rf_prob = rf.predict_proba(test[INPUTS])[:, 1]

print("\nRandom Forest")
print("ROC-AUC :", round(roc_auc_score(test[OUTPUT], rf_prob), 3))
print("PR-AUC  :", round(average_precision_score(test[OUTPUT], rf_prob), 3))

# Which inputs mattered most to the Random Forest
importance = pd.Series(rf.feature_importances_, index=INPUTS).sort_values(ascending=False)
print("\nInput importance:\n", importance.round(3))

# Keep whichever model has the better PR-AUC, and save it to a file for the backend
lr_pr = average_precision_score(test[OUTPUT], prob)
rf_pr = average_precision_score(test[OUTPUT], rf_prob)
best, name = (rf, "Random Forest") if rf_pr > lr_pr else (model, "Logistic Regression")
joblib.dump({"model": best, "inputs": INPUTS}, "breakdown_model.joblib")
print("\nSaved:", name, "-> breakdown_model.joblib")