import numpy as np
import pandas as pd
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# 1. Load the table from build_fuel_table.py
df = pd.read_csv("fuel_training_table.csv", parse_dates=["Week"])

INPUTS = ["Fuel_L", "Fuel_Prev_Week", "Fuel_Avg_4W", "Hours", "Machines",
          "Intensity_Next_Week", "Week_Of_Year"]
OUTPUT = "Fuel_Next_Week"

# 2. Split by TIME: oldest 75% of weeks = training, newest 25% = testing
cutoff = df["Week"].quantile(0.75)
train = df[df["Week"] <= cutoff]
test = df[df["Week"] > cutoff]
print("Cut-off week:", cutoff.date(), "| Train rows:", len(train), "| Test rows:", len(test))

# 3. One function to measure any prediction the same way
def report(name, actual, predicted):
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    nonzero = actual > 0                                   # MAPE can't divide by zero
    mape = (abs(actual[nonzero] - predicted[nonzero]) / actual[nonzero]).mean() * 100
    print(f"{name:<20} MAE {mae:8.0f} L | RMSE {rmse:8.0f} L | MAPE {mape:5.1f} %")
    return mae

# 4. Baseline: "next week = this week"
base_mae = report("Baseline", test[OUTPUT], test["Fuel_L"])

# 5. Ridge regression (with scaling, because inputs have very different sizes)
ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
ridge.fit(train[INPUTS], train[OUTPUT])
ridge_mae = report("Ridge", test[OUTPUT], ridge.predict(test[INPUTS]))

# 6. Random Forest
rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=5, random_state=0)
rf.fit(train[INPUTS], train[OUTPUT])
rf_mae = report("Random Forest", test[OUTPUT], rf.predict(test[INPUTS]))

# 7. Which inputs the forest relied on
importance = pd.Series(rf.feature_importances_, index=INPUTS).sort_values(ascending=False)
print("\nInput importance:\n", importance.round(3))

# 8. Save the model with the lowest MAE (only if it beats the baseline)
best_name, best_model, best_mae = min(
    [("Ridge", ridge, ridge_mae), ("Random Forest", rf, rf_mae)], key=lambda x: x[2]
)
if best_mae < base_mae:
    joblib.dump({"model": best_model, "inputs": INPUTS}, "fuel_model.joblib")
    print(f"\nSaved: {best_name} -> fuel_model.joblib")
else:
    print("\nNo model beat the baseline - nothing saved.")