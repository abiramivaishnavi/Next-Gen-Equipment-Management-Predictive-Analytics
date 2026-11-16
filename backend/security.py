"""
Login + role checking for the EMS API.

How it works (plain version):
  1. The user signs in with email + password  ->  POST /auth/login
  2. If correct, the server hands back a signed token (a "badge") valid for 8 hours.
  3. The browser sends that token with every request.
  4. get_current_user() reads the token and works out WHO is calling and what ROLE they have.
  5. require_roles(...) lets a route say "only Fleet Managers may use this".

This is deliberately simple, prototype-grade security — enough to show real role-based
access (the assignment's RBAC requirement) without needing an identity provider.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt  # pip install pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.rows import dict_row

from database import get_connection

# In a real deployment set EMS_SECRET_KEY in the environment. The fallback is only so the
# prototype runs out of the box — anyone who knows it could forge a token.
SECRET_KEY = os.getenv("EMS_SECRET_KEY", "dev-only-change-me-before-any-real-use")
ALGORITHM = "HS256"
TOKEN_HOURS = 8  # one working shift
PBKDF2_ITERATIONS = 200_000

# Employees with these statuses can no longer sign in.
BLOCKED_STATUSES = {"inactive", "terminated", "resigned", "suspended", "left"}

bearer_scheme = HTTPBearer(auto_error=False)


# ---------- passwords (never store the real password, only a salted hash) ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)  # constant-time compare
    except (ValueError, TypeError):
        return False


# ---------- roles ----------

def role_key(role_name: str | None) -> str:
    """Turn the ROLE.Role_Name text into a fixed key the code can rely on, so a small
    spelling difference in the data ('Fleet Manager' vs 'Fleet manager') can't break access."""
    name = (role_name or "").lower()
    if "fleet" in name:
        return "fleet_manager"
    if "mechanic" in name or "workshop" in name:
        return "mechanic"
    if "site" in name or "engineer" in name:
        return "site_engineer"
    return "unknown"


# ---------- tokens ----------

def create_access_token(employee_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": employee_id, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


def load_user(employee_id: str):
    """Fetch the employee + role fresh from the database (so a deactivated user is
    locked out immediately, not only when their token expires)."""
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'SELECT e."Employee_ID", e."Employee_Name", e."Email", e."Employee_Status", '
                '       e."Password_Hash", r."Role_Name" '
                'FROM "EMPLOYEE" e LEFT JOIN "ROLE" r ON r."Role_ID" = e."Role_ID" '
                'WHERE e."Employee_ID" = %s;',
                (employee_id,),
            )
            return cursor.fetchone()


def public_user(row: dict) -> dict:
    """The safe-to-send version of a user (no password hash)."""
    return {
        "Employee_ID": row["Employee_ID"],
        "Employee_Name": row["Employee_Name"],
        "Email": row["Email"],
        "Role_Name": row["Role_Name"],
        "Role": role_key(row["Role_Name"]),
    }


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    """Dependency: use on any route that needs a signed-in user."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired — please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session — please sign in again.")

    row = load_user(payload.get("sub"))
    if row is None or (row["Employee_Status"] or "").lower() in BLOCKED_STATUSES:
        raise HTTPException(status_code=401, detail="This account is no longer active.")
    return public_user(row)


def require_roles(*allowed_roles: str):
    """Dependency factory: require_roles("fleet_manager") -> only Fleet Managers get in (403 for others)."""

    def checker(user: dict = Depends(get_current_user)):
        if user["Role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Your role is not allowed to do this.",
            )
        return user

    return checker