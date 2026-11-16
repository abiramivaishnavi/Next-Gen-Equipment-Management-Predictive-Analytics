from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from datetime import date
from psycopg.errors import ForeignKeyViolation, CheckViolation

router = APIRouter(prefix="/project-activities", tags=["Project Activities"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: site_engineer
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("site_engineer"))


class ProjectActivityCreate(BaseModel):
    Project_ID: str
    Activity_Name: str
    Start_Date: date
    End_Date: date | None = None
    Expected_Intensity: str | None = None

    @field_validator("Expected_Intensity")
    @classmethod
    def known_intensity(cls, value):
        # Low / Medium / High only ("high" or " HIGH " are tidied to "High"); blank is allowed for old rows.
        if value is None or not value.strip():
            return None
        tidy = value.strip().capitalize()
        if tidy not in ("Low", "Medium", "High"):
            raise ValueError("Expected_Intensity must be Low, Medium or High")
        return tidy


OPEN_STATUSES = ("Active", "On Hold")


def check_project_is_open(cursor, project_id: str, verb: str):
    """Activities can only be planned for a project that is Active or On Hold."""
    cursor.execute('SELECT "Project_Status" FROM "PROJECT" WHERE "Project_ID" = %s;', (project_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid Project_ID")
    if row["Project_Status"] not in OPEN_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"{project_id} is {row['Project_Status']}. Activities can only be planned for Active or On Hold projects. Activity not {verb}.",
        )


@router.get("/")
def get_project_activity_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "PROJECT_ACTIVITY" ORDER BY "Activity_ID";')
            return cursor.fetchall()


@router.get("/{activity_id}")
def get_project_activity(activity_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "PROJECT_ACTIVITY" WHERE "Activity_ID" = %s;', (activity_id,))
            activity = cursor.fetchone()
            if activity is None:
                raise HTTPException(status_code=404, detail="Project activity not found")
            return activity


@router.post("/", status_code=201)
def create_project_activity(activity: ProjectActivityCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                check_project_is_open(cursor, activity.Project_ID, "added")
                cursor.execute(
                    'INSERT INTO "PROJECT_ACTIVITY" '
                    '("Project_ID", "Activity_Name", "Start_Date", "End_Date", "Expected_Intensity") '
                    'VALUES (%s, %s, %s, %s, %s) RETURNING *;',
                    (
                        activity.Project_ID,
                        activity.Activity_Name,
                        activity.Start_Date,
                        activity.End_Date,
                        activity.Expected_Intensity,
                    )
                )
                return cursor.fetchone()
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: End_Date must be on or after Start_Date"
                )


@router.put("/{activity_id}")
def update_project_activity(activity_id: int, activity: ProjectActivityCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute('SELECT "Project_ID" FROM "PROJECT_ACTIVITY" WHERE "Activity_ID" = %s;', (activity_id,))
                before = cursor.fetchone()
                if before is None:
                    raise HTTPException(status_code=404, detail="Project activity not found")
                # only re-check the project when the activity is moved to another project
                if before["Project_ID"] != activity.Project_ID:
                    check_project_is_open(cursor, activity.Project_ID, "saved")
                cursor.execute(
                    'UPDATE "PROJECT_ACTIVITY" SET '
                    '"Project_ID" = %s, "Activity_Name" = %s, "Start_Date" = %s, '
                    '"End_Date" = %s, "Expected_Intensity" = %s '
                    'WHERE "Activity_ID" = %s RETURNING *;',
                    (
                        activity.Project_ID,
                        activity.Activity_Name,
                        activity.Start_Date,
                        activity.End_Date,
                        activity.Expected_Intensity,
                        activity_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Project activity not found")
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Project_ID")
            except CheckViolation:
                connection.rollback()
                raise HTTPException(
                    status_code=400,
                    detail="Invalid value: End_Date must be on or after Start_Date"
                )


@router.delete("/{activity_id}", status_code=204)
def delete_project_activity(activity_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "PROJECT_ACTIVITY" WHERE "Activity_ID" = %s;', (activity_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project activity not found")