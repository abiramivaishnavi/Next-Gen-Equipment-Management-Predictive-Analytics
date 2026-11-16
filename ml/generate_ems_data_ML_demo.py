# ML DEMO VERSION (SYNTHETIC data, for the Phase 3 demo only; does not touch the live database).
# Same as the original generator, plus two demo patterns:
#  1) breakdown risk is stronger: older, heavily used, service-overdue machines break down more often;
#  2) planned work intensity (Low/Medium/High) at the project raises operating hours and fuel use.
# Output goes to ems_synthetic_data_strong/.
"""
EMS synthetic data generator — Phase 3 training data.

Generates FK-consistent CSVs for all 12 tables, with breakdown risk
deliberately tied to equipment age, cumulative utilization hours, and
time since last service — so the predictive-maintenance model in
Phase 3 has a real pattern to learn, not pure noise.
"""

import csv
import random
from datetime import date, timedelta

import numpy as np
from faker import Faker

fake = Faker()
random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------
WINDOW_END = date(2026, 10, 10)
WINDOW_START = date(2024, 10, 10)
WINDOW_DAYS = (WINDOW_END - WINDOW_START).days

N_EQUIPMENT = 45
N_EMPLOYEES = 20
N_PROJECTS = 10

OUT_DIR = "ems_synthetic_data_strong"
import os
os.makedirs(OUT_DIR, exist_ok=True)


def rand_date(start, end):
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def write_csv(name, rows, fieldnames):
    path = os.path.join(OUT_DIR, f"{name}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows -> {path}")


# ---------------------------------------------------------------
# 1. ROLE
# ---------------------------------------------------------------
roles = [
    {"Role_ID": 1, "Role_Name": "Site Engineer", "Role_Description": "Handles equipment data entry, fuel and utilization logging, incident reporting, and transfer requests."},
    {"Role_ID": 2, "Role_Name": "Workshop Mechanic", "Role_Description": "Handles scheduled maintenance, breakdown logging, and repair records."},
    {"Role_ID": 3, "Role_Name": "Fleet Manager", "Role_Description": "Approves or rejects equipment transfer requests and views operational and predictive analytics."},
]
write_csv("ROLE", roles, ["Role_ID", "Role_Name", "Role_Description"])

# ---------------------------------------------------------------
# 2. EMPLOYEE
# ---------------------------------------------------------------
employees = []
role_weights = [1] * 10 + [2] * 5 + [3] * 5  # 10 SE, 5 WM, 5 FM
for i, role_id in enumerate(role_weights, start=1):
    emp_id = f"EMP-{i:03d}"
    name = fake.name()
    employees.append({
        "Employee_ID": emp_id,
        "Employee_Name": name,
        "Email": f"{name.lower().replace(' ', '.')}{i}@ems-demo.com",
        "Phone": fake.numerify("9#########"),
        "Role_ID": role_id,
        "Employee_Status": "Active" if random.random() > 0.05 else "Inactive",
    })
write_csv("EMPLOYEE", employees, ["Employee_ID", "Employee_Name", "Email", "Phone", "Role_ID", "Employee_Status"])

site_engineers = [e["Employee_ID"] for e in employees if e["Role_ID"] == 1]
fleet_managers = [e["Employee_ID"] for e in employees if e["Role_ID"] == 3]

# ---------------------------------------------------------------
# 3. PROJECT
# ---------------------------------------------------------------
project_names = [
    "Apex Mining Sector B", "Rocky Ridge Tunnel", "Blackwood Quarry East",
    "Salt Lake Transit Extension", "Harbor Bridge Expansion", "Greenfield Highway Phase 2",
    "Northgate Industrial Park", "Coastal Pipeline Corridor", "Summit Dam Rehabilitation",
    "Riverside Logistics Hub",
]
locations = ["Dammam", "Jubail", "Al Khobar", "Riyadh", "Jeddah", "Dhahran"]
projects = []
for i, pname in enumerate(project_names, start=1):
    start = rand_date(WINDOW_START, WINDOW_START + timedelta(days=200))
    end = start + timedelta(days=random.randint(300, 700))
    status = random.choices(["Active", "On Hold", "Completed"], weights=[6, 1, 3])[0]
    projects.append({
        "Project_ID": f"PRJ-{i:03d}",
        "Project_Name": pname,
        "Location": random.choice(locations),
        "Start_Date": start.isoformat(),
        "Expected_End_Date": end.isoformat(),
        "Project_Status": status,
    })
write_csv("PROJECT", projects, ["Project_ID", "Project_Name", "Location", "Start_Date", "Expected_End_Date", "Project_Status"])
project_ids = [p["Project_ID"] for p in projects]
project_span = {p["Project_ID"]: (date.fromisoformat(p["Start_Date"]), date.fromisoformat(p["Expected_End_Date"])) for p in projects}

# ---------------------------------------------------------------
# 4. EQUIPMENT
# ---------------------------------------------------------------
equip_types = ["Excavator", "Dozer", "Dump Truck", "Crane", "Wheel Loader", "Grader", "Compactor", "Forklift"]
manufacturers = ["Caterpillar", "Komatsu", "Volvo", "Liebherr", "JCB", "Hitachi"]
fuel_types = ["Diesel"] * 9 + ["Petrol"] + ["Electric"]  # mostly diesel

equipment = []
for i in range(1, N_EQUIPMENT + 1):
    eq_id = f"EQ-{i:03d}"
    mfg_year = random.randint(2015, 2025)
    purchase_date = date(mfg_year, random.randint(1, 12), random.randint(1, 28))
    status = random.choices(
        ["Active", "Idle", "Under Repair", "Decommissioned"],
        weights=[70, 15, 10, 5],
    )[0]
    equipment.append({
        "Equipment_ID": eq_id,
        "Equipment_Type": random.choice(equip_types),
        "Manufacturer": random.choice(manufacturers),
        "Model": f"{random.choice(['X','D','L','C'])}{random.randint(100,999)}{random.choice(['','D','H'])}",
        "Manufacturing_Year": mfg_year,
        "Fuel_Type": random.choice(fuel_types),
        "Capacity": round(random.uniform(1.5, 40.0), 2),
        "Purchase_Date": purchase_date.isoformat(),
        "Current_Status": status,
    })
write_csv("EQUIPMENT", equipment, ["Equipment_ID", "Equipment_Type", "Manufacturer", "Model", "Manufacturing_Year", "Fuel_Type", "Capacity", "Purchase_Date", "Current_Status"])

# Each equipment's "active window" in our data = max(purchase_date, WINDOW_START) .. WINDOW_END
eq_active_start = {}
for e in equipment:
    pd_ = date.fromisoformat(e["Purchase_Date"])
    eq_active_start[e["Equipment_ID"]] = max(pd_, WINDOW_START)

# ---------------------------------------------------------------
# 5. PROJECT_ACTIVITY
# ---------------------------------------------------------------
activity_names = ["Excavation", "Foundation Work", "Road Construction", "Site Clearance",
                   "Concrete Pouring", "Steel Erection", "Pipeline Laying", "Grading"]
project_activities = []
activity_id = 1
for pid in project_ids:
    pstart, pend = project_span[pid]
    n = random.randint(3, 5)
    for _ in range(n):
        a_start = rand_date(pstart, max(pstart, pend - timedelta(days=30)))
        a_end = a_start + timedelta(days=random.randint(20, 120))
        project_activities.append({
            "Activity_ID": activity_id,
            "Project_ID": pid,
            "Activity_Name": random.choice(activity_names),
            "Start_Date": a_start.isoformat(),
            "End_Date": a_end.isoformat(),
            "Expected_Intensity": random.choice(["Low", "Medium", "High"]),
        })
        activity_id += 1
write_csv("PROJECT_ACTIVITY", project_activities, ["Activity_ID", "Project_ID", "Activity_Name", "Start_Date", "End_Date", "Expected_Intensity"])

# ---------------------------------------------------------------
# 6. TRANSFER
# ---------------------------------------------------------------
transfers = []
transfer_id = 1
for e in equipment:
    n_transfers = random.randint(1, 4)
    for _ in range(n_transfers):
        from_p, to_p = random.sample(project_ids, 2)
        req_date = rand_date(eq_active_start[e["Equipment_ID"]], WINDOW_END - timedelta(days=5))
        status = random.choices(["Completed", "Approved", "Pending", "Rejected"], weights=[5, 3, 1, 1])[0]
        approved_by = random.choice(fleet_managers) if status in ("Completed", "Approved") else None
        eff_date = (req_date + timedelta(days=random.randint(1, 10))).isoformat() if status in ("Completed", "Approved") else ""
        transfers.append({
            "Transfer_ID": transfer_id,
            "Equipment_ID": e["Equipment_ID"],
            "From_Project_ID": from_p,
            "To_Project_ID": to_p,
            "Requested_By": random.choice(site_engineers),
            "Approved_By": approved_by if approved_by else "",
            "Request_Date": req_date.isoformat(),
            "Effective_Transfer_Date": eff_date,
            "Transfer_Status": status,
        })
        transfer_id += 1
write_csv("TRANSFER", transfers, ["Transfer_ID", "Equipment_ID", "From_Project_ID", "To_Project_ID", "Requested_By", "Approved_By", "Request_Date", "Effective_Transfer_Date", "Transfer_Status"])

# ---------------------------------------------------------------
# 7+8+10+11+12: Per-equipment weekly simulation
# Drives UTILIZATION_LOG, FUEL_LOG, MAINTENANCE, BREAKDOWN, REPAIR together
# so cumulative hours / last-service / age stay internally consistent.
# ---------------------------------------------------------------
burn_rate_by_type = {  # liters per operating hour, rough
    "Excavator": 18, "Dozer": 22, "Dump Truck": 15, "Crane": 12,
    "Wheel Loader": 16, "Grader": 14, "Compactor": 10, "Forklift": 5,
}
FUEL_PRICE = 1.65  # per liter

utilization_logs, fuel_logs, maintenance_logs = [], [], []
breakdowns, repairs, incidents = [], [], []
util_id = fuel_id = maint_id = bd_id = rep_id = inc_id = 1

incident_types = ["Near Miss", "Minor Collision", "Equipment Tip-Over Risk", "Safety Violation", "Property Damage"]
breakdown_descriptions = [
    "Hydraulic pressure drop detected during operation.",
    "Engine overheating under load.",
    "Unusual vibration and noise from main drivetrain.",
    "Electrical fault in control panel.",
    "Track/undercarriage wear causing loss of traction.",
    "Fuel system blockage.",
]

service_delay = {}
# DEMO LINK: planned work intensity at the machine's project drives hours and fuel
INTENSITY_FACTOR = {"Low": 0.75, "Medium": 1.0, "High": 1.3}
def project_intensity(pid, day):
    f = [INTENSITY_FACTOR[a["Expected_Intensity"]] for a in project_activities
         if a["Project_ID"] == pid and a["Start_Date"] <= day.isoformat() <= a["End_Date"]]
    return sum(f) / len(f) if f else 0.9   # no planned work -> a little quieter
for e in equipment:
    eq_id = e["Equipment_ID"]
    mfg_year = e["Manufacturing_Year"]
    start = eq_active_start[eq_id]
    weeks = max(1, (WINDOW_END - start).days // 7)

    cumulative_hours = 0.0
    last_service_date = start - timedelta(days=random.randint(10, 80))
    current_project = random.choice(project_ids)

    for w in range(weeks):
        log_date = start + timedelta(days=7 * w)
        if random.random() < 0.08:  # occasional project reassignment
            current_project = random.choice(project_ids)

        # ---- UTILIZATION_LOG ----
        intensity = project_intensity(current_project, log_date)
        hours = min(110, max(0, np.random.normal(42 * intensity, 10)))
        cumulative_hours += hours
        utilization_logs.append({
            "Utilization_ID": util_id, "Equipment_ID": eq_id, "Project_ID": current_project,
            "Log_Date": log_date.isoformat(), "Operating_Hours": round(hours, 2),
        })
        util_id += 1

        # ---- FUEL_LOG ----
        burn = burn_rate_by_type.get(e["Equipment_Type"], 15)
        consumed = max(0, hours * burn * (1 + 0.5 * (intensity - 1)) * np.random.normal(1.0, 0.1))
        fuel_logs.append({
            "Fuel_Log_ID": fuel_id, "Equipment_ID": eq_id, "Project_ID": current_project,
            "Fuel_Date": log_date.isoformat(), "Fuel_Consumed": round(consumed, 2),
            "Fuel_Cost": round(consumed * FUEL_PRICE, 2),
        })
        fuel_id += 1

        # ---- MAINTENANCE (every ~13 weeks) ----
        days_since_service = (log_date - last_service_date).days
        if days_since_service >= 90 + service_delay.get(eq_id, 0):
            service_delay[eq_id] = random.choice([0, 0, 0, 20, 40, 60, 90, 120])
            service_date = log_date
            maintenance_logs.append({
                "Maintenance_ID": maint_id, "Equipment_ID": eq_id, "Service_Date": service_date.isoformat(),
                "Maintenance_Type": random.choice(["Routine Service", "Inspection", "Oil Change", "Filter Replacement"]),
                "Meter_Reading": round(cumulative_hours, 2),
                "Service_Details": "Scheduled preventive maintenance performed as per service interval.",
                "Next_Service_Date": (service_date + timedelta(days=90)).isoformat(),
                "Total_Cost": round(random.uniform(150, 1200), 2),
            })
            maint_id += 1
            last_service_date = service_date
            days_since_service = 0

        # ---- BREAKDOWN risk ----
        age_years = log_date.year - mfg_year
        # STRONGER (demo) pattern: older, heavily used and service-overdue machines break down more often
        risk = (
            0.0012 +
            0.0060 * max(0, age_years - 3) ** 1.3 / 3 +
            0.0000012 * max(0, cumulative_hours - 1500) +
            0.0050 * max(0, days_since_service - 100) / 3 +
            0.0006 * max(0, hours - 55)
        )
        risk = min(risk, 0.25)
        if random.random() < risk:
            bd_date = log_date + timedelta(days=random.randint(0, 6))
            if bd_date > WINDOW_END:
                bd_date = WINDOW_END
            downtime = round(random.uniform(2, 72), 2)
            status = random.choices(["Resolved", "Under Repair", "Open"], weights=[8, 1, 1])[0]
            breakdowns.append({
                "Breakdown_ID": bd_id, "Equipment_ID": eq_id, "Breakdown_Date": bd_date.isoformat(),
                "Description": random.choice(breakdown_descriptions),
                "Downtime_Hours": downtime, "Breakdown_Status": status,
            })
            if status != "Open":
                n_rep = random.choice([1, 1, 2])
                for _ in range(n_rep):
                    rep_date = bd_date + timedelta(days=random.randint(0, 3))
                    repairs.append({
                        "Repair_ID": rep_id, "Breakdown_ID": bd_id, "Repair_Date": rep_date.isoformat(),
                        "Parts_Replaced": random.choice(["Hydraulic seal", "Fuel filter", "Drive belt", "Control relay", "Track pad", "None"]),
                        "Labor_Hours": round(random.uniform(1, 10), 2),
                        "Parts_Cost": round(random.uniform(20, 1500), 2),
                        "Labor_Cost": round(random.uniform(50, 600), 2),
                        "Repair_Details": "Repair completed and equipment returned to service.",
                    })
                    rep_id += 1
            bd_id += 1

        # ---- INCIDENT (rare) ----
        if random.random() < 0.004:
            incidents.append({
                "Incident_ID": inc_id, "Equipment_ID": eq_id, "Project_ID": current_project,
                "Incident_Date": log_date.isoformat(), "Incident_Type": random.choice(incident_types),
                "Severity": random.choices(["Minor", "Major", "Critical"], weights=[7, 2, 1])[0],
                "Description": "Incident reported during routine site operation.",
            })
            inc_id += 1

write_csv("UTILIZATION_LOG", utilization_logs, ["Utilization_ID", "Equipment_ID", "Project_ID", "Log_Date", "Operating_Hours"])
write_csv("FUEL_LOG", fuel_logs, ["Fuel_Log_ID", "Equipment_ID", "Project_ID", "Fuel_Date", "Fuel_Consumed", "Fuel_Cost"])
write_csv("MAINTENANCE", maintenance_logs, ["Maintenance_ID", "Equipment_ID", "Service_Date", "Maintenance_Type", "Meter_Reading", "Service_Details", "Next_Service_Date", "Total_Cost"])
write_csv("BREAKDOWN", breakdowns, ["Breakdown_ID", "Equipment_ID", "Breakdown_Date", "Description", "Downtime_Hours", "Breakdown_Status"])
write_csv("REPAIR", repairs, ["Repair_ID", "Breakdown_ID", "Repair_Date", "Parts_Replaced", "Labor_Hours", "Parts_Cost", "Labor_Cost", "Repair_Details"])
write_csv("INCIDENT", incidents, ["Incident_ID", "Equipment_ID", "Project_ID", "Incident_Date", "Incident_Type", "Severity", "Description"])

print("\nDone. Total rows:", sum([
    len(roles), len(employees), len(projects), len(equipment), len(project_activities),
    len(transfers), len(utilization_logs), len(fuel_logs), len(maintenance_logs),
    len(breakdowns), len(repairs), len(incidents),
]))