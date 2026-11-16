import re

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from database import get_connection
from security import (
    BLOCKED_STATUSES,
    create_access_token,
    get_current_user,
    hash_password,
    public_user,
    role_key,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Roles a person may pick when creating their own account.
# Fleet Manager is deliberately NOT here: that role approves transfers, so it must be
# given by an existing Fleet Manager, never self-selected.
SELF_SERVICE_ROLES = {"site_engineer", "mechanic"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginBody(BaseModel):
    email: str
    password: str


class RegisterBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    role: str  # "site_engineer" or "mechanic"


@router.post("/login")
def login(body: LoginBody):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'SELECT e."Employee_ID", e."Employee_Name", e."Email", e."Employee_Status", '
                '       e."Password_Hash", r."Role_Name" '
                'FROM "EMPLOYEE" e LEFT JOIN "ROLE" r ON r."Role_ID" = e."Role_ID" '
                'WHERE lower(e."Email") = lower(%s);',
                (body.email.strip(),),
            )
            row = cursor.fetchone()

    # One generic message for "no such user" and "wrong password", so the login
    # screen can't be used to discover which emails exist.
    bad_login = HTTPException(status_code=401, detail="Invalid email or password.")
    if row is None or not verify_password(body.password, row["Password_Hash"]):
        raise bad_login
    # Only reached with the CORRECT password, so this message leaks nothing.
    if (row["Employee_Status"] or "").lower() in BLOCKED_STATUSES:
        raise HTTPException(
            status_code=403,
            detail="This account is not active. If you just created it, a Fleet Manager "
                   "needs to approve it first.",
        )

    return {
        "access_token": create_access_token(row["Employee_ID"]),
        "token_type": "bearer",
        "user": public_user(row),
    }


def next_employee_id(cursor) -> str:
    """Make the next Employee_ID in the SAME style as the existing ones
    (e.g. E007 -> E008, EMP-0012 -> EMP-0013), so we never have to guess the format."""
    cursor.execute('SELECT "Employee_ID" FROM "EMPLOYEE";')
    best = None  # (number, prefix, width)
    for row in cursor.fetchall():
        m = re.match(r"^(\D*)(\d+)$", row["Employee_ID"] or "")
        if m and (best is None or int(m.group(2)) > best[0]):
            best = (int(m.group(2)), m.group(1), len(m.group(2)))
    if best is None:
        return "EMP-0001"
    number, prefix, width = best
    return f"{prefix}{str(number + 1).zfill(width)}"


@router.post("/register", status_code=201)
def register(body: RegisterBody):
    """Create-your-own-account. The account starts as 'Inactive' (existing status value,
    so no schema change) and cannot sign in until a Fleet Manager sets it to 'Active'
    on the Employees page."""
    email = body.email.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if body.role not in SELF_SERVICE_ROLES:
        raise HTTPException(
            status_code=400,
            detail="You can create a Site Engineer or Workshop Mechanic account. "
                   "Fleet Manager accounts are created by an existing Fleet Manager.",
        )

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT "Role_ID", "Role_Name" FROM "ROLE";')
            role_id = next((r["Role_ID"] for r in cursor.fetchall() if role_key(r["Role_Name"]) == body.role), None)
            if role_id is None:
                raise HTTPException(status_code=400, detail="That role is not set up in the system.")

            cursor.execute('SELECT 1 FROM "EMPLOYEE" WHERE lower("Email") = %s;', (email,))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="An account with this email already exists.")

            password_hash = hash_password(body.password)
            for _ in range(3):  # retry if two people register at the very same moment
                employee_id = next_employee_id(cursor)
                try:
                    cursor.execute(
                        'INSERT INTO "EMPLOYEE" ("Employee_ID", "Employee_Name", "Email", "Phone", '
                        '"Role_ID", "Employee_Status", "Password_Hash") '
                        "VALUES (%s, %s, %s, %s, %s, 'Inactive', %s);",
                        (employee_id, body.name.strip(), email, (body.phone or "").strip() or None, role_id, password_hash),
                    )
                    break
                except psycopg.errors.UniqueViolation:
                    connection.rollback()
            else:
                raise HTTPException(status_code=500, detail="Could not create the account. Please try again.")

    return {
        "Employee_ID": employee_id,
        "message": "Account created. A Fleet Manager must approve it before you can sign in.",
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Who am I? The frontend calls this on page load to restore the session."""
    return user
