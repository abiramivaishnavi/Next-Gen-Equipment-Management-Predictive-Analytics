from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from equipment_status import sync_machine_status
from datetime import date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/breakdowns", tags=["Breakdowns"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: mechanic
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("mechanic"))

# The only statuses a breakdown can have. "Open" = reported, work not started.
STATUSES = ["Open", "Under Repair", "Resolved"]


class BreakdownCreate(BaseModel):
    Equipment_ID: str
    Breakdown_Date: date
    Description: str | None = None
    Downtime_Hours: float | None = None
    Breakdown_Status: str

    @field_validator("Equipment_ID")
    @classmethod
    def tidy_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("Breakdown_Status")
    @classmethod
    def known_status(cls, value: str) -> str:
        # "under repair" / "UNDER REPAIR" are saved as "Under Repair" so the dashboards never see two spellings.
        for status in STATUSES:
            if value.strip().lower() == status.lower():
                return status
        raise ValueError("Status must be Open, Under Repair or Resolved")


@router.get("/")
def get_breakdown_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "BREAKDOWN" ORDER BY "Breakdown_ID";')
            return cursor.fetchall()


@router.get("/{breakdown_id}")
def get_breakdown(breakdown_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "BREAKDOWN" WHERE "Breakdown_ID" = %s;', (breakdown_id,))
            breakdown = cursor.fetchone()
            if breakdown is None:
                raise HTTPException(status_code=404, detail="Breakdown not found")
            return breakdown


@router.post("/", status_code=201)
def create_breakdown(breakdown: BreakdownCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "BREAKDOWN" '
                    '("Equipment_ID", "Breakdown_Date", "Description", "Downtime_Hours", "Breakdown_Status") '
                    'VALUES (%s, %s, %s, %s, %s) RETURNING *;',
                    (
                        breakdown.Equipment_ID,
                        breakdown.Breakdown_Date,
                        breakdown.Description,
                        breakdown.Downtime_Hours,
                        breakdown.Breakdown_Status,
                    )
                )
                created = cursor.fetchone()
                # Same transaction: an unresolved breakdown puts the machine 'Under Repair'.
                sync_machine_status(cursor, created["Equipment_ID"])
                return created
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Downtime_Hours must be >= 0")


@router.put("/{breakdown_id}")
def update_breakdown(breakdown_id: int, breakdown: BreakdownCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute('SELECT "Equipment_ID" FROM "BREAKDOWN" WHERE "Breakdown_ID" = %s;', (breakdown_id,))
                before = cursor.fetchone()

                cursor.execute(
                    'UPDATE "BREAKDOWN" SET '
                    '"Equipment_ID" = %s, "Breakdown_Date" = %s, "Description" = %s, '
                    '"Downtime_Hours" = %s, "Breakdown_Status" = %s '
                    'WHERE "Breakdown_ID" = %s RETURNING *;',
                    (
                        breakdown.Equipment_ID,
                        breakdown.Breakdown_Date,
                        breakdown.Description,
                        breakdown.Downtime_Hours,
                        breakdown.Breakdown_Status,
                        breakdown_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Breakdown not found")
                # The breakdown may have been moved to another machine: refresh both.
                if before and before["Equipment_ID"] != updated["Equipment_ID"]:
                    sync_machine_status(cursor, before["Equipment_ID"])
                sync_machine_status(cursor, updated["Equipment_ID"])
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Downtime_Hours must be >= 0")


@router.delete("/{breakdown_id}", status_code=204)
def delete_breakdown(breakdown_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'DELETE FROM "BREAKDOWN" WHERE "Breakdown_ID" = %s RETURNING "Equipment_ID";', (breakdown_id,)
                )
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=409,
                    detail="This breakdown has repair records. Delete those repairs first.",
                )
            deleted = cursor.fetchone()
            if deleted is None:
                raise HTTPException(status_code=404, detail="Breakdown not found")
            # Deleting the only open breakdown frees the machine again.
            sync_machine_status(cursor, deleted["Equipment_ID"])
