"""
Equipment transfers: request -> Fleet Manager approval -> equipment moves to the new project.

WHO CAN DO WHAT (taken from the signed-in user's token - nobody types a name any more)
  Site Engineer  : POST /transfers/request        raise a request (Requested_By = me, status Pending)
                   POST /transfers/{id}/cancel    withdraw MY request while it is still Pending
                   GET  /transfers/queue          see MY requests (all / pending / approved / rejected)
                   GET  /transfers/request-options   equipment + projects for the request form
  Fleet Manager  : GET  /transfers/queue          see ALL requests
                   GET  /transfers/{id}/context   everything needed to judge a request
                   POST /transfers/{id}/approve   approve (Approved_By = me)
                   POST /transfers/{id}/reject    reject with a required reason (Approved_By = me)
                   + the older admin routes: GET /, GET /{id}, POST /, PUT /{id}, DELETE /{id}

Safeguards kept from earlier versions:
  * From project always = where the equipment actually is right now (never trusted from the browser)
  * To project must differ from From project
  * only ONE Pending request per equipment
  * nobody approves their own request
  * stale request (equipment moved since it was raised) cannot be approved - reject and re-raise
  * approving + moving the equipment happen in ONE database transaction
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.errors import CheckViolation, ForeignKeyViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from database import get_connection
from security import get_current_user, require_roles

router = APIRouter(prefix="/transfers", tags=["Transfers"])

# Equipment in these states can't be moved. (Matched loosely so it works with your real status names.)
UNMOVABLE_WORDS = ("decommission", "retired", "scrapped", "disposed")

# Tabs on the queue -> which Transfer_Status values they cover.
TAB_STATUSES = {
    "Pending": ["Pending"],
    "Approved": ["Approved", "Completed"],
    "Rejected": ["Rejected"],
    "Cancelled": ["Cancelled"],
}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class TransferRequestBody(BaseModel):
    """What a Site Engineer sends. Everything else (From, who, when, status) is filled in by the server."""
    Equipment_ID: str
    To_Project_ID: str
    Transfer_Notes: str | None = Field(default=None, max_length=255)


class RejectBody(BaseModel):
    Rejection_Reason: str = Field(min_length=1, max_length=255)


class TransferCreate(BaseModel):
    """Used only by the older admin create/update routes (Fleet Manager)."""
    Equipment_ID: str
    From_Project_ID: str
    To_Project_ID: str
    Requested_By: str
    Approved_By: str | None = None
    Request_Date: date
    Effective_Transfer_Date: date | None = None
    Transfer_Status: str
    Rejection_Reason: str | None = None
    Transfer_Notes: str | None = None


def is_unmovable(status: str | None) -> bool:
    text = (status or "").lower()
    return any(word in text for word in UNMOVABLE_WORDS)


# ---------------------------------------------------------------------------
# Shared SQL: one transfer row with all the friendly names joined in
# ---------------------------------------------------------------------------
QUEUE_SELECT = """
SELECT t."Transfer_ID", t."Equipment_ID", t."From_Project_ID", t."To_Project_ID",
       t."Requested_By", t."Approved_By", t."Request_Date", t."Effective_Transfer_Date",
       t."Transfer_Status", t."Rejection_Reason", t."Transfer_Notes",
       e."Equipment_Name", e."Equipment_Type", e."Current_Status" AS "Equipment_Status",
       e."Current_Project_ID",
       pf."Project_Name" AS "From_Project_Name", pt."Project_Name" AS "To_Project_Name",
       req."Employee_Name" AS "Requested_By_Name", dec."Employee_Name" AS "Approved_By_Name",
       (t."Transfer_Status" = 'Pending' AND e."Current_Project_ID" IS DISTINCT FROM t."From_Project_ID") AS "Is_Stale"
FROM "TRANSFER" t
JOIN "EQUIPMENT" e ON e."Equipment_ID" = t."Equipment_ID"
LEFT JOIN "PROJECT" pf ON pf."Project_ID" = t."From_Project_ID"
LEFT JOIN "PROJECT" pt ON pt."Project_ID" = t."To_Project_ID"
LEFT JOIN "EMPLOYEE" req ON req."Employee_ID" = t."Requested_By"
LEFT JOIN "EMPLOYEE" dec ON dec."Employee_ID" = t."Approved_By"
"""


# NOTE: fixed-path routes (/queue, /request-options, /request, /pending) are declared BEFORE
# "/{transfer_id}" so FastAPI doesn't try to read "queue" as a transfer id.

# ---------------------------------------------------------------------------
# Queue (Site Engineer: my requests / Fleet Manager: everything)
# ---------------------------------------------------------------------------
@router.get("/queue")
def get_queue(
    status: str = Query("All", pattern="^(All|Pending|Approved|Rejected|Cancelled)$"),
    limit: int = Query(100, ge=1, le=500),
    user: dict = Depends(require_roles("site_engineer", "fleet_manager")),
):
    mine_only = user["Role"] == "site_engineer"
    owner_sql = ' WHERE t."Requested_By" = %s' if mine_only else ""
    owner_params = [user["Employee_ID"]] if mine_only else []

    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        # numbers on the tabs
        cursor.execute(
            f'SELECT t."Transfer_Status" AS s, COUNT(*) AS n FROM "TRANSFER" t{owner_sql} GROUP BY 1;',
            owner_params or None,
        )
        by_status = {r["s"]: r["n"] for r in cursor.fetchall()}
        counts = {"All": sum(by_status.values())}
        for tab, statuses in TAB_STATUSES.items():
            counts[tab] = sum(by_status.get(s, 0) for s in statuses)

        where, params = [], list(owner_params)
        if mine_only:
            where.append('t."Requested_By" = %s')
        if status != "All":
            where.append('t."Transfer_Status" = ANY(%s)')
            params.append(TAB_STATUSES[status])
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        cursor.execute(
            f'{QUEUE_SELECT}{where_sql} ORDER BY t."Request_Date" DESC, t."Transfer_ID" DESC LIMIT %s;',
            params + [limit],
        )
        return {"counts": counts, "rows": cursor.fetchall(), "scope": "mine" if mine_only else "all"}


# ---------------------------------------------------------------------------
# Request form helpers + creating a request
# ---------------------------------------------------------------------------
@router.get("/request-options")
def request_options(user: dict = Depends(require_roles("site_engineer"))):
    """Equipment (with 'can it be requested right now, and if not why') and projects for the form."""
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            'SELECT e."Equipment_ID", e."Equipment_Name", e."Equipment_Type", e."Current_Status", '
            '       e."Current_Project_ID", p."Project_Name" AS "Current_Project_Name", '
            '       (SELECT MIN(t."Transfer_ID") FROM "TRANSFER" t '
            '         WHERE t."Equipment_ID" = e."Equipment_ID" AND t."Transfer_Status" = \'Pending\') AS "Pending_Transfer_ID" '
            'FROM "EQUIPMENT" e LEFT JOIN "PROJECT" p ON p."Project_ID" = e."Current_Project_ID" '
            'ORDER BY e."Equipment_ID";'
        )
        equipment = cursor.fetchall()
        for e in equipment:
            if is_unmovable(e["Current_Status"]):
                e["Block_Reason"] = f'{e["Current_Status"]} equipment cannot be transferred'
            elif e["Current_Project_ID"] is None:
                e["Block_Reason"] = "no current project assigned"
            elif e["Pending_Transfer_ID"] is not None:
                e["Block_Reason"] = f'already has a pending request (#{e["Pending_Transfer_ID"]})'
            else:
                e["Block_Reason"] = None

        cursor.execute('SELECT "Project_ID", "Project_Name", "Location", "Project_Status" FROM "PROJECT" ORDER BY "Project_ID";')
        return {"equipment": equipment, "projects": cursor.fetchall(), "requester": user["Employee_Name"]}


@router.post("/request", status_code=201)
def create_request(body: TransferRequestBody, user: dict = Depends(require_roles("site_engineer"))):
    notes = (body.Transfer_Notes or "").strip() or None
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        try:
            # Lock the equipment row: two engineers requesting the same machine at the same moment
            # are handled one after the other, so the "one pending request" rule can't be dodged.
            cursor.execute(
                'SELECT "Current_Project_ID", "Current_Status" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s FOR UPDATE;',
                (body.Equipment_ID,),
            )
            equipment = cursor.fetchone()
            if equipment is None:
                raise HTTPException(status_code=400, detail="Unknown equipment.")
            if is_unmovable(equipment["Current_Status"]):
                raise HTTPException(status_code=400, detail=f'{equipment["Current_Status"]} equipment cannot be transferred.')
            if equipment["Current_Project_ID"] is None:
                raise HTTPException(status_code=400, detail="This equipment has no current project, so it can't be transferred. Assign it a project first.")
            cursor.execute('SELECT 1 FROM "PROJECT" WHERE "Project_ID" = %s;', (body.To_Project_ID,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=400, detail="Unknown project.")
            if body.To_Project_ID == equipment["Current_Project_ID"]:
                raise HTTPException(status_code=400, detail="The equipment is already on that project. Choose a different To Project.")

            cursor.execute(
                'SELECT "Transfer_ID" FROM "TRANSFER" WHERE "Equipment_ID" = %s AND "Transfer_Status" = \'Pending\';',
                (body.Equipment_ID,),
            )
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"{body.Equipment_ID} already has a pending transfer request (#{existing['Transfer_ID']}). Wait for the decision first.",
                )

            cursor.execute(
                'INSERT INTO "TRANSFER" ("Equipment_ID", "From_Project_ID", "To_Project_ID", "Requested_By", '
                '"Request_Date", "Transfer_Status", "Transfer_Notes") '
                "VALUES (%s, %s, %s, %s, CURRENT_DATE, 'Pending', %s) RETURNING *;",
                (body.Equipment_ID, equipment["Current_Project_ID"], body.To_Project_ID, user["Employee_ID"], notes),
            )
            return cursor.fetchone()
        except ForeignKeyViolation:
            connection.rollback()
            raise HTTPException(status_code=400, detail="Unknown project.")


# ---------------------------------------------------------------------------
# Fleet Manager: decision context
# ---------------------------------------------------------------------------
@router.get("/{transfer_id}/context")
def get_context(transfer_id: int, user: dict = Depends(require_roles("fleet_manager"))):
    """Everything a Fleet Manager needs to judge one request, in one call."""
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(f'{QUEUE_SELECT} WHERE t."Transfer_ID" = %s;', (transfer_id,))
        transfer = cursor.fetchone()
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer not found")
        eq_id = transfer["Equipment_ID"]

        cursor.execute(
            'SELECT "Equipment_ID", "Equipment_Name", "Equipment_Type", "Manufacturer", "Model", "Manufacturing_Year", '
            '"Current_Status", "Current_Project_ID" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (eq_id,))
        equipment = cursor.fetchone()
        year = equipment.get("Manufacturing_Year")
        equipment["Age_Years"] = (date.today().year - year) if year else None

        # Breakdowns
        cursor.execute(
            'SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE "Breakdown_Status" <> \'Resolved\') AS open_now, '
            'COALESCE(SUM("Downtime_Hours"), 0) AS downtime, MAX("Breakdown_Date") AS last_date '
            'FROM "BREAKDOWN" WHERE "Equipment_ID" = %s;', (eq_id,))
        b = cursor.fetchone()

        # Servicing
        cursor.execute(
            'SELECT MAX("Service_Date") AS last_service FROM "MAINTENANCE" WHERE "Equipment_ID" = %s;', (eq_id,))
        last_service = cursor.fetchone()["last_service"]
        cursor.execute(
            'SELECT "Next_Service_Date" FROM "MAINTENANCE" WHERE "Equipment_ID" = %s AND "Next_Service_Date" IS NOT NULL '
            'ORDER BY "Service_Date" DESC, "Maintenance_ID" DESC LIMIT 1;', (eq_id,))
        nxt = cursor.fetchone()
        next_service = nxt["Next_Service_Date"] if nxt else None
        overdue = (date.today() - next_service).days if next_service and next_service < date.today() else 0

        # Utilization: the 30 days up to the machine's latest log (data may not be "today")
        cursor.execute(
            'SELECT MAX("Log_Date") AS last_log, COALESCE(SUM("Operating_Hours"), 0) AS hours, COUNT(*) AS days '
            'FROM "UTILIZATION_LOG" WHERE "Equipment_ID" = %s AND "Log_Date" > '
            '(SELECT COALESCE(MAX("Log_Date"), CURRENT_DATE) - 30 FROM "UTILIZATION_LOG" WHERE "Equipment_ID" = %s);',
            (eq_id, eq_id))
        u = cursor.fetchone()

        # The two projects
        def project(pid):
            if pid is None:
                return None
            cursor.execute('SELECT "Project_ID", "Project_Name", "Location", "Project_Status" FROM "PROJECT" WHERE "Project_ID" = %s;', (pid,))
            p = cursor.fetchone()
            if p:
                cursor.execute('SELECT COUNT(*) AS n FROM "EQUIPMENT" WHERE "Current_Project_ID" = %s;', (pid,))
                p["Units_On_Site"] = cursor.fetchone()["n"]
            return p

        to_project = project(transfer["To_Project_ID"])
        if to_project:
            cursor.execute(
                'SELECT "Activity_Name", "Start_Date", "End_Date", "Expected_Intensity" FROM "PROJECT_ACTIVITY" '
                'WHERE "Project_ID" = %s ORDER BY "Start_Date" DESC LIMIT 3;', (transfer["To_Project_ID"],))
            to_project["Activities"] = cursor.fetchall()

        # Plain-language heads-ups, most important first
        flags = []
        if transfer["Is_Stale"]:
            flags.append(f'Out of date: the equipment is now on {equipment["Current_Project_ID"]}, not {transfer["From_Project_ID"]}. It cannot be approved - reject it and ask for a new request.')
        if b["open_now"]:
            flags.append(f'{b["open_now"]} unresolved breakdown(s) on this equipment.')
        if is_unmovable(equipment["Current_Status"]):
            flags.append(f'Equipment status is {equipment["Current_Status"]}.')
        elif "repair" in (equipment["Current_Status"] or "").lower():
            flags.append(f'Equipment status is {equipment["Current_Status"]} - it is not working right now.')
        if overdue > 0:
            flags.append(f"Service overdue by {overdue} days.")
        if transfer["Transfer_Status"] == "Pending" and not transfer["Transfer_Notes"]:
            flags.append("The requester gave no reason.")

        return {
            "transfer": transfer,
            "equipment": equipment,
            "health": {
                "breakdowns_total": b["total"], "breakdowns_open": b["open_now"],
                "downtime_hours": float(b["downtime"]), "last_breakdown": b["last_date"],
                "last_service": last_service, "next_service": next_service, "service_overdue_days": overdue,
                "util_hours_30d": float(u["hours"]), "util_days_30d": u["days"], "last_log": u["last_log"],
            },
            "from_project": project(transfer["From_Project_ID"]),
            "to_project": to_project,
            "flags": flags,
        }


# ---------------------------------------------------------------------------
# Fleet Manager: approve / reject
# ---------------------------------------------------------------------------
@router.post("/{transfer_id}/approve")
def approve_transfer(transfer_id: int, user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        # FOR UPDATE locks the row so two managers clicking at once can't both approve it.
        cursor.execute('SELECT * FROM "TRANSFER" WHERE "Transfer_ID" = %s FOR UPDATE;', (transfer_id,))
        transfer = cursor.fetchone()
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer not found")
        if transfer["Transfer_Status"] != "Pending":
            raise HTTPException(status_code=409, detail=f"This request is already {transfer['Transfer_Status']} - only Pending requests can be approved.")
        # Segregation of duties: the person who raised a request can't approve it.
        if user["Employee_ID"] == transfer["Requested_By"]:
            raise HTTPException(status_code=400, detail="A request cannot be approved by the person who requested it.")

        cursor.execute('SELECT "Current_Project_ID" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s FOR UPDATE;', (transfer["Equipment_ID"],))
        equipment = cursor.fetchone()
        if equipment["Current_Project_ID"] != transfer["From_Project_ID"]:
            raise HTTPException(
                status_code=409,
                detail=f"This request is out of date: the equipment is now on {equipment['Current_Project_ID']}, "
                       f"not {transfer['From_Project_ID']}. Reject it and ask for a new request.",
            )

        # GREATEST(...) keeps the effective date from falling before the request date.
        cursor.execute(
            'UPDATE "TRANSFER" SET "Transfer_Status" = \'Approved\', "Approved_By" = %s, "Rejection_Reason" = NULL, '
            '"Effective_Transfer_Date" = GREATEST(CURRENT_DATE, "Request_Date") WHERE "Transfer_ID" = %s RETURNING *;',
            (user["Employee_ID"], transfer_id),
        )
        approved = cursor.fetchone()
        cursor.execute('UPDATE "EQUIPMENT" SET "Current_Project_ID" = %s WHERE "Equipment_ID" = %s;',
                       (transfer["To_Project_ID"], transfer["Equipment_ID"]))
        return approved


@router.post("/{transfer_id}/cancel")
def cancel_transfer(transfer_id: int, user: dict = Depends(require_roles("site_engineer"))):
    """The engineer who raised a request can withdraw it while it is still Pending (wrong machine, plans changed).
    The row is kept with status 'Cancelled' (history is never deleted) and the machine can be requested again."""
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            'SELECT "Transfer_Status", "Requested_By" FROM "TRANSFER" WHERE "Transfer_ID" = %s FOR UPDATE;',
            (transfer_id,),
        )
        transfer = cursor.fetchone()
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer not found")
        if transfer["Requested_By"] != user["Employee_ID"]:
            raise HTTPException(status_code=403, detail="You can only cancel your own requests.")
        if transfer["Transfer_Status"] != "Pending":
            raise HTTPException(
                status_code=409,
                detail=f"This request is already {transfer['Transfer_Status']} - only Pending requests can be cancelled.",
            )
        cursor.execute(
            'UPDATE "TRANSFER" SET "Transfer_Status" = \'Cancelled\' WHERE "Transfer_ID" = %s RETURNING *;',
            (transfer_id,),
        )
        return cursor.fetchone()


@router.post("/{transfer_id}/reject")
def reject_transfer(transfer_id: int, body: RejectBody, user: dict = Depends(require_roles("fleet_manager"))):
    reason = body.Rejection_Reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A rejection reason is required.")
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute('SELECT "Transfer_Status" FROM "TRANSFER" WHERE "Transfer_ID" = %s FOR UPDATE;', (transfer_id,))
        transfer = cursor.fetchone()
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer not found")
        if transfer["Transfer_Status"] != "Pending":
            raise HTTPException(status_code=409, detail=f"This request is already {transfer['Transfer_Status']} - only Pending requests can be rejected.")
        cursor.execute(
            'UPDATE "TRANSFER" SET "Transfer_Status" = \'Rejected\', "Approved_By" = %s, "Rejection_Reason" = %s '
            'WHERE "Transfer_ID" = %s RETURNING *;',
            (user["Employee_ID"], reason, transfer_id),
        )
        return cursor.fetchone()


# ---------------------------------------------------------------------------
# Older admin routes (Fleet Manager only now, so nobody can skip the approval workflow)
# ---------------------------------------------------------------------------
@router.get("/")
def get_transfer_list(user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute('SELECT * FROM "TRANSFER" ORDER BY "Transfer_ID";')
        return cursor.fetchall()


@router.get("/{transfer_id}")
def get_transfer(transfer_id: int, user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute('SELECT * FROM "TRANSFER" WHERE "Transfer_ID" = %s;', (transfer_id,))
        transfer = cursor.fetchone()
        if transfer is None:
            raise HTTPException(status_code=404, detail="Transfer not found")
        return transfer


@router.post("/", status_code=201)
def create_transfer(transfer: TransferCreate, user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        try:
            cursor.execute('SELECT "Current_Project_ID" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (transfer.Equipment_ID,))
            equipment = cursor.fetchone()
            if equipment is None:
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
            if equipment["Current_Project_ID"] != transfer.From_Project_ID:
                raise HTTPException(status_code=400, detail=f"From_Project_ID must match the equipment's current project ({equipment['Current_Project_ID']}).")
            if transfer.To_Project_ID == transfer.From_Project_ID:
                raise HTTPException(status_code=400, detail="To Project must be different from From Project.")
            if transfer.Transfer_Status == "Pending":
                cursor.execute('SELECT "Transfer_ID" FROM "TRANSFER" WHERE "Equipment_ID" = %s AND "Transfer_Status" = \'Pending\';', (transfer.Equipment_ID,))
                existing = cursor.fetchone()
                if existing:
                    raise HTTPException(status_code=409, detail=f"{transfer.Equipment_ID} already has a Pending transfer request (Transfer ID {existing['Transfer_ID']}).")
            cursor.execute(
                'INSERT INTO "TRANSFER" ("Equipment_ID", "From_Project_ID", "To_Project_ID", "Requested_By", "Approved_By", '
                '"Request_Date", "Effective_Transfer_Date", "Transfer_Status", "Rejection_Reason", "Transfer_Notes") '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *;',
                (transfer.Equipment_ID, transfer.From_Project_ID, transfer.To_Project_ID, transfer.Requested_By,
                 transfer.Approved_By, transfer.Request_Date, transfer.Effective_Transfer_Date,
                 transfer.Transfer_Status, transfer.Rejection_Reason, transfer.Transfer_Notes),
            )
            new_transfer = cursor.fetchone()
            if transfer.Transfer_Status in ("Approved", "Completed"):
                cursor.execute('UPDATE "EQUIPMENT" SET "Current_Project_ID" = %s WHERE "Equipment_ID" = %s;',
                               (transfer.To_Project_ID, transfer.Equipment_ID))
            return new_transfer
        except ForeignKeyViolation:
            connection.rollback()
            raise HTTPException(status_code=400, detail="Invalid Equipment_ID, project, Requested_By or Approved_By")
        except CheckViolation:
            connection.rollback()
            raise HTTPException(status_code=400, detail="Invalid value: To_Project_ID must differ from From_Project_ID, and Effective_Transfer_Date must be on or after Request_Date")


@router.put("/{transfer_id}")
def update_transfer(transfer_id: int, transfer: TransferCreate, user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor(row_factory=dict_row) as cursor:
        try:
            cursor.execute(
                'UPDATE "TRANSFER" SET "Equipment_ID" = %s, "From_Project_ID" = %s, "To_Project_ID" = %s, '
                '"Requested_By" = %s, "Approved_By" = %s, "Request_Date" = %s, "Effective_Transfer_Date" = %s, '
                '"Transfer_Status" = %s, "Rejection_Reason" = %s, "Transfer_Notes" = %s WHERE "Transfer_ID" = %s RETURNING *;',
                (transfer.Equipment_ID, transfer.From_Project_ID, transfer.To_Project_ID, transfer.Requested_By,
                 transfer.Approved_By, transfer.Request_Date, transfer.Effective_Transfer_Date,
                 transfer.Transfer_Status, transfer.Rejection_Reason, transfer.Transfer_Notes, transfer_id),
            )
            updated = cursor.fetchone()
            if updated is None:
                raise HTTPException(status_code=404, detail="Transfer not found")
            # Only move the equipment if this transfer still applies (equipment is on its From project),
            # so editing an OLD transfer can't drag a machine back to a site it left months ago.
            if transfer.Transfer_Status in ("Approved", "Completed"):
                cursor.execute(
                    'UPDATE "EQUIPMENT" SET "Current_Project_ID" = %s WHERE "Equipment_ID" = %s AND "Current_Project_ID" = %s;',
                    (transfer.To_Project_ID, transfer.Equipment_ID, transfer.From_Project_ID),
                )
            return updated
        except ForeignKeyViolation:
            connection.rollback()
            raise HTTPException(status_code=400, detail="Invalid Equipment_ID, project, Requested_By or Approved_By")
        except CheckViolation:
            connection.rollback()
            raise HTTPException(status_code=400, detail="Invalid value: To_Project_ID must differ from From_Project_ID, and Effective_Transfer_Date must be on or after Request_Date")


@router.delete("/{transfer_id}", status_code=204)
def delete_transfer(transfer_id: int, user: dict = Depends(require_roles("fleet_manager"))):
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute('DELETE FROM "TRANSFER" WHERE "Transfer_ID" = %s;', (transfer_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Transfer not found")
