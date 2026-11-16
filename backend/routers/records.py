"""
Records API - the "see / filter / download data" side of every register.

Why this file exists
--------------------
The register pages (Fuel Logs, Incidents, ...) used to load EVERY row into the browser
(4,514 fuel rows!) which made typing and clicking slow. Now:
  * a register page only asks for its latest 10 entries, and
  * the Records page asks the database for ONE page (25 rows) at a time, already filtered.

Endpoints (all need a signed-in user; they only READ data, nothing is changed here)
  GET /records/{key}             one page of rows   (?q= &equipment_id= &project_id= &date_from= &date_to= &page= &page_size=)
  GET /records/{key}/export      same filters, whole result as a file  (?format=csv|pdf)   (&all=1 ignores the filters)
  GET /records/equipment/next-id next free Equipment_ID, e.g. "EQ-043"
  GET /records/equipment/choices existing Types / Fuel Types / Statuses, for dropdown suggestions
  GET /records-meta              list of the available record types (for the Reports page)

{key} is one of: equipment, fuel-logs, utilization-logs, incidents, maintenance,
breakdowns, repairs, transfers   (see REGISTRY below).

Search: type anything - "eq7", "EQ-007", "dozer", "prj 3", "2026-01". Capital letters,
dashes and spaces don't matter, and every word you type must be found somewhere in the row
(equipment ID, equipment name, type, project, date, description ...).
"""

import csv
import io
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from psycopg.rows import dict_row

from database import get_connection
from security import get_current_user
from fuel_units import unit_label

router = APIRouter(tags=["Records"])

# ---------------------------------------------------------------------------
# What each record type is. Only table/column NAMES from this trusted list are ever put into
# SQL text - whatever the user types always goes in as a bound parameter.
#   equip   : SQL expression giving the row's equipment id
#   projects: SQL expressions that hold a project id (used by the project filter)
#   join    : extra JOIN needed to reach the equipment (repairs only know their breakdown)
# ---------------------------------------------------------------------------
REGISTRY = {
    "equipment": {
        "label": "Equipment", "table": "EQUIPMENT", "pk": "Equipment_ID", "date": None,
        "equip": 't."Equipment_ID"', "projects": ['t."Current_Project_ID"'], "join": "", "add_name": False,
    },
    "fuel-logs": {
        "label": "Fuel Logs", "table": "FUEL_LOG", "pk": "Fuel_Log_ID", "date": "Fuel_Date",
        "equip": 't."Equipment_ID"', "projects": ['t."Project_ID"'], "join": "", "add_name": True,
    },
    "utilization-logs": {
        "label": "Utilization Logs", "table": "UTILIZATION_LOG", "pk": "Utilization_ID", "date": "Log_Date",
        "equip": 't."Equipment_ID"', "projects": ['t."Project_ID"'], "join": "", "add_name": True,
    },
    "incidents": {
        "label": "Incidents", "table": "INCIDENT", "pk": "Incident_ID", "date": "Incident_Date",
        "equip": 't."Equipment_ID"', "projects": ['t."Project_ID"'], "join": "", "add_name": True,
    },
    "maintenance": {
        "label": "Maintenance", "table": "MAINTENANCE", "pk": "Maintenance_ID", "date": "Service_Date",
        "equip": 't."Equipment_ID"', "projects": ['e."Current_Project_ID"'], "join": "", "add_name": True,
    },
    "breakdowns": {
        "label": "Breakdowns", "table": "BREAKDOWN", "pk": "Breakdown_ID", "date": "Breakdown_Date",
        "equip": 't."Equipment_ID"', "projects": ['e."Current_Project_ID"'], "join": "", "add_name": True,
    },
    "repairs": {
        "label": "Repairs", "table": "REPAIR", "pk": "Repair_ID", "date": "Repair_Date",
        "equip": 'b."Equipment_ID"', "projects": ['e."Current_Project_ID"'],
        "join": 'LEFT JOIN "BREAKDOWN" b ON b."Breakdown_ID" = t."Breakdown_ID"', "add_name": True,
    },
    "transfers": {
        "label": "Transfers", "table": "TRANSFER", "pk": "Transfer_ID", "date": "Request_Date",
        "equip": 't."Equipment_ID"', "projects": ['t."From_Project_ID"', 't."To_Project_ID"'], "join": "", "add_name": True,
    },
}

# Column titles for downloads where the plain column name is not enough (fuel cost is in Saudi riyals).
HEADER_LABELS = {
    "fuel-logs": {"Fuel_Cost": "Fuel Cost (SAR)"},
}

EXPORT_PDF_MAX_ROWS = 2000  # a PDF with more rows is unreadable - CSV is the right tool for "everything"


def get_entity(key: str) -> dict:
    entity = REGISTRY.get(key)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Unknown record type '{key}'.")
    return entity


# ---------------------------------------------------------------------------
# Search matching
# ---------------------------------------------------------------------------
def _strip_zeros(text: str) -> str:
    """'eq-007' -> 'eq-7'  (so people can type EQ-7, EQ-07 or EQ-007)."""
    return re.sub(r"(^|[^0-9])0+([0-9])", r"\1\2", text)


def _squash(text: str) -> str:
    """lower-case, keep only letters and digits (commas separate columns in the row text, so
    what you type can never match across two different columns)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


# The same two clean-ups, done inside PostgreSQL on the row text.
_SQL_RAW = "regexp_replace(lower({x}), '[^a-z0-9,]', '', 'g')"
_SQL_ZEROFREE = (
    "regexp_replace(regexp_replace(lower({x}), '(^|[^0-9])0+([0-9])', '\\1\\2', 'g'), '[^a-z0-9,]', '', 'g')"
)


def build_where(entity: dict, q, equipment_id, project_id, date_from, date_to):
    """Return (sql_after_WHERE, params) for the given filters."""
    clauses, params = [], []

    if equipment_id:
        clauses.append(f'{entity["equip"]} = %s')
        params.append(equipment_id)

    if project_id:
        ors = " OR ".join(f"{expr} = %s" for expr in entity["projects"])
        clauses.append(f"({ors})")
        params.extend([project_id] * len(entity["projects"]))

    if entity["date"]:
        if date_from:
            clauses.append(f't."{entity["date"]}" >= %s')
            params.append(date_from)
        if date_to:
            clauses.append(f't."{entity["date"]}" <= %s')
            params.append(date_to)

    # Free-text search. "haystack" = the whole row as text + equipment name/type + project.
    if q and q.strip():
        raw_expr, zero_expr = "h.raw", "h.zf"  # computed once per row in from_clause()
        for word in q.split():
            squashed = _squash(word)
            if not squashed:
                continue
            if re.search(r"[a-z]", squashed):
                # contains letters ("eq7", "dozer"): compare without leading zeros
                clauses.append(f"{zero_expr} LIKE %s")
                params.append(f"%{_squash(_strip_zeros(word.lower()))}%")
            else:
                # numbers only ("007", "2026"): compare exactly as typed
                clauses.append(f"{raw_expr} LIKE %s")
                params.append(f"%{squashed}%")

    return (" AND ".join(clauses) if clauses else "TRUE"), params


def from_clause(entity: dict, searching: bool = False) -> str:
    """FROM + JOINs. e = the row's equipment, p = that equipment's current project.
    When searching, h.raw / h.zf hold the row's searchable text (cleaned up once per row)."""
    if entity["table"] == "EQUIPMENT":
        base = 'FROM "EQUIPMENT" t LEFT JOIN "EQUIPMENT" e ON e."Equipment_ID" = t."Equipment_ID"'
    else:
        base = f'FROM "{entity["table"]}" t {entity["join"]} LEFT JOIN "EQUIPMENT" e ON e."Equipment_ID" = {entity["equip"]}'
    base += ' LEFT JOIN "PROJECT" p ON p."Project_ID" = e."Current_Project_ID"'
    if entity["table"] == "FUEL_LOG":
        # the project the fuel was logged at (not the machine's project today)
        base += ' LEFT JOIN "PROJECT" pj ON pj."Project_ID" = t."Project_ID"'
    if searching:
        hay = "concat_ws(',', t::text, e.\"Equipment_Name\", e.\"Equipment_Type\", p.\"Project_Name\")"
        base += (
            " CROSS JOIN LATERAL (SELECT " + _SQL_RAW.format(x="s.x") + " AS raw, "
            + _SQL_ZEROFREE.format(x="s.x") + " AS zf FROM (SELECT " + hay + " AS x) s) h"
        )
    return base


def select_list(entity: dict) -> str:
    extra = ', e."Equipment_Name" AS "Equipment_Name"' if entity["add_name"] else ""
    if entity["table"] == "FUEL_LOG":
        # Project_Name and the machine's fuel type (turned into a Unit by shape_rows below)
        extra += ', pj."Project_Name" AS "Project_Name", e."Fuel_Type" AS "_fuel_type"'
    return f"t.*{extra}"


def shape_rows(entity: dict, rows: list) -> list:
    """Fuel logs: put Project_Name right after Project_ID and a Unit (litres / kWh) right after Fuel_Consumed.
    The unit is not stored; it follows from the machine's fuel type (see fuel_units.py)."""
    if entity["table"] != "FUEL_LOG":
        return rows
    shaped = []
    for row in rows:
        new = {}
        for name, value in row.items():
            if name in ("Project_Name", "_fuel_type"):
                continue
            new[name] = value
            if name == "Project_ID":
                new["Project_Name"] = row.get("Project_Name")
            if name == "Fuel_Consumed":
                new["Fuel_Unit"] = unit_label(row.get("_fuel_type"))
        shaped.append(new)
    return shaped


# ---------------------------------------------------------------------------
# Next Equipment_ID + dropdown values   (declared BEFORE /records/{key} on purpose)
# ---------------------------------------------------------------------------
def next_equipment_id(cursor) -> str:
    """Look at the existing IDs (EQ-001, EQ-022 ...) and return the next one, same style."""
    cursor.execute('SELECT "Equipment_ID" FROM "EQUIPMENT";')
    best = None  # (number, prefix, width)
    for row in cursor.fetchall():
        m = re.match(r"^(\D*)(\d+)$", row["Equipment_ID"] or "")
        if m and (best is None or int(m.group(2)) > best[0]):
            best = (int(m.group(2)), m.group(1), len(m.group(2)))
    if best is None:
        return "EQ-001"
    number, prefix, width = best
    return f"{prefix}{str(number + 1).zfill(width)}"


@router.get("/records/equipment/next-id")
def get_next_equipment_id(user: dict = Depends(get_current_user)):
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        return {"next_id": next_equipment_id(cur)}


@router.get("/records/equipment/choices")
def get_equipment_choices(user: dict = Depends(get_current_user)):
    """Values already used in the equipment table, so the form can suggest them (and stay consistent)."""
    wanted = ["Equipment_Type", "Fuel_Type", "Current_Status", "Manufacturer"]
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'EQUIPMENT';"
        )
        existing = {r["column_name"] for r in cur.fetchall()}
        result = {}
        for col in wanted:
            if col not in existing:
                continue
            cur.execute(
                f'SELECT DISTINCT "{col}" AS v FROM "EQUIPMENT" WHERE "{col}" IS NOT NULL AND "{col}" <> \'\' ORDER BY 1;'
            )
            result[col] = [r["v"] for r in cur.fetchall()]

        # Fuel types that have a price in Fuel Rates, plus any type that only has a price (so it can be suggested too).
        cur.execute('SELECT DISTINCT "Fuel_Type" AS v FROM "FUEL_RATE" WHERE "Fuel_Type" IS NOT NULL ORDER BY 1;')
        priced = [r["v"] for r in cur.fetchall()]
        result["Fuel_Type_Priced"] = priced
        have = {v.lower() for v in result.get("Fuel_Type", [])}
        result["Fuel_Type"] = result.get("Fuel_Type", []) + [v for v in priced if v.lower() not in have]
        return result


@router.get("/records-meta")
def records_meta(user: dict = Depends(get_current_user)):
    return [{"key": k, "label": v["label"]} for k, v in REGISTRY.items()]


# ---------------------------------------------------------------------------
# One page of rows
# ---------------------------------------------------------------------------
@router.get("/records/{key}")
def list_records(
    key: str,
    q: str | None = None,
    equipment_id: str | None = None,
    project_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    entity = get_entity(key)
    where, params = build_where(entity, q, equipment_id, project_id, date_from, date_to)
    source = from_clause(entity, bool(q and q.strip()))

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS n {source} WHERE {where};", params or None)
        total = cur.fetchone()["n"]
        cur.execute(
            f'SELECT {select_list(entity)} {source} WHERE {where} '
            f'ORDER BY t."{entity["pk"]}" DESC LIMIT %s OFFSET %s;',
            params + [page_size, (page - 1) * page_size],
        )
        rows = shape_rows(entity, cur.fetchall())

    return {
        "key": key, "label": entity["label"], "pk": entity["pk"], "has_date": bool(entity["date"]),
        "total": total, "page": page, "page_size": page_size, "rows": rows,
    }


# ---------------------------------------------------------------------------
# Download (CSV for any size, PDF for readable sizes)
# ---------------------------------------------------------------------------
@router.get("/records/{key}/export")
def export_records(
    key: str,
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    all: bool = False,
    q: str | None = None,
    equipment_id: str | None = None,
    project_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: dict = Depends(get_current_user),
):
    entity = get_entity(key)
    if all:  # "download everything": ignore every filter
        q = equipment_id = project_id = date_from = date_to = None
    where, params = build_where(entity, q, equipment_id, project_id, date_from, date_to)
    source = from_clause(entity, bool(q and q.strip()))
    limit_sql = f" LIMIT {EXPORT_PDF_MAX_ROWS + 1}" if format == "pdf" else ""

    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f'SELECT {select_list(entity)} {source} WHERE {where} ORDER BY t."{entity["pk"]}" DESC{limit_sql};',
            params or None,
        )
        rows = shape_rows(entity, cur.fetchall())

    columns = list(rows[0].keys()) if rows else [entity["pk"]]
    titles = HEADER_LABELS.get(key, {})
    today = date.today().isoformat()
    filename = f'{key}-{today}'

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([titles.get(c, c) for c in columns])
        for row in rows:
            writer.writerow(["" if row[c] is None else row[c] for c in columns])
        # utf-8 with BOM so Excel shows Arabic/special characters correctly
        data = ("﻿" + buffer.getvalue()).encode("utf-8")
        return Response(
            content=data, media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    return pdf_response(entity, rows, columns, filename, all, q, equipment_id, project_id, date_from, date_to, titles)


def pdf_response(entity, rows, columns, filename, all_rows, q, equipment_id, project_id, date_from, date_to, titles=None):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF needs one extra package. Run: pip install reportlab")

    truncated = len(rows) > EXPORT_PDF_MAX_ROWS
    rows = rows[:EXPORT_PDF_MAX_ROWS]

    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7, leading=8.5)
    head = styles["BodyText"].clone("head", fontSize=7, leading=8.5, textColor=colors.white, fontName="Helvetica-Bold")

    filters = []
    if all_rows:
        filters.append("all data")
    else:
        if q: filters.append(f"search '{q}'")
        if equipment_id: filters.append(f"equipment {equipment_id}")
        if project_id: filters.append(f"project {project_id}")
        if date_from: filters.append(f"from {date_from}")
        if date_to: filters.append(f"to {date_to}")
    summary = ", ".join(filters) if filters else "no filters"

    story = [
        Paragraph(f'Next-Gen Equipment Management System: {entity["label"]}', styles["Title"]),
        Paragraph(f"Generated {date.today().isoformat()} | Filters: {summary} | {len(rows)} row(s)", styles["BodyText"]),
    ]
    if truncated:
        story.append(Paragraph(
            f"<b>Only the latest {EXPORT_PDF_MAX_ROWS} rows are shown.</b> Narrow the filters or download the CSV for everything.",
            styles["BodyText"]))
    story.append(Spacer(1, 8))

    titles = titles or {}
    table_data = [[Paragraph(titles.get(c, c.replace("_", " ")), head) for c in columns]]
    for row in rows:
        table_data.append([Paragraph("" if row[c] is None else str(row[c])[:200], small) for c in columns])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f9488")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24).build(story)
    return Response(
        content=buffer.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


# ---------------------------------------------------------------------------
# Attach the lookup / history / overview endpoints (insights.py) to this router, so main.py
# only ever needs the single `include_router(records.router)` line.
# ---------------------------------------------------------------------------
try:
    from routers.insights import router as insights_router  # normal project layout (backend/routers/)
except ImportError:  # flat layout, used only by my test setup
    from insights import router as insights_router
router.include_router(insights_router)
