import pandas as pd
pd.set_option("display.max_columns", None)

folder = "ems_synthetic_data_strong"

# 1. Read the two tables we need for this piece
util = pd.read_csv(f"{folder}/UTILIZATION_LOG.csv")
equipment = pd.read_csv(f"{folder}/EQUIPMENT.csv")

# 2. Turn the date text "2025-09-03" into a real date, so we can do date maths later
util["Log_Date"] = pd.to_datetime(util["Log_Date"])

# 3. Join: add each machine's Manufacturing_Year to every weekly row (like a SQL JOIN on Equipment_ID)
weekly = util.merge(equipment[["Equipment_ID", "Manufacturing_Year"]], on="Equipment_ID")

# 4. Input 1: machine age in that week, in years
weekly["Age_Years"] = weekly["Log_Date"].dt.year - weekly["Manufacturing_Year"]

# 5. Sort by machine, then by date, so each machine's weeks are in order
weekly = weekly.sort_values(["Equipment_ID", "Log_Date"])
# Read the service history and make the date a real date
maintenance = pd.read_csv(f"{folder}/MAINTENANCE.csv")
maintenance["Service_Date"] = pd.to_datetime(maintenance["Service_Date"])

# Input 2: total hours in the last 4 weeks (this week + 3 before), counted per machine
weekly["Hours_Last_4W"] = (
    weekly.groupby("Equipment_ID")["Operating_Hours"]
          .transform(lambda h: h.rolling(4, min_periods=1).sum())
)

# Input 3: total hours the machine has worked so far (running total, per machine)
weekly["Cumulative_Hours"] = weekly.groupby("Equipment_ID")["Operating_Hours"].cumsum()

# Input 4: days since the last service ON OR BEFORE this week
weekly = weekly.sort_values("Log_Date")                     # merge_asof needs rows sorted by date
maintenance = maintenance.sort_values("Service_Date")
weekly = pd.merge_asof(
    weekly,
    maintenance[["Equipment_ID", "Service_Date"]],
    left_on="Log_Date", right_on="Service_Date",
    by="Equipment_ID",          # match only the same machine
    direction="backward",       # only services in the PAST (no peeking at the future)
)
weekly["Days_Since_Service"] = (weekly["Log_Date"] - weekly["Service_Date"]).dt.days

weekly = weekly.sort_values(["Equipment_ID", "Log_Date"]).reset_index(drop=True)

# Read breakdowns and make the date a real date
breakdowns = pd.read_csv(f"{folder}/BREAKDOWN.csv")
breakdowns["Breakdown_Date"] = pd.to_datetime(breakdowns["Breakdown_Date"])

# For each machine, a list of its breakdown dates, e.g. {"EQ-002": [2025-05-27, 2025-11-05, ...]}
breakdown_dates = breakdowns.groupby("Equipment_ID")["Breakdown_Date"].apply(list).to_dict()

# Output: 1 if this machine broke down AFTER this week's date and within the next 30 days, else 0
def broke_down_next_30_days(row):
    for d in breakdown_dates.get(row["Equipment_ID"], []):     # [] if the machine never broke down
        days_ahead = (d - row["Log_Date"]).days
        if 0 < days_ahead <= 30:
            return 1
    return 0

weekly["Breakdown_Next_30D"] = weekly.apply(broke_down_next_30_days, axis=1)

# The last 30 days of data can't be labelled fairly (we can't see their full future), so drop them
last_date = weekly["Log_Date"].max()
weekly = weekly[weekly["Log_Date"] <= last_date - pd.Timedelta(days=30)]

# Save the training table so the next script can use it
weekly.to_csv("breakdown_training_table.csv", index=False)

print(weekly["Breakdown_Next_30D"].value_counts())
print("Share of 1s:", round(weekly["Breakdown_Next_30D"].mean() * 100, 1), "%")
print(weekly.head(10))
print("Rows:", len(weekly))