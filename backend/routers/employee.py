from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from psycopg.errors import UniqueViolation, ForeignKeyViolation

router = APIRouter(prefix="/employees", tags=["Employees"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : fleet_manager
#   write: fleet_manager
READ_ACCESS = Depends(require_roles("fleet_manager"))
WRITE_ACCESS = Depends(require_roles("fleet_manager"))


# Never send Password_Hash to the browser (SELECT * would include it).
COLUMNS = '"Employee_ID", "Employee_Name", "Email", "Phone", "Role_ID", "Employee_Status"'


class EmployeeCreate(BaseModel):
    Employee_ID: str
    Employee_Name: str
    Email: str
    Phone: str | None = None  # optional: the form says "(optional)" and the column allows empty
    Role_ID: int
    Employee_Status: str = "Active"

    @field_validator("Phone")
    @classmethod
    def blank_phone_is_empty(cls, value):
        return (value or "").strip() or None


@router.get("/")
def get_employees(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(f'SELECT {COLUMNS} FROM "EMPLOYEE" ORDER BY "Employee_ID";')
            return cursor.fetchall()


@router.get("/{employee_id}")
def get_employee(employee_id: str, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(f'SELECT {COLUMNS} FROM "EMPLOYEE" WHERE "Employee_ID" = %s;', (employee_id,))
            employee = cursor.fetchone()
            if employee is None:
                raise HTTPException(status_code=404, detail="employee not found")
            return employee


@router.post("/", status_code=201)
def create_employee(employee: EmployeeCreate, user: dict = WRITE_ACCESS):
    employee.Employee_ID = employee.Employee_ID.upper()

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "EMPLOYEE" '
                    '("Employee_ID", "Employee_Name", "Email", "Phone", "Role_ID", "Employee_Status") '
                    f'VALUES (%s, %s, %s, %s, %s, %s) RETURNING {COLUMNS};',
                    (employee.Employee_ID, employee.Employee_Name, employee.Email,
                     employee.Phone, employee.Role_ID, employee.Employee_Status),
                )
                return cursor.fetchone()
            except UniqueViolation as e:
                connection.rollback()
                constraint = e.diag.constraint_name or ""
                if "pkey" in constraint:
                    raise HTTPException(status_code=409, detail="Employee_ID already exists")
                else:
                    raise HTTPException(status_code=409, detail="Email already exists")
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Role_ID does not exist")


@router.put("/{employee_id}")
def update_employee(employee_id: str, employee: EmployeeCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'UPDATE "EMPLOYEE" SET "Employee_Name" = %s, "Email" = %s, "Phone" = %s, '
                    f'"Role_ID" = %s, "Employee_Status" = %s WHERE "Employee_ID" = %s RETURNING {COLUMNS};',
                    (employee.Employee_Name, employee.Email, employee.Phone,
                     employee.Role_ID, employee.Employee_Status, employee_id),
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="employee not found")
                return updated
            except UniqueViolation as e:
                connection.rollback()
                constraint = e.diag.constraint_name or ""
                if "pkey" in constraint:
                    raise HTTPException(status_code=409, detail="Employee_ID already exists")
                else:
                    raise HTTPException(status_code=409, detail="Email already exists")
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Role_ID does not exist")


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: str, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "EMPLOYEE" WHERE "Employee_ID" = %s;', (employee_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="employee not found")