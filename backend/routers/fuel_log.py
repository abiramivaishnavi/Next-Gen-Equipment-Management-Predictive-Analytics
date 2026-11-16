from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from entry_checks import check_entry_date
from datetime import date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/fuel-logs", tags=["Fuel Logs"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: site_engineer
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("site_engineer"))


class FuelLogCreate(BaseModel):
    Equipment_ID: str
    Project_ID: str
    Fuel_Date: date
    Fuel_Consumed: float
    # Fuel_Consumed is in LITRES for Diesel/Petrol and kWh for Electric (see fuel_units.py).
    # Fuel_Cost is intentionally NOT here anymore. It's computed automatically
    # from FUEL_RATE based on the equipment's fuel type and this log's date,
    # not entered by the user.

    @field_validator("Equipment_ID", "Project_ID")
    @classmethod
    def tidy_id(cls, value: str) -> str:
        return value.strip().upper()


def _compute_fuel_cost(cursor, equipment_id: str, fuel_date: date, fuel_consumed: float) -> float:
    """Looks up the equipment's fuel type, then the latest FUEL_RATE effective
    on or before fuel_date for that type, and returns Fuel_Consumed x the rate per unit
    (the column is still called Rate_Per_Liter; for Electric the unit is kWh)."""
    cursor.execute('SELECT "Fuel_Type" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (equipment_id,))
    equipment = cursor.fetchone()
    if equipment is None:
        raise HTTPException(status_code=400, detail="Invalid Equipment_ID")

    fuel_type = equipment["Fuel_Type"]
    cursor.execute(
        'SELECT "Rate_Per_Liter" FROM "FUEL_RATE" '
        'WHERE lower("Fuel_Type") = lower(%s) AND "Effective_Date" <= %s '
        'ORDER BY "Effective_Date" DESC LIMIT 1;',
        (fuel_type, fuel_date)
    )
    rate_row = cursor.fetchone()
    if rate_row is None:
        # Two different problems, two different messages.
        cursor.execute(
            'SELECT MIN("Effective_Date") AS first_date FROM "FUEL_RATE" WHERE lower("Fuel_Type") = lower(%s);',
            (fuel_type,)
        )
        first = cursor.fetchone()["first_date"]
        if first is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No fuel price set for '{fuel_type}' yet - ask a Fleet Manager to add it in Fuel Rates. "
                    f"Entry not saved."
                )
            )
        raise HTTPException(
            status_code=400,
            detail=(
                f"No fuel price for '{fuel_type}' on {fuel_date} - the first price starts on {first}. "
                f"Ask a Fleet Manager to check Fuel Rates. Entry not saved."
            )
        )

    return round(fuel_consumed * float(rate_row["Rate_Per_Liter"]), 2)


@router.get("/")
def get_fuel_log_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "FUEL_LOG" ORDER BY "Fuel_Log_ID";')
            return cursor.fetchall()


@router.get("/{fuel_log_id}")
def get_fuel_log(fuel_log_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "FUEL_LOG" WHERE "Fuel_Log_ID" = %s;', (fuel_log_id,))
            log = cursor.fetchone()
            if log is None:
                raise HTTPException(status_code=404, detail="Fuel log not found")
            return log


@router.post("/", status_code=201)
def create_fuel_log(log: FuelLogCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                check_entry_date(cursor, log.Equipment_ID, log.Fuel_Date, "Fuel", "added")
                fuel_cost = _compute_fuel_cost(cursor, log.Equipment_ID, log.Fuel_Date, log.Fuel_Consumed)

                cursor.execute(
                    'INSERT INTO "FUEL_LOG" '
                    '("Equipment_ID", "Project_ID", "Fuel_Date", "Fuel_Consumed", "Fuel_Cost") '
                    'VALUES (%s, %s, %s, %s, %s) RETURNING *;',
                    (log.Equipment_ID, log.Project_ID, log.Fuel_Date, log.Fuel_Consumed, fuel_cost)
                )
                return cursor.fetchone()
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Fuel_Consumed and Fuel_Cost must be >= 0")


@router.put("/{fuel_log_id}")
def update_fuel_log(fuel_log_id: int, log: FuelLogCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                # Only re-check the date when the date or the machine is being changed: fixing the litres of an
                # old entry must keep working.
                cursor.execute(
                    'SELECT "Equipment_ID", "Fuel_Date" FROM "FUEL_LOG" WHERE "Fuel_Log_ID" = %s;', (fuel_log_id,)
                )
                before = cursor.fetchone()
                if before is None:
                    raise HTTPException(status_code=404, detail="Fuel log not found")
                if before["Fuel_Date"] != log.Fuel_Date or before["Equipment_ID"] != log.Equipment_ID:
                    check_entry_date(cursor, log.Equipment_ID, log.Fuel_Date, "Fuel", "saved")
                fuel_cost = _compute_fuel_cost(cursor, log.Equipment_ID, log.Fuel_Date, log.Fuel_Consumed)

                cursor.execute(
                    'UPDATE "FUEL_LOG" SET '
                    '"Equipment_ID" = %s, "Project_ID" = %s, "Fuel_Date" = %s, '
                    '"Fuel_Consumed" = %s, "Fuel_Cost" = %s '
                    'WHERE "Fuel_Log_ID" = %s RETURNING *;',
                    (log.Equipment_ID, log.Project_ID, log.Fuel_Date, log.Fuel_Consumed,
                     fuel_cost, fuel_log_id)
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Fuel log not found")
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Fuel_Consumed and Fuel_Cost must be >= 0")


@router.delete("/{fuel_log_id}", status_code=204)
def delete_fuel_log(fuel_log_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "FUEL_LOG" WHERE "Fuel_Log_ID" = %s;', (fuel_log_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Fuel log not found")