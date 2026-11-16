from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from datetime import date
from psycopg.errors import UniqueViolation, CheckViolation

router = APIRouter(prefix="/equipment", tags=["Equipment"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: site_engineer
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("site_engineer"))


# What "Capacity" is measured in. Stored with every machine (EQUIPMENT.Capacity_Unit).
CAPACITY_UNITS = ["tonnes", "m3", "kW", "litres"]


def _tidy_fuel_type(cursor, typed: str) -> str:
    """One spelling per fuel type. 'diesel ' / 'DIESEL' become the spelling already in use ('Diesel');
    a brand-new type gets a capital first letter ('Biodiesel'); short all-capital names such as CNG or LPG stay as typed."""
    typed = " ".join((typed or "").split())
    cursor.execute(
        'SELECT "Fuel_Type" AS v FROM "EQUIPMENT" WHERE lower("Fuel_Type") = lower(%s) '
        'UNION SELECT "Fuel_Type" FROM "FUEL_RATE" WHERE lower("Fuel_Type") = lower(%s) LIMIT 1;',
        (typed, typed),
    )
    existing = cursor.fetchone()
    if existing:
        return existing["v"]
    if typed.isupper() and len(typed) <= 4:
        return typed
    return typed.title()


def check_equipment_dates(equipment_id: str, year: int, purchased: date | None, verb: str):
    """Manufacturing year and purchase date must make sense:
       - not in the future
       - the purchase date is not before the start of the manufacturing year"""
    today = date.today()
    if year > today.year:
        raise HTTPException(
            status_code=400,
            detail=f"Manufacturing year {year} is in the future. Equipment not {verb}.",
        )
    if purchased is not None:
        if purchased > today:
            raise HTTPException(
                status_code=400,
                detail=f"Purchase date {purchased} is in the future. Equipment not {verb}.",
            )
        if purchased < date(year, 1, 1):
            raise HTTPException(
                status_code=400,
                detail=f"Purchase date {purchased} is before the manufacturing year {year}. Equipment not {verb}.",
            )


class EquipmentCreate(BaseModel):
    Equipment_ID: str
    Equipment_Type: str
    Equipment_Name: str
    Manufacturer: str | None = None
    Model: str | None = None
    Manufacturing_Year: int
    Fuel_Type: str
    Capacity: float | None = None
    # Left out (None) = keep the current unit when editing, 'tonnes' when creating.
    Capacity_Unit: str | None = None
    Purchase_Date: date | None = None
    Current_Status: str
    # The project the machine starts on. Used when ADDING only; after that a machine moves between
    # projects through the Transfer request / approval workflow (so every move is recorded and approved).
    Current_Project_ID: str | None = None

    @field_validator("Current_Project_ID")
    @classmethod
    def tidy_project(cls, value):
        if value is None or value.strip() == "":
            return None
        return value.strip().upper()

    @field_validator("Equipment_ID")
    @classmethod
    def tidy_id(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("Capacity_Unit")
    @classmethod
    def known_unit(cls, value):
        if value is None or value.strip() == "":
            return None
        for unit in CAPACITY_UNITS:
            if value.strip().lower() == unit.lower():
                return unit
        raise ValueError("Capacity unit must be one of: " + ", ".join(CAPACITY_UNITS))


@router.get("/")
def get_equipment_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "EQUIPMENT" ORDER BY "Equipment_ID";')
            return cursor.fetchall()


@router.get("/{equipment_id}")
def get_equipment(equipment_id: str, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (equipment_id,))
            equipment = cursor.fetchone()
            if equipment is None:
                raise HTTPException(status_code=404, detail="Equipment not found")
            return equipment


@router.post("/", status_code=201)
def create_equipment(equipment: EquipmentCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                check_equipment_dates(equipment.Equipment_ID, equipment.Manufacturing_Year, equipment.Purchase_Date, "added")
                if equipment.Current_Project_ID is not None:
                    cursor.execute(
                        'SELECT "Project_Status" FROM "PROJECT" WHERE "Project_ID" = %s;',
                        (equipment.Current_Project_ID,),
                    )
                    project = cursor.fetchone()
                    if project is None:
                        raise HTTPException(status_code=400, detail=f"Unknown project {equipment.Current_Project_ID}. Equipment not added.")
                    if project["Project_Status"] not in ("Active", "On Hold"):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Project {equipment.Current_Project_ID} is {project['Project_Status']}, so equipment cannot be placed on it. Equipment not added.",
                        )
                fuel_type = _tidy_fuel_type(cursor, equipment.Fuel_Type)
                cursor.execute(
                    'INSERT INTO "EQUIPMENT" '
                    '("Equipment_ID", "Equipment_Type", "Equipment_Name", "Manufacturer", "Model", '
                    '"Manufacturing_Year", "Fuel_Type", "Capacity", "Capacity_Unit", "Purchase_Date", "Current_Status", '
                    '"Current_Project_ID") '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *;',
                    (
                        equipment.Equipment_ID,
                        equipment.Equipment_Type,
                        equipment.Equipment_Name,
                        equipment.Manufacturer,
                        equipment.Model,
                        equipment.Manufacturing_Year,
                        fuel_type,
                        equipment.Capacity,
                        equipment.Capacity_Unit or "tonnes",
                        equipment.Purchase_Date,
                        equipment.Current_Status,
                        equipment.Current_Project_ID,
                    )
                )
                return cursor.fetchone()
            except UniqueViolation:
                connection.rollback()
                raise HTTPException(status_code=409, detail="Equipment_ID already exists")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: check Manufacturing_Year (>= 1900) and Capacity (> 0)"
                )


@router.put("/{equipment_id}")
def update_equipment(equipment_id: str, equipment: EquipmentCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                # Re-check the dates only when the year or purchase date is being changed, so other edits to an
                # older record always stay possible.
                cursor.execute(
                    'SELECT "Manufacturing_Year", "Purchase_Date" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;',
                    (equipment_id,),
                )
                before = cursor.fetchone()
                if before is None:
                    raise HTTPException(status_code=404, detail="Equipment not found")
                if (before["Manufacturing_Year"] != equipment.Manufacturing_Year
                        or before["Purchase_Date"] != equipment.Purchase_Date):
                    check_equipment_dates(equipment_id, equipment.Manufacturing_Year, equipment.Purchase_Date, "saved")
                fuel_type = _tidy_fuel_type(cursor, equipment.Fuel_Type)
                cursor.execute(
                    'UPDATE "EQUIPMENT" SET '
                    '"Equipment_Type" = %s, "Equipment_Name" = %s, "Manufacturer" = %s, "Model" = %s, '
                    '"Manufacturing_Year" = %s, "Fuel_Type" = %s, "Capacity" = %s, '
                    '"Capacity_Unit" = COALESCE(%s, "Capacity_Unit"), '
                    '"Purchase_Date" = %s, "Current_Status" = %s '
                    'WHERE "Equipment_ID" = %s RETURNING *;',
                    (
                        equipment.Equipment_Type,
                        equipment.Equipment_Name,
                        equipment.Manufacturer,
                        equipment.Model,
                        equipment.Manufacturing_Year,
                        fuel_type,
                        equipment.Capacity,
                        equipment.Capacity_Unit,
                        equipment.Purchase_Date,
                        equipment.Current_Status,
                        equipment_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Equipment not found")
                return updated
            except UniqueViolation:
                connection.rollback()
                raise HTTPException(status_code=409, detail="Equipment_ID already exists")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: check Manufacturing_Year (>= 1900) and Capacity (> 0)"
                )


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: str, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (equipment_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Equipment not found")