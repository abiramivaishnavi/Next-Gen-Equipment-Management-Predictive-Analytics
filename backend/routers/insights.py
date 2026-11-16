"""
Read-only "insight" endpoints for the lookup / history / overview screens.
Nothing here changes data.

This router is attached to the records router (see the bottom of records.py), so main.py
needs NO extra line for it.

  GET /info/equipment?q=            search equipment (ID, name, type, project ...)          any signed-in role
  GET /info/equipment/{id}          one equipment's profile + condition summary             any signed-in role
  GET /info/projects?q=             search projects, with unit counts                       any signed-in role
  GET /info/projects/{id}           one project + the equipment currently on it             any signed-in role
  GET /info/equipment/{id}/export   the profile as a one-page PDF                          any signed-in role
  GET /info/projects/{id}/export    the project + its equipment as a PDF                    any signed-in role
  GET /history/{equipment_id}       service + breakdown + repair timeline (date filters)    mechanic, fleet manager
  GET /overview/operational         per-project operations + maintenance snapshot           fleet manager
"""

import re
from datetime import date, timedelta

import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from psycopg.rows import dict_row

from database import get_connection
from fuel_units import ELECTRIC_SQL, LIQUID_SQL, unit_label
from security import get_current_user, require_roles

router = APIRouter(tags=["Insights"])

WINDOW_DAYS = 30        # "recent" window for usage / fuel numbers
SERVICE_WARNING_DAYS = 14


# ---------------------------------------------------------------------------
# Search helpers (same idea as the Records page: ignore capitals, dashes, leading zeros)
# ---------------------------------------------------------------------------
def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _strip_zeros(text: str) -> str:
    return re.sub(r"(^|[^0-9])0+([0-9])", r"\1\2", text)


def search_clause(words_source: str, q: str | None):
    """Return (sql, params) that keeps rows whose text contains EVERY word of q."""
    clauses, params = [], []
    for word in (q or "").split():
        squashed = _squash(word)
        if not squashed:
            continue
        zero_free = f"regexp_replace(regexp_replace(lower({words_source}), '(^|[^0-9])0+([0-9])', '\\1\\2', 'g'), '[^a-z0-9,]', '', 'g')"
        raw = f"regexp_replace(lower({words_source}), '[^a-z0-9,]', '', 'g')"
        if re.search(r"[a-z]", squashed):
            clauses.append(f"{zero_free} LIKE %s")
            params.append(f"%{_squash(_strip_zeros(word.lower()))}%")
        else:
            clauses.append(f"{raw} LIKE %s")
            params.append(f"%{squashed}%")
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def exact_first(id_column: str, q: str | None):
    """ORDER BY piece that puts an exact ID match first ('eq1' -> EQ-001 before EQ-010)."""
    wanted = _squash(_strip_zeros((q or "").strip().lower()))
    if not wanted:
        return "", []
    expr = f"regexp_replace(regexp_replace(lower({id_column}), '(^|[^0-9])0+([0-9])', '\\1\\2', 'g'), '[^a-z0-9]', '', 'g')"
    return f"CASE WHEN {expr} = %s THEN 0 ELSE 1 END, ", [wanted]


# ---------------------------------------------------------------------------
# Information lookup
# ---------------------------------------------------------------------------
@router.get("/info/equipment")
def info_equipment(q: str | None = None, user: dict = Depends(get_current_user)):
    hay = "concat_ws(',', e::text, p.\"Project_Name\")"
    where, params = search_clause(hay, q)
    order, order_params = exact_first('e."Equipment_ID"', q)
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            'SELECT e."Equipment_ID", e."Equipment_Name", e."Equipment_Type", e."Current_Status", '
            '       e."Current_Project_ID", p."Project_Name" AS "Current_Project_Name" '
            'FROM "EQUIPMENT" e LEFT JOIN "PROJECT" p ON p."Project_ID" = e."Current_Project_ID" '
            f"WHERE {where} ORDER BY {order}e.\"Equipment_ID\" LIMIT 25;",
            (params + order_params) or None,
        )
        return cur.fetchall()


def equipment_health(cur, eq_id: str) -> dict:
    """Condition summary used on the equipment profile."""
    cur.execute(
        'SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE "Breakdown_Status" <> \'Resolved\') AS open_now, '
        'COALESCE(SUM("Downtime_Hours"), 0) AS downtime FROM "BREAKDOWN" WHERE "Equipment_ID" = %s;', (eq_id,))
    b = cur.fetchone()
    cur.execute('SELECT MAX("Service_Date") AS last_service FROM "MAINTENANCE" WHERE "Equipment_ID" = %s;', (eq_id,))
    last_service = cur.fetchone()["last_service"]
    cur.execute(
        'SELECT "Next_Service_Date" FROM "MAINTENANCE" WHERE "Equipment_ID" = %s AND "Next_Service_Date" IS NOT NULL '
        'ORDER BY "Service_Date" DESC, "Maintenance_ID" DESC LIMIT 1;', (eq_id,))
    nxt = cur.fetchone()
    next_service = nxt["Next_Service_Date"] if nxt else None
    cur.execute(
        'SELECT MAX("Log_Date") AS last_log, COALESCE(SUM("Operating_Hours"), 0) AS hours FROM "UTILIZATION_LOG" '
        'WHERE "Equipment_ID" = %s AND "Log_Date" > (SELECT COALESCE(MAX("Log_Date"), CURRENT_DATE) - %s '
        'FROM "UTILIZATION_LOG" WHERE "Equipment_ID" = %s);', (eq_id, WINDOW_DAYS, eq_id))
    u = cur.fetchone()
    cur.execute(
        'SELECT MAX("Fuel_Date") AS last_fuel, COALESCE(SUM("Fuel_Consumed"), 0) AS litres FROM "FUEL_LOG" '
        'WHERE "Equipment_ID" = %s AND "Fuel_Date" > (SELECT COALESCE(MAX("Fuel_Date"), CURRENT_DATE) - %s '
        'FROM "FUEL_LOG" WHERE "Equipment_ID" = %s);', (eq_id, WINDOW_DAYS, eq_id))
    f = cur.fetchone()
    cur.execute('SELECT "Fuel_Type" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (eq_id,))
    machine = cur.fetchone()
    cur.execute('SELECT "Transfer_ID" FROM "TRANSFER" WHERE "Equipment_ID" = %s AND "Transfer_Status" = \'Pending\' LIMIT 1;', (eq_id,))
    pending = cur.fetchone()
    today = date.today()
    return {
        "breakdowns_total": b["total"], "breakdowns_open": b["open_now"], "downtime_hours": float(b["downtime"]),
        "last_service": last_service, "next_service": next_service,
        "service_overdue_days": (today - next_service).days if next_service and next_service < today else 0,
        "util_hours": float(u["hours"]), "last_log": u["last_log"],
        # the number is litres for diesel/petrol and kWh for electric (key name kept for the frontend)
        "fuel_litres": float(f["litres"]), "fuel_unit": unit_label(machine["Fuel_Type"] if machine else None),
        "last_fuel": f["last_fuel"],
        "pending_transfer_id": pending["Transfer_ID"] if pending else None,
        "window_days": WINDOW_DAYS,
    }


@router.get("/info/equipment/{equipment_id}")
def info_equipment_profile(equipment_id: str, user: dict = Depends(get_current_user)):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            'SELECT e.*, p."Project_Name" AS "Current_Project_Name", p."Location" AS "Current_Project_Location" '
            'FROM "EQUIPMENT" e LEFT JOIN "PROJECT" p ON p."Project_ID" = e."Current_Project_ID" '
            'WHERE e."Equipment_ID" = %s;', (equipment_id,))
        equipment = cur.fetchone()
        if equipment is None:
            raise HTTPException(status_code=404, detail="Equipment not found")
        year = equipment.get("Manufacturing_Year")
        equipment["Age_Years"] = (date.today().year - year) if year else None
        return {"equipment": equipment, "health": equipment_health(cur, equipment_id)}


@router.get("/info/projects")
def info_projects(q: str | None = None, user: dict = Depends(get_current_user)):
    where, params = search_clause("p::text", q)
    order, order_params = exact_first('p."Project_ID"', q)
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            'SELECT p."Project_ID", p."Project_Name", p."Location", p."Project_Status", '
            '  (SELECT COUNT(*) FROM "EQUIPMENT" e WHERE e."Current_Project_ID" = p."Project_ID") AS "Units_On_Site" '
            f'FROM "PROJECT" p WHERE {where} ORDER BY {order}p."Project_ID" LIMIT 50;',
            (params + order_params) or None,
        )
        return cur.fetchall()


@router.get("/info/projects/{project_id}")
def info_project(project_id: str, user: dict = Depends(get_current_user)):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT * FROM "PROJECT" WHERE "Project_ID" = %s;', (project_id,))
        project = cur.fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        cur.execute(
            'SELECT "Equipment_ID", "Equipment_Name", "Equipment_Type", "Current_Status" FROM "EQUIPMENT" '
            'WHERE "Current_Project_ID" = %s ORDER BY "Equipment_ID";', (project_id,))
        equipment = cur.fetchall()
        cur.execute(
            'SELECT "Activity_Name", "Start_Date", "End_Date", "Expected_Intensity" FROM "PROJECT_ACTIVITY" '
            'WHERE "Project_ID" = %s ORDER BY "Start_Date" DESC LIMIT 5;', (project_id,))
        return {"project": project, "equipment": equipment, "activities": cur.fetchall()}


# ---------------------------------------------------------------------------
# PDF downloads of a profile (same look as the Records page PDFs)
# ---------------------------------------------------------------------------
def _pdf(title: str, sections: list, filename: str) -> Response:
    """sections = [(heading, [(label, value), ...])]  or  [(heading, {"columns": [...], "rows": [[...]]})]"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF needs one extra package. Run: pip install reportlab")

    styles = getSampleStyleSheet()
    teal = colors.HexColor("#0f9488")
    story = [
        Paragraph(f"Next-Gen Equipment Management System: {title}", styles["Title"]),
        Paragraph(f"Generated {date.today().isoformat()}", styles["BodyText"]),
        Spacer(1, 10),
    ]
    for heading, body in sections:
        story.append(Paragraph(heading, styles["Heading3"]))
        if isinstance(body, dict):
            data = [body["columns"]] + [["" if c is None else str(c) for c in r] for r in body["rows"]] if body["rows"] else None
            if data is None:
                story.append(Paragraph("None.", styles["BodyText"]))
                continue
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), teal), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ]))
        else:
            table = Table([[k, "-" if v is None or v == "" else str(v)] for k, v in body], colWidths=[150, 320])
            table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ]))
        story.append(table)
        story.append(Spacer(1, 8))

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36).build(story)
    return Response(
        content=buffer.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/info/equipment/{equipment_id}/export")
def export_equipment_profile(equipment_id: str, user: dict = Depends(get_current_user)):
    data = info_equipment_profile(equipment_id, user)
    e, h = data["equipment"], data["health"]
    sections = [
        ("Equipment", [
            ("Equipment ID", e["Equipment_ID"]), ("Name", e.get("Equipment_Name")), ("Type", e.get("Equipment_Type")),
            ("Manufacturer", e.get("Manufacturer")), ("Model", e.get("Model")),
            ("Built", f'{e["Manufacturing_Year"]} ({e["Age_Years"]} years old)' if e.get("Manufacturing_Year") else None),
            ("Fuel type", e.get("Fuel_Type")), ("Capacity", f'{e["Capacity"]} {e.get("Capacity_Unit") or ""}'.strip() if e.get("Capacity") is not None else None), ("Purchased", e.get("Purchase_Date")),
        ]),
        ("Where it is", [
            ("Status", e.get("Current_Status")),
            ("Project", f'{e["Current_Project_ID"]} - {e.get("Current_Project_Name") or ""}' if e.get("Current_Project_ID") else "Not assigned"),
            ("Location", e.get("Current_Project_Location")),
            ("Transfer pending", f'Yes (#{h["pending_transfer_id"]})' if h["pending_transfer_id"] else "No"),
        ]),
        ("Condition", [
            ("Breakdowns (all time)", h["breakdowns_total"]), ("Unresolved now", h["breakdowns_open"]),
            ("Total downtime (h)", h["downtime_hours"]), ("Last service", h["last_service"]),
            ("Next service", h["next_service"]),
            ("Service overdue (days)", h["service_overdue_days"] or None),
        ]),
        (f'Recent activity (last {h["window_days"]} days of records)', [
            ("Operating hours", f'{h["util_hours"]} (to {h["last_log"]})' if h["last_log"] else "none logged"),
            (f'Fuel ({h["fuel_unit"]})', f'{h["fuel_litres"]} (to {h["last_fuel"]})' if h["last_fuel"] else "none logged"),
        ]),
    ]
    return _pdf(f'Equipment {e["Equipment_ID"]}', sections, f'equipment-{e["Equipment_ID"]}-{date.today().isoformat()}.pdf')


@router.get("/info/projects/{project_id}/export")
def export_project(project_id: str, user: dict = Depends(get_current_user)):
    data = info_project(project_id, user)
    p = data["project"]
    sections = [
        ("Project", [
            ("Project ID", p["Project_ID"]), ("Name", p.get("Project_Name")), ("Location", p.get("Location")),
            ("Status", p.get("Project_Status")), ("Start", p.get("Start_Date")), ("Expected end", p.get("Expected_End_Date")),
            ("Units on site", len(data["equipment"])),
        ]),
        ("Equipment on this project", {
            "columns": ["ID", "Name", "Type", "Status"],
            "rows": [[x["Equipment_ID"], x["Equipment_Name"], x["Equipment_Type"], x["Current_Status"]] for x in data["equipment"]],
        }),
        ("Planned activities (latest 5)", {
            "columns": ["Activity", "Start", "End", "Intensity"],
            "rows": [[a["Activity_Name"], a["Start_Date"], a["End_Date"], a["Expected_Intensity"]] for a in data["activities"]],
        }),
    ]
    return _pdf(f'Project {p["Project_ID"]}', sections, f'project-{p["Project_ID"]}-{date.today().isoformat()}.pdf')


# ---------------------------------------------------------------------------
# Maintenance history of ONE machine (services + breakdowns + repairs, newest first)
# ---------------------------------------------------------------------------
@router.get("/history/{equipment_id}")
def maintenance_history(
    equipment_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    user: dict = Depends(require_roles("mechanic", "fleet_manager")),
):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            'SELECT e."Equipment_ID", e."Equipment_Name", e."Equipment_Type", e."Current_Status", e."Current_Project_ID" '
            'FROM "EQUIPMENT" e WHERE e."Equipment_ID" = %s;', (equipment_id,))
        equipment = cur.fetchone()
        if equipment is None:
            raise HTTPException(status_code=404, detail="Equipment not found")

        def window(column):
            sql, params = "", []
            if date_from:
                sql += f' AND {column} >= %s'
                params.append(date_from)
            if date_to:
                sql += f' AND {column} <= %s'
                params.append(date_to)
            return sql, params

        s_sql, s_par = window('"Service_Date"')
        b_sql, b_par = window('"Breakdown_Date"')
        r_sql, r_par = window('r."Repair_Date"')

        cur.execute(
            'SELECT "Service_Date" AS date, \'Service\' AS kind, COALESCE("Maintenance_Type", \'Scheduled service\') AS title, '
            '  "Service_Details" AS detail, "Total_Cost" AS cost, NULL::numeric AS hours, "Next_Service_Date" AS next_date '
            f'FROM "MAINTENANCE" WHERE "Equipment_ID" = %s{s_sql} '
            'UNION ALL '
            'SELECT "Breakdown_Date", \'Breakdown\', \'Breakdown - \' || COALESCE("Breakdown_Status", \'\'), '
            '  "Description", NULL::numeric, "Downtime_Hours", NULL::date '
            f'FROM "BREAKDOWN" WHERE "Equipment_ID" = %s{b_sql} '
            'UNION ALL '
            'SELECT r."Repair_Date", \'Repair\', \'Repair for breakdown #\' || r."Breakdown_ID", '
            '  concat_ws(\' | \', NULLIF(r."Parts_Replaced", \'\'), NULLIF(r."Repair_Details", \'\')), '
            '  COALESCE(r."Parts_Cost", 0) + COALESCE(r."Labor_Cost", 0), r."Labor_Hours", NULL::date '
            'FROM "REPAIR" r JOIN "BREAKDOWN" b ON b."Breakdown_ID" = r."Breakdown_ID" '
            f'WHERE b."Equipment_ID" = %s{r_sql} '
            'ORDER BY date DESC, kind LIMIT 1000;',
            [equipment_id, *s_par, equipment_id, *b_par, equipment_id, *r_par],
        )
        events = cur.fetchall()

    summary = {
        "services": sum(1 for e in events if e["kind"] == "Service"),
        "breakdowns": sum(1 for e in events if e["kind"] == "Breakdown"),
        "repairs": sum(1 for e in events if e["kind"] == "Repair"),
        "downtime_hours": float(sum(e["hours"] or 0 for e in events if e["kind"] == "Breakdown")),
        "labour_hours": float(sum(e["hours"] or 0 for e in events if e["kind"] == "Repair")),
        "total_cost": float(sum(e["cost"] or 0 for e in events)),
    }
    return {"equipment": equipment, "summary": summary, "events": events}


# ---------------------------------------------------------------------------
# Fleet Manager: operations + maintenance overview
# ---------------------------------------------------------------------------
@router.get("/overview/operational")
def operational_overview(user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        # Recent windows end at the newest record, not "today" (the data may not be live up to today).
        cur.execute('SELECT MAX("Log_Date") AS d FROM "UTILIZATION_LOG";')
        util_end = cur.fetchone()["d"]
        cur.execute('SELECT MAX("Fuel_Date") AS d FROM "FUEL_LOG";')
        fuel_end = cur.fetchone()["d"]
        util_from = (util_end or date.today()) - timedelta(days=WINDOW_DAYS)
        fuel_from = (fuel_end or date.today()) - timedelta(days=WINDOW_DAYS)

        cur.execute(
            'SELECT p."Project_ID", p."Project_Name", p."Project_Status", '
            '  (SELECT COUNT(*) FROM "EQUIPMENT" e WHERE e."Current_Project_ID" = p."Project_ID") AS units, '
            '  (SELECT COUNT(*) FROM "EQUIPMENT" e WHERE e."Current_Project_ID" = p."Project_ID" '
            '     AND e."Current_Status" ILIKE %s) AS under_repair, '
            '  (SELECT COALESCE(SUM(u."Operating_Hours"), 0) FROM "UTILIZATION_LOG" u '
            '     WHERE u."Project_ID" = p."Project_ID" AND u."Log_Date" > %s) AS util_hours, '
            '  (SELECT COALESCE(SUM(f."Fuel_Consumed"), 0) FROM "FUEL_LOG" f '
            '     JOIN "EQUIPMENT" e ON e."Equipment_ID" = f."Equipment_ID" '
            f'     WHERE f."Project_ID" = p."Project_ID" AND f."Fuel_Date" > %s AND {LIQUID_SQL}) AS fuel_litres, '
            '  (SELECT COALESCE(SUM(f."Fuel_Consumed"), 0) FROM "FUEL_LOG" f '
            '     JOIN "EQUIPMENT" e ON e."Equipment_ID" = f."Equipment_ID" '
            f'     WHERE f."Project_ID" = p."Project_ID" AND f."Fuel_Date" > %s AND {ELECTRIC_SQL}) AS fuel_kwh, '
            '  (SELECT COALESCE(SUM(f."Fuel_Cost"), 0) FROM "FUEL_LOG" f '
            '     WHERE f."Project_ID" = p."Project_ID" AND f."Fuel_Date" > %s) AS fuel_cost, '
            '  (SELECT COUNT(*) FROM "BREAKDOWN" b JOIN "EQUIPMENT" e ON e."Equipment_ID" = b."Equipment_ID" '
            '     WHERE e."Current_Project_ID" = p."Project_ID" AND b."Breakdown_Status" <> \'Resolved\') AS open_breakdowns '
            'FROM "PROJECT" p ORDER BY units DESC, p."Project_ID";',
            ("%repair%", util_from, fuel_from, fuel_from, fuel_from),
        )
        projects = cur.fetchall()
        for p in projects:
            for key in ("util_hours", "fuel_litres", "fuel_kwh", "fuel_cost"):
                p[key] = float(p[key])

        # Maintenance snapshot (decommissioned machines are not "fleet")
        cur.execute(
            'WITH latest AS (SELECT DISTINCT ON (m."Equipment_ID") m."Equipment_ID", m."Next_Service_Date" '
            '  FROM "MAINTENANCE" m JOIN "EQUIPMENT" e ON e."Equipment_ID" = m."Equipment_ID" '
            '  WHERE e."Current_Status" NOT ILIKE %s '
            '  ORDER BY m."Equipment_ID", m."Service_Date" DESC, m."Maintenance_ID" DESC) '
            'SELECT COUNT(*) FILTER (WHERE "Next_Service_Date" < CURRENT_DATE) AS overdue, '
            '       COUNT(*) FILTER (WHERE "Next_Service_Date" >= CURRENT_DATE AND "Next_Service_Date" <= CURRENT_DATE + %s) AS due_soon '
            'FROM latest;',
            ("%decommission%", SERVICE_WARNING_DAYS),
        )
        service = cur.fetchone()
        cur.execute(
            'SELECT COUNT(*) AS open_n, MIN("Breakdown_Date") AS oldest, '
            '       COUNT(*) FILTER (WHERE "Breakdown_Status" = \'Under Repair\') AS repair_n '
            'FROM "BREAKDOWN" WHERE "Breakdown_Status" <> \'Resolved\';')
        brk = cur.fetchone()
        cur.execute('SELECT MAX("Service_Date") AS d FROM "MAINTENANCE";')
        m_end = cur.fetchone()["d"]
        cur.execute(
            'SELECT COALESCE(SUM("Total_Cost"), 0) AS cost FROM "MAINTENANCE" WHERE "Service_Date" > %s;',
            ((m_end or date.today()) - timedelta(days=90),))
        service_cost = float(cur.fetchone()["cost"])
        cur.execute(
            'SELECT COALESCE(SUM(COALESCE("Parts_Cost", 0) + COALESCE("Labor_Cost", 0)), 0) AS cost FROM "REPAIR" WHERE "Repair_Date" > %s;',
            ((m_end or date.today()) - timedelta(days=90),))
        repair_cost = float(cur.fetchone()["cost"])

    return {
        "windows": {"days": WINDOW_DAYS, "usage_to": util_end, "fuel_to": fuel_end, "cost_days": 90, "cost_to": m_end},
        "projects": projects,
        "maintenance": {
            "services_overdue": service["overdue"], "services_due_soon": service["due_soon"],
            "due_soon_days": SERVICE_WARNING_DAYS,
            "breakdowns_unresolved": brk["open_n"],
            "breakdowns_under_repair": brk["repair_n"],
            "oldest_unresolved_date": brk["oldest"],
            "oldest_unresolved_days": max((date.today() - brk["oldest"]).days, 0) if brk["oldest"] else 0,
            "service_cost_90d": service_cost, "repair_cost_90d": repair_cost,
        },
    }
