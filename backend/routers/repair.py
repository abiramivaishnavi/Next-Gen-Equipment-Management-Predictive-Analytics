from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel
from database import get_connection
from security import get_current_user, require_roles
from equipment_status import sync_machine_status
from datetime import date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/repairs", tags=["Repairs"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: mechanic
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("mechanic"))


class RepairCreate(BaseModel):
    Breakdown_ID: int
    Repair_Date: date
    Parts_Replaced: str | None = None
    Labor_Hours: float | None = None
    Parts_Cost: float | None = None
    Labor_Cost: float | None = None
    Repair_Details: str | None = None


def _auto_downtime(cursor, breakdown_id: int, repair_date: date, old_repair_date: date | None = None):
    """Fill the breakdown's Downtime_Hours from the dates: (repair date - breakdown date) in days x 24.
    Dates only (no clock times), so this is an approximation: 24 h per day, a same-day repair counts as 0.
    A figure the mechanic typed is never overwritten. It is replaced only when it is empty / 0, or when it is
    the figure this rule gave for the OLD repair date (so correcting a repair date corrects the downtime too)."""
    cursor.execute(
        'SELECT "Breakdown_Date", "Downtime_Hours" FROM "BREAKDOWN" WHERE "Breakdown_ID" = %s;',
        (breakdown_id,),
    )
    b = cursor.fetchone()
    if b is None:
        return
    new_hours = max((repair_date - b["Breakdown_Date"]).days, 0) * 24
    current = float(b["Downtime_Hours"] or 0)
    came_from_old_date = (
        old_repair_date is not None and current == max((old_repair_date - b["Breakdown_Date"]).days, 0) * 24
    )
    if current == 0 or came_from_old_date:
        cursor.execute(
            'UPDATE "BREAKDOWN" SET "Downtime_Hours" = %s WHERE "Breakdown_ID" = %s;',
            (new_hours, breakdown_id),
        )


def _revert_breakdown_if_no_repairs_left(cursor, breakdown_id: int):
    """If a breakdown no longer has any repair logged against it, it isn't
    actually fixed anymore — put its status back to 'Under Repair' instead of
    leaving it stuck on 'Resolved' with no repair record to justify that."""
    cursor.execute('SELECT COUNT(*) AS count FROM "REPAIR" WHERE "Breakdown_ID" = %s;', (breakdown_id,))
    remaining = cursor.fetchone()["count"]
    if remaining == 0:
        cursor.execute(
            'UPDATE "BREAKDOWN" SET "Breakdown_Status" = %s WHERE "Breakdown_ID" = %s;',
            ("Under Repair", breakdown_id)
        )
    _sync_machine_of_breakdown(cursor, breakdown_id)


def _sync_machine_of_breakdown(cursor, breakdown_id: int):
    """A repair changes its breakdown's status, which can free (or re-lock) the machine itself."""
    cursor.execute('SELECT "Equipment_ID" FROM "BREAKDOWN" WHERE "Breakdown_ID" = %s;', (breakdown_id,))
    row = cursor.fetchone()
    if row:
        sync_machine_status(cursor, row["Equipment_ID"])


@router.get("/")
def get_repair_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "REPAIR" ORDER BY "Repair_ID";')
            return cursor.fetchall()


@router.get("/{repair_id}")
def get_repair(repair_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "REPAIR" WHERE "Repair_ID" = %s;', (repair_id,))
            repair = cursor.fetchone()
            if repair is None:
                raise HTTPException(status_code=404, detail="Repair not found")
            return repair


@router.post("/", status_code=201)
def create_repair(repair: RepairCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "REPAIR" '
                    '("Breakdown_ID", "Repair_Date", "Parts_Replaced", "Labor_Hours", '
                    '"Parts_Cost", "Labor_Cost", "Repair_Details") '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *;',
                    (
                        repair.Breakdown_ID,
                        repair.Repair_Date,
                        repair.Parts_Replaced,
                        repair.Labor_Hours,
                        repair.Parts_Cost,
                        repair.Labor_Cost,
                        repair.Repair_Details,
                    )
                )
                created = cursor.fetchone()

                cursor.execute(
                    'UPDATE "BREAKDOWN" SET "Breakdown_Status" = %s WHERE "Breakdown_ID" = %s;',
                    ("Resolved", repair.Breakdown_ID)
                )
                _auto_downtime(cursor, repair.Breakdown_ID, repair.Repair_Date)
                _sync_machine_of_breakdown(cursor, repair.Breakdown_ID)

                return created
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Breakdown_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Labor_Hours, Parts_Cost and Labor_Cost must be >= 0"
                )


@router.put("/{repair_id}")
def update_repair(repair_id: int, repair: RepairCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute('SELECT "Breakdown_ID", "Repair_Date" FROM "REPAIR" WHERE "Repair_ID" = %s;', (repair_id,))
                existing = cursor.fetchone()
                old_breakdown_id = existing["Breakdown_ID"] if existing else None
                old_repair_date = existing["Repair_Date"] if existing else None

                cursor.execute(
                    'UPDATE "REPAIR" SET '
                    '"Breakdown_ID" = %s, "Repair_Date" = %s, "Parts_Replaced" = %s, '
                    '"Labor_Hours" = %s, "Parts_Cost" = %s, "Labor_Cost" = %s, "Repair_Details" = %s '
                    'WHERE "Repair_ID" = %s RETURNING *;',
                    (
                        repair.Breakdown_ID,
                        repair.Repair_Date,
                        repair.Parts_Replaced,
                        repair.Labor_Hours,
                        repair.Parts_Cost,
                        repair.Labor_Cost,
                        repair.Repair_Details,
                        repair_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Repair not found")

                cursor.execute(
                    'UPDATE "BREAKDOWN" SET "Breakdown_Status" = %s WHERE "Breakdown_ID" = %s;',
                    ("Resolved", repair.Breakdown_ID)
                )

                _auto_downtime(
                    cursor, repair.Breakdown_ID, repair.Repair_Date,
                    old_repair_date if old_breakdown_id == repair.Breakdown_ID else None,
                )
                _sync_machine_of_breakdown(cursor, repair.Breakdown_ID)
                if old_breakdown_id is not None and old_breakdown_id != repair.Breakdown_ID:
                    _revert_breakdown_if_no_repairs_left(cursor, old_breakdown_id)

                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Breakdown_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Labor_Hours, Parts_Cost and Labor_Cost must be >= 0"
                )


@router.delete("/{repair_id}", status_code=204)
def delete_repair(repair_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'DELETE FROM "REPAIR" WHERE "Repair_ID" = %s RETURNING "Breakdown_ID";',
                (repair_id,)
            )
            deleted = cursor.fetchone()
            if deleted is None:
                raise HTTPException(status_code=404, detail="Repair not found")

            _revert_breakdown_if_no_repairs_left(cursor, deleted["Breakdown_ID"])