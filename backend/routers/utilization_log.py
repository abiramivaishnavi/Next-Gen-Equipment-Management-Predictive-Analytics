from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from entry_checks import check_entry_date, check_utilization_entry
from datetime import date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/utilization-logs", tags=["Utilization Logs"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: site_engineer
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("site_engineer"))


class UtilizationLogCreate(BaseModel):
    Equipment_ID: str
    Project_ID: str
    Log_Date: date
    Operating_Hours: float  # total hours worked in the period this entry covers (the sample data = one week, up to 168)

    @field_validator("Equipment_ID", "Project_ID")
    @classmethod
    def tidy_id(cls, value: str) -> str:
        return value.strip().upper()


@router.get("/")
def get_utilization_log_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "UTILIZATION_LOG" ORDER BY "Utilization_ID";')
            return cursor.fetchall()


@router.get("/{utilization_id}")
def get_utilization_log(utilization_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'SELECT * FROM "UTILIZATION_LOG" WHERE "Utilization_ID" = %s;',
                (utilization_id,)
            )
            log = cursor.fetchone()
            if log is None:
                raise HTTPException(status_code=404, detail="Utilization log not found")
            return log


@router.post("/", status_code=201)
def create_utilization_log(log: UtilizationLogCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                check_entry_date(cursor, log.Equipment_ID, log.Log_Date, "Operating-hours", "added")
                check_utilization_entry(cursor, log.Equipment_ID, log.Log_Date, log.Operating_Hours, "added")
                cursor.execute(
                    'INSERT INTO "UTILIZATION_LOG" '
                    '("Equipment_ID", "Project_ID", "Log_Date", "Operating_Hours") '
                    'VALUES (%s, %s, %s, %s) RETURNING *;',
                    (log.Equipment_ID, log.Project_ID, log.Log_Date, log.Operating_Hours)
                )
                return cursor.fetchone()
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Operating_Hours must be >= 0")


@router.put("/{utilization_id}")
def update_utilization_log(utilization_id: int, log: UtilizationLogCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                # Only re-check the date when the date or the machine is being changed.
                cursor.execute(
                    'SELECT "Equipment_ID", "Log_Date", "Operating_Hours" FROM "UTILIZATION_LOG" WHERE "Utilization_ID" = %s;',
                    (utilization_id,)
                )
                before = cursor.fetchone()
                if before is None:
                    raise HTTPException(status_code=404, detail="Utilization log not found")
                moved = before["Log_Date"] != log.Log_Date or before["Equipment_ID"] != log.Equipment_ID
                if moved:
                    check_entry_date(cursor, log.Equipment_ID, log.Log_Date, "Operating-hours", "saved")
                if moved or float(before["Operating_Hours"]) != log.Operating_Hours:
                    check_utilization_entry(cursor, log.Equipment_ID, log.Log_Date, log.Operating_Hours,
                                            "saved", exclude_id=utilization_id, check_week=moved)
                cursor.execute(
                    'UPDATE "UTILIZATION_LOG" SET '
                    '"Equipment_ID" = %s, "Project_ID" = %s, "Log_Date" = %s, "Operating_Hours" = %s '
                    'WHERE "Utilization_ID" = %s RETURNING *;',
                    (log.Equipment_ID, log.Project_ID, log.Log_Date, log.Operating_Hours, utilization_id)
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Utilization log not found")
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Operating_Hours must be >= 0")


@router.delete("/{utilization_id}", status_code=204)
def delete_utilization_log(utilization_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "UTILIZATION_LOG" WHERE "Utilization_ID" = %s;', (utilization_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Utilization log not found")