from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel
from database import get_connection
from security import get_current_user, require_roles

router = APIRouter(prefix="/roles", tags=["Roles"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : fleet_manager
#   write: fleet_manager
READ_ACCESS = Depends(require_roles("fleet_manager"))
WRITE_ACCESS = Depends(require_roles("fleet_manager"))


class RoleCreate(BaseModel):
    Role_Name: str
    Role_Description: str | None = None


@router.get("/")
def get_roles(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "ROLE" ORDER BY "Role_ID";')
            return cursor.fetchall()


@router.get("/{role_id}")
def get_role(role_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "ROLE" WHERE "Role_ID" = %s;', (role_id,))
            role = cursor.fetchone()
            if role is None:
                raise HTTPException(status_code=404, detail="Role not found")
            return role


@router.post("/", status_code=201)
def create_role(role: RoleCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'INSERT INTO "ROLE" ("Role_Name", "Role_Description") '
                'VALUES (%s, %s) RETURNING *;',
                (role.Role_Name, role.Role_Description),
            )
            return cursor.fetchone()


@router.put("/{role_id}")
def update_role(role_id: int, role: RoleCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'UPDATE "ROLE" SET "Role_Name" = %s, "Role_Description" = %s '
                'WHERE "Role_ID" = %s RETURNING *;',
                (role.Role_Name, role.Role_Description, role_id),
            )
            updated = cursor.fetchone()
            if updated is None:
                raise HTTPException(status_code=404, detail="Role not found")
            return updated


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "ROLE" WHERE "Role_ID" = %s;', (role_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Role not found")