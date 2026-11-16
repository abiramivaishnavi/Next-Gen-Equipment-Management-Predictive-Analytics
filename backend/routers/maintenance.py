from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel
from database import get_connection
from security import get_current_user, require_roles
from datetime import date
from entry_checks import check_service_date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: mechanic
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("mechanic"))


class MaintenanceCreate(BaseModel):
    Equipment_ID: str
    Service_Date: date
    Maintenance_Type: str
    Meter_Reading: float | None = None
    Service_Details: str | None = None
    Next_Service_Date: date | None = None
    Total_Cost: float | None = None


@router.get("/")
def get_maintenance_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "MAINTENANCE" ORDER BY "Maintenance_ID";')
            return cursor.fetchall()


@router.get("/{maintenance_id}")
def get_maintenance(maintenance_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "MAINTENANCE" WHERE "Maintenance_ID" = %s;', (maintenance_id,))
            record = cursor.fetchone()
            if record is None:
                raise HTTPException(status_code=404, detail="Maintenance record not found")
            return record


@router.post("/", status_code=201)
def create_maintenance(record: MaintenanceCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                check_service_date(cursor, record.Equipment_ID, record.Service_Date, "added")
                cursor.execute(
                    'INSERT INTO "MAINTENANCE" '
                    '("Equipment_ID", "Service_Date", "Maintenance_Type", "Meter_Reading", '
                    '"Service_Details", "Next_Service_Date", "Total_Cost") '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *;',
                    (
                        record.Equipment_ID,
                        record.Service_Date,
                        record.Maintenance_Type,
                        record.Meter_Reading,
                        record.Service_Details,
                        record.Next_Service_Date,
                        record.Total_Cost,
                    )
                )
                return cursor.fetchone()
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: Meter_Reading and Total_Cost must be >= 0, "
                           "Next_Service_Date must be on or after Service_Date"
                )


@router.put("/{maintenance_id}")
def update_maintenance(maintenance_id: int, record: MaintenanceCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                # Check the date only when the service date or the machine is being changed, so other edits
                # to an older record (cost, details...) always stay possible.
                cursor.execute(
                    'SELECT "Equipment_ID", "Service_Date" FROM "MAINTENANCE" WHERE "Maintenance_ID" = %s;',
                    (maintenance_id,),
                )
                before = cursor.fetchone()
                if before is None:
                    raise HTTPException(status_code=404, detail="Maintenance record not found")
                if before["Equipment_ID"] != record.Equipment_ID or before["Service_Date"] != record.Service_Date:
                    check_service_date(cursor, record.Equipment_ID, record.Service_Date, "saved")
                cursor.execute(
                    'UPDATE "MAINTENANCE" SET '
                    '"Equipment_ID" = %s, "Service_Date" = %s, "Maintenance_Type" = %s, '
                    '"Meter_Reading" = %s, "Service_Details" = %s, "Next_Service_Date" = %s, "Total_Cost" = %s '
                    'WHERE "Maintenance_ID" = %s RETURNING *;',
                    (
                        record.Equipment_ID,
                        record.Service_Date,
                        record.Maintenance_Type,
                        record.Meter_Reading,
                        record.Service_Details,
                        record.Next_Service_Date,
                        record.Total_Cost,
                        maintenance_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Maintenance record not found")
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: Meter_Reading and Total_Cost must be >= 0, "
                           "Next_Service_Date must be on or after Service_Date"
                )


@router.delete("/{maintenance_id}", status_code=204)
def delete_maintenance(maintenance_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "MAINTENANCE" WHERE "Maintenance_ID" = %s;', (maintenance_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Maintenance record not found")