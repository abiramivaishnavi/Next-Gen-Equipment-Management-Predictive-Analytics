"""
Dashboard numbers for the three role dashboards (wireframes 2, 10 and 15).

One endpoint:  GET /dashboard/summary   (any signed-in user)
It looks at WHO is calling (from the login token) and returns that role's cards,
alerts, recent entries and side panel in one generic shape, so the React page can
draw all three dashboards with the same code.

Read-only: nothing here changes data.
"""

from datetime import date

from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from database import get_connection
from security import get_current_user
from fuel_units import LIQUID_SQL, ELECTRIC_SQL

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

SERVICE_WARNING_DAYS = 14  # "due soon" window


def units(n):
    return f"{n} unit" + ("" if n == 1 else "s")


# ---------- small query helpers ----------

def one(cursor, sql, params=None):
    cursor.execute(sql, params)
    return cursor.fetchone()


def many(cursor, sql, params=None):
    cursor.execute(sql, params)
    return cursor.fetchall()


def fleet_status(cursor):
    """Equipment grouped by Current_Status (decommissioned units are not 'fleet')."""
    rows = many(
        cursor,
        'SELECT "Current_Status" AS status, COUNT(*) AS n FROM "EQUIPMENT" '
        'WHERE "Current_Status" <> \'Decommissioned\' GROUP BY 1 ORDER BY 2 DESC;',
    )
    total = sum(r["n"] for r in rows)
    in_repair = sum(r["n"] for r in rows if "repair" in (r["status"] or "").lower())
    availability = round(100.0 * (total - in_repair) / total, 1) if total else 0.0
    return rows, total, availability


def services_due(cursor):
    """Latest service record per machine -> its Next_Service_Date. Overdue / due soon."""
    return many(
        cursor,
        """
        WITH latest AS (
            SELECT DISTINCT ON ("Equipment_ID") "Equipment_ID", "Next_Service_Date"
            FROM "MAINTENANCE"
            ORDER BY "Equipment_ID", "Service_Date" DESC, "Maintenance_ID" DESC
        )
        SELECT e."Equipment_ID", e."Equipment_Name", l."Next_Service_Date",
               (CURRENT_DATE - l."Next_Service_Date") AS days_overdue
        FROM latest l JOIN "EQUIPMENT" e USING ("Equipment_ID")
        WHERE e."Current_Status" <> 'Decommissioned'
          AND l."Next_Service_Date" IS NOT NULL
          AND l."Next_Service_Date" <= CURRENT_DATE + %s
        ORDER BY l."Next_Service_Date";
        """,
        (SERVICE_WARNING_DAYS,),
    )


def open_breakdowns(cursor):
    return many(
        cursor,
        """
        SELECT b."Breakdown_ID", b."Equipment_ID", e."Equipment_Name", b."Breakdown_Date",
               b."Description", b."Downtime_Hours", b."Breakdown_Status"
        FROM "BREAKDOWN" b JOIN "EQUIPMENT" e USING ("Equipment_ID")
        WHERE b."Breakdown_Status" <> 'Resolved'
        ORDER BY b."Breakdown_Date" DESC, b."Breakdown_ID" DESC;
        """,
    )


def oldest_open(brk):
    """(date, days) of the longest-waiting unresolved breakdown, or (None, 0) when none is open.
    A date is easier for a manager to read than a pile of downtime hours: 'open since 2024-11-05 (732 days)'."""
    if not brk:
        return None, 0
    oldest = min(b["Breakdown_Date"] for b in brk)
    return oldest, max((date.today() - oldest).days, 0)


def fuel_recent(cursor):
    """Fuel over the latest 30 days OF RECORDS (not 'today'), so the card is never
    empty just because nobody has logged fuel this week.

    Litres and kWh must not be added together, so: litres = liquid fuels only (diesel/petrol),
    kwh = electricity, other = any other fuel type (unit unknown). Cost (SAR) is a plain total."""
    return one(
        cursor,
        f"""
        SELECT COALESCE(SUM(f."Fuel_Consumed") FILTER (WHERE {LIQUID_SQL}), 0)   AS litres,
               COALESCE(SUM(f."Fuel_Consumed") FILTER (WHERE {ELECTRIC_SQL}), 0) AS kwh,
               COALESCE(SUM(f."Fuel_Consumed") FILTER (WHERE NOT ({LIQUID_SQL}) AND NOT ({ELECTRIC_SQL})), 0) AS other,
               COALESCE(SUM(f."Fuel_Cost"), 0)                                   AS cost
        FROM "FUEL_LOG" f JOIN "EQUIPMENT" e ON e."Equipment_ID" = f."Equipment_ID"
        WHERE f."Fuel_Date" > (SELECT MAX("Fuel_Date") FROM "FUEL_LOG") - 30;
        """,
    )


def fuel_cost_text(fuel, prefix=""):
    """'Cost SAR 12,345.00 · + 1,200 kWh electric' (the extras only appear when there is something to show)."""
    text = f'{prefix}SAR {float(fuel["cost"]):,.2f}'
    if float(fuel["kwh"]) > 0:
        text += f' · + {float(fuel["kwh"]):,.0f} kWh electric'
    if float(fuel["other"]) > 0:
        text += f' · + {float(fuel["other"]):,.0f} units other fuel'
    return text


def pending_transfers(cursor):
    return many(
        cursor,
        """
        SELECT t."Transfer_ID", t."Equipment_ID", e."Equipment_Name",
               t."From_Project_ID", t."To_Project_ID", t."Request_Date",
               emp."Employee_Name" AS requested_by_name
        FROM "TRANSFER" t
        JOIN "EQUIPMENT" e USING ("Equipment_ID")
        LEFT JOIN "EMPLOYEE" emp ON emp."Employee_ID" = t."Requested_By"
        WHERE t."Transfer_Status" = 'Pending'
        ORDER BY t."Request_Date", t."Transfer_ID";
        """,
    )


# ---------- shared pieces of the response ----------

def status_bars(rows, total):
    return {
        "title": "Fleet status",
        "type": "bars",
        "rows": [
            {
                "label": r["status"],
                "value": r["n"],
                "pct": round(100.0 * r["n"] / total) if total else 0,
                "tone": "bad" if "repair" in (r["status"] or "").lower()
                        else "warn" if (r["status"] or "").lower() == "idle" else "ok",
            }
            for r in rows
        ],
    }


# "Open" is confusing on a dashboard (open for work? open case?). Say what it means.
BREAKDOWN_BADGES = {"Open": "Awaiting repair", "Under Repair": "Under repair"}


def breakdown_alerts(rows, limit=3):
    return [
        {
            "title": f'{b["Equipment_Name"]} ({b["Equipment_ID"]})',
            "detail": (b["Description"] or "Breakdown reported")[:110],
            "badge": BREAKDOWN_BADGES.get(b["Breakdown_Status"], b["Breakdown_Status"]).upper(),
            "tone": "bad",
        }
        for b in rows[:limit]
    ]


def service_alerts(rows, limit=3):
    out = []
    for s in rows[:limit]:
        late = s["days_overdue"] or 0
        out.append(
            {
                "title": f'{s["Equipment_Name"]} ({s["Equipment_ID"]})',
                "detail": (f"Service overdue by {late} days" if late > 0
                           else f'Service due {s["Next_Service_Date"]}'),
                "badge": "SERVICE OVERDUE" if late > 0 else "SERVICE DUE",
                "tone": "warn",
            }
        )
    return out


# ---------- the three dashboards ----------

def site_engineer_view(cur):
    rows, total, availability = fleet_status(cur)
    due = services_due(cur)
    overdue = sum(1 for s in due if (s["days_overdue"] or 0) > 0)
    fuel = fuel_recent(cur)
    brk = open_breakdowns(cur)
    in_repair = sum(r["n"] for r in rows if "repair" in (r["status"] or "").lower())
    incidents = many(
        cur,
        'SELECT i."Incident_ID", i."Equipment_ID", i."Incident_Type", i."Incident_Type_Other", '
        'i."Severity", i."Incident_Date", i."Incident_Time" '
        'FROM "INCIDENT" i ORDER BY i."Incident_Date" DESC, i."Incident_Time" DESC, i."Incident_ID" DESC LIMIT 5;',
    )
    return {
        "title": "Site Fleet Overview",
        "kpis": [
            {"label": "Fleet size", "value": units(total),
             "sub": ", ".join(f'{r["n"]} {r["status"]}' for r in rows) or "No equipment yet", "tone": "neutral"},
            {"label": "Availability", "value": f"{total - in_repair} of {total} units",
             "sub": f"available ({availability}%)", "tone": "ok" if availability >= 90 else "warn"},
            {"label": "Service due (14 days)", "value": units(len(due)),
             "sub": f"{overdue} already overdue", "tone": "warn" if due else "ok"},
            {"label": "Fuel (latest 30 days)", "value": f'{float(fuel["litres"]):,.0f} L',
             "sub": fuel_cost_text(fuel, "Cost "), "tone": "neutral"},
        ],
        "alerts_title": "Equipment alerts",
        "alerts": breakdown_alerts(brk) + service_alerts(due),
        "recent": {
            "title": "Recent incidents",
            "rows": [
                {
                    "title": f'{i["Incident_Type_Other"] or i["Incident_Type"]} — {i["Severity"]}',
                    "detail": f'Equipment {i["Equipment_ID"]}',
                    "right": f'{i["Incident_Date"]} {str(i["Incident_Time"])[:5]}',
                }
                for i in incidents
            ],
        },
        "panel": status_bars(rows, total),
    }


def mechanic_view(cur):
    rows, total, _ = fleet_status(cur)
    due = services_due(cur)
    overdue = sum(1 for s in due if (s["days_overdue"] or 0) > 0)
    brk = open_breakdowns(cur)
    oldest_date, oldest_days = oldest_open(brk)
    under_repair = sum(1 for b in brk if b["Breakdown_Status"] == "Under Repair")
    repairs30 = one(
        cur,
        'SELECT COUNT(*) AS n FROM "REPAIR" WHERE "Repair_Date" > (SELECT MAX("Repair_Date") FROM "REPAIR") - 30;',
    )["n"]
    recent = many(
        cur,
        'SELECT r."Repair_ID", r."Repair_Date", r."Parts_Replaced", r."Labor_Hours", b."Equipment_ID" '
        'FROM "REPAIR" r JOIN "BREAKDOWN" b USING ("Breakdown_ID") '
        'ORDER BY r."Repair_Date" DESC, r."Repair_ID" DESC LIMIT 5;',
    )
    status_rows = many(
        cur,
        'SELECT "Breakdown_Status" AS status, COUNT(*) AS n FROM "BREAKDOWN" GROUP BY 1 ORDER BY 2 DESC;',
    )
    status_total = sum(r["n"] for r in status_rows)
    panel = {
        "title": "Breakdown log by status",
        "type": "bars",
        "rows": [
            {"label": r["status"], "value": r["n"],
             "pct": round(100.0 * r["n"] / status_total) if status_total else 0,
             "tone": "ok" if r["status"] == "Resolved" else "bad"}
            for r in status_rows
        ],
    }
    return {
        "title": "Workshop Overview",
        "kpis": [
            {"label": "Unresolved breakdowns", "value": units(len(brk)),
             "sub": f"{under_repair} under repair", "tone": "bad" if brk else "ok"},
            {"label": "Oldest open breakdown", "value": str(oldest_date) if oldest_date else "None",
             "sub": (f"Waiting {oldest_days:,} day" + ("" if oldest_days == 1 else "s")) if oldest_date else "Nothing unresolved",
             "tone": "warn" if oldest_date else "ok"},
            {"label": "Service due (14 days)", "value": units(len(due)),
             "sub": f"{overdue} already overdue", "tone": "warn" if due else "ok"},
            {"label": "Repairs (latest 30 days)", "value": f"{repairs30}",
             "sub": "Repair records logged", "tone": "neutral"},
        ],
        "alerts_title": "Work needing attention",
        "alerts": breakdown_alerts(brk, 4) + service_alerts(due, 3),
        "recent": {
            "title": "Recent repairs",
            "rows": [
                {
                    "title": f'Repair #{r["Repair_ID"]} — {r["Equipment_ID"]}',
                    "detail": (r["Parts_Replaced"] or "No parts recorded")[:90],
                    "right": str(r["Repair_Date"]),
                }
                for r in recent
            ],
        },
        "panel": panel,
    }


def fleet_manager_view(cur):
    rows, total, availability = fleet_status(cur)
    due = services_due(cur)
    overdue = sum(1 for s in due if (s["days_overdue"] or 0) > 0)
    brk = open_breakdowns(cur)
    repair_n = sum(1 for b in brk if b["Breakdown_Status"] == "Under Repair")
    open_n = len(brk) - repair_n  # everything unresolved that is not yet in the workshop
    pending = pending_transfers(cur)
    fuel = fuel_recent(cur)
    projects = many(
        cur,
        """
        SELECT p."Project_ID", p."Project_Name",
               COUNT(e."Equipment_ID") AS units,
               COUNT(*) FILTER (WHERE e."Current_Status" = 'Active') AS active,
               COUNT(*) FILTER (WHERE e."Current_Status" ILIKE '%repair%') AS repair
        FROM "PROJECT" p LEFT JOIN "EQUIPMENT" e ON e."Current_Project_ID" = p."Project_ID"
             AND e."Current_Status" <> 'Decommissioned'
        WHERE p."Project_Status" = 'Active'
        GROUP BY p."Project_ID", p."Project_Name"
        ORDER BY units DESC, p."Project_ID" LIMIT 8;
        """,
    )
    return {
        "title": "Fleet Operations Overview",
        "kpis": [
            {"label": "Fleet availability", "value": f"{availability}%",
             "sub": f"{total} units in service", "tone": "ok" if availability >= 90 else "warn"},
            {"label": "Unresolved breakdowns", "value": units(len(brk)),
             "sub": (f"{open_n} open \u00b7 {repair_n} under repair" if brk else "Nothing unresolved"),
             "tone": "bad" if brk else "ok"},
            {"label": "Pending approvals", "value": f"{len(pending)} transfer" + ("" if len(pending) == 1 else "s"),
             "sub": (f'Oldest request: {pending[0]["Request_Date"]}' if pending else "Nothing waiting"),
             "tone": "warn" if pending else "ok"},
            {"label": "Fuel (latest 30 days)", "value": f'{float(fuel["litres"]):,.0f} L',
             "sub": fuel_cost_text(fuel), "tone": "neutral"},
        ],
        "alerts_title": "Urgent operational alerts",
        "alerts": breakdown_alerts(brk, 3) + service_alerts(due, 3),
        "recent": {
            "title": "Transfer requests waiting for you",
            "rows": [
                {
                    "title": f'#{t["Transfer_ID"]} {t["Equipment_Name"]} ({t["Equipment_ID"]})',
                    "detail": f'{t["From_Project_ID"]} → {t["To_Project_ID"]} · requested by {t["requested_by_name"]}',
                    "right": str(t["Request_Date"]),
                }
                for t in pending[:5]
            ],
        },
        "panel": {
            "title": "Project equipment overview",
            "type": "table",
            "columns": ["Project", "Units", "Active", "Under repair"],
            "rows": [
                [f'{p["Project_Name"]}', p["units"], p["active"], p["repair"]] for p in projects
            ],
        },
        "pending_count": len(pending),
    }


KPI_ICONS = {
    "site_engineer": ["equipment", "check", "clock", "fuel"],
    "mechanic": ["alert", "clock", "tool", "tool"],
    "fleet_manager": ["check", "alert", "transfer", "fuel"],
}

VIEWS = {
    "site_engineer": site_engineer_view,
    "mechanic": mechanic_view,
    "fleet_manager": fleet_manager_view,
}


@router.get("/summary")
def dashboard_summary(user: dict = Depends(get_current_user)):
    view = VIEWS.get(user["Role"])
    if view is None:
        return {"title": "Dashboard", "kpis": [], "alerts": [], "recent": {"title": "", "rows": []}, "panel": None}
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            data = view(cursor)
    # icon for each KPI card (names match the frontend Icon component)
    for card, icon in zip(data.get("kpis", []), KPI_ICONS.get(user["Role"], [])):
        card["icon"] = icon
    return data


@router.get("/meta")
def dashboard_meta(user: dict = Depends(get_current_user)):
    """Small numbers shown on every page: top strip, sidebar badge, diesel rate."""
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            sites = one(cursor, 'SELECT COUNT(*) AS n FROM "PROJECT" WHERE "Project_Status" = \'Active\';')["n"]
            assets = one(
                cursor,
                'SELECT COUNT(*) AS n FROM "EQUIPMENT" WHERE "Current_Status" <> \'Decommissioned\';',
            )["n"]
            pending = one(cursor, 'SELECT COUNT(*) AS n FROM "TRANSFER" WHERE "Transfer_Status" = \'Pending\';')["n"]
            # New self-registered accounts wait as 'Inactive' until a Fleet Manager activates them.
            accounts_waiting = one(
                cursor, 'SELECT COUNT(*) AS n FROM "EMPLOYEE" WHERE "Employee_Status" = \'Inactive\';'
            )["n"]
            rate = one(
                cursor,
                '''
                SELECT "Rate_Per_Liter" FROM "FUEL_RATE"
                WHERE "Fuel_Type" ILIKE 'diesel' AND "Effective_Date" <= CURRENT_DATE
                ORDER BY "Effective_Date" DESC LIMIT 1;
                ''',
            )
    return {
        "projects": sites,
        "assets": assets,
        "pending_transfers": pending,
        "pending_accounts": accounts_waiting,
        "diesel_rate": float(rate["Rate_Per_Liter"]) if rate else None,
    }
