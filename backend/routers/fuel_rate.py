from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel
from database import get_connection
from security import get_current_user, require_roles
from datetime import date
from psycopg.errors import CheckViolation

router = APIRouter(prefix="/fuel-rates", tags=["Fuel Rates"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: fleet_manager
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("fleet_manager"))


class FuelRateCreate(BaseModel):
    Fuel_Type: str
    Rate_Per_Liter: float
    Effective_Date: date


@router.get("/")
def get_fuel_rate_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "FUEL_RATE" ORDER BY "Fuel_Type", "Effective_Date" DESC;')
            return cursor.fetchall()


@router.get("/{fuel_rate_id}")
def get_fuel_rate(fuel_rate_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "FUEL_RATE" WHERE "Fuel_Rate_ID" = %s;', (fuel_rate_id,))
            rate = cursor.fetchone()
            if rate is None:
                raise HTTPException(status_code=404, detail="Fuel rate not found")
            return rate


@router.post("/", status_code=201)
def create_fuel_rate(rate: FuelRateCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "FUEL_RATE" ("Fuel_Type", "Rate_Per_Liter", "Effective_Date") '
                    'VALUES (%s, %s, %s) RETURNING *;',
                    (rate.Fuel_Type, rate.Rate_Per_Liter, rate.Effective_Date)
                )
                return cursor.fetchone()
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Rate_Per_Liter must be > 0")


@router.put("/{fuel_rate_id}")
def update_fuel_rate(fuel_rate_id: int, rate: FuelRateCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'UPDATE "FUEL_RATE" SET "Fuel_Type" = %s, "Rate_Per_Liter" = %s, "Effective_Date" = %s '
                    'WHERE "Fuel_Rate_ID" = %s RETURNING *;',
                    (rate.Fuel_Type, rate.Rate_Per_Liter, rate.Effective_Date, fuel_rate_id)
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Fuel rate not found")
                return updated
            except CheckViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Rate_Per_Liter must be > 0")


@router.delete("/{fuel_rate_id}", status_code=204)
def delete_fuel_rate(fuel_rate_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "FUEL_RATE" WHERE "Fuel_Rate_ID" = %s;', (fuel_rate_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Fuel rate not found")