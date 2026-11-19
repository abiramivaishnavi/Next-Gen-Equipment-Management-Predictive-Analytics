import pandas as pd
pd.set_option("display.max_columns", None)

folder = "ems_synthetic_data_strong"

# ---------- Piece 1: weekly totals per project ----------
fuel = pd.read_csv(f"{folder}/FUEL_LOG.csv", parse_dates=["Fuel_Date"])
util = pd.read_csv(f"{folder}/UTILIZATION_LOG.csv", parse_dates=["Log_Date"])
equipment = pd.read_csv(f"{folder}/EQUIPMENT.csv")

# Litres model: only liquid fuels (Diesel, Petrol). Electric (kWh) is forecast separately later.
liquid_ids = equipment[equipment["Fuel_Type"].isin(["Diesel", "Petrol"])]["Equipment_ID"]
fuel = fuel[fuel["Equipment_ID"].isin(liquid_ids)]
util = util[util["Equipment_ID"].isin(liquid_ids)]

# Every date -> the Monday of its week, so all entries of one week fall together
fuel["Week"] = fuel["Fuel_Date"].dt.to_period("W-SUN").dt.start_time
util["Week"] = util["Log_Date"].dt.to_period("W-SUN").dt.start_time

weekly_fuel = fuel.groupby(["Project_ID", "Week"])["Fuel_Consumed"].sum().rename("Fuel_L")
weekly_hours = util.groupby(["Project_ID", "Week"])["Operating_Hours"].sum().rename("Hours")
weekly_machines = util.groupby(["Project_ID", "Week"])["Equipment_ID"].nunique().rename("Machines")

weekly = pd.concat([weekly_fuel, weekly_hours, weekly_machines], axis=1).reset_index()

# Weeks with no entries for a project = 0 (no machines there), so every project has every week
all_weeks = pd.date_range(weekly["Week"].min(), weekly["Week"].max(), freq="W-MON")
full = pd.MultiIndex.from_product([weekly["Project_ID"].unique(), all_weeks], names=["Project_ID", "Week"])
weekly = weekly.set_index(["Project_ID", "Week"]).reindex(full, fill_value=0).reset_index()

# ---------- Piece 2: inputs and output ----------
activities = pd.read_csv(f"{folder}/PROJECT_ACTIVITY.csv", parse_dates=["Start_Date", "End_Date"])
SCORE = {"Low": 1, "Medium": 2, "High": 3}
activities["Score"] = activities["Expected_Intensity"].map(SCORE)

# Planned work in a week = sum of the scores of the project's activities running during that week
def planned_intensity(row):
    week_end = row["Week"] + pd.Timedelta(days=6)
    running = activities[
        (activities["Project_ID"] == row["Project_ID"])
        & (activities["Start_Date"] <= week_end)
        & (activities["End_Date"] >= row["Week"])
    ]
    return running["Score"].sum()

weekly["Intensity"] = weekly.apply(planned_intensity, axis=1)

weekly = weekly.sort_values(["Project_ID", "Week"])
by_project = weekly.groupby("Project_ID")

# Inputs: what we know at the END of this week
weekly["Fuel_Prev_Week"] = by_project["Fuel_L"].shift(1)                       # the week before
weekly["Fuel_Avg_4W"] = by_project["Fuel_L"].transform(lambda s: s.rolling(4).mean())
weekly["Intensity_Next_Week"] = by_project["Intensity"].shift(-1)             # PLANNED work, known in advance
weekly["Week_Of_Year"] = (weekly["Week"] + pd.Timedelta(days=7)).dt.isocalendar().week.astype(int)

# Output: next week's actual litres
weekly["Fuel_Next_Week"] = by_project["Fuel_L"].shift(-1)

# Drop rows without a full history or without a next week
weekly = weekly.dropna(subset=["Fuel_Prev_Week", "Fuel_Avg_4W", "Fuel_Next_Week"])

weekly.to_csv("fuel_training_table.csv", index=False)
print(weekly.head(6))
print("Rows:", len(weekly))