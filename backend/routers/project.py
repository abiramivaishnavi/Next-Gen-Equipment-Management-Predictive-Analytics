from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, field_validator
from database import get_connection
from security import get_current_user, require_roles
from datetime import date
from psycopg.errors import UniqueViolation

router = APIRouter(prefix="/projects", tags=["Projects"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: fleet_manager
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("fleet_manager"))


class ProjectCreate(BaseModel):
    Project_ID: str
    Project_Name: str
    Location: str
    Start_Date: date
    Expected_End_Date: date | None = None
    Project_Status: str

    @field_validator("Project_ID")
    @classmethod
    def tidy_id(cls, value: str) -> str:
        # "prj-002 " and "PRJ-002" must be the same project, so always store capitals without spaces.
        return value.strip().upper()


@router.get("/")
def get_projects(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "PROJECT" ORDER BY "Project_ID";')
            return cursor.fetchall()


@router.get("/{project_id}")
def get_project(project_id: str, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "PROJECT" WHERE "Project_ID" = %s;', (project_id,))
            project = cursor.fetchone()
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found")
            return project


@router.post("/", status_code=201)
def create_project(project: ProjectCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "PROJECT" '
                    '("Project_ID", "Project_Name", "Location", '
                    '"Start_Date", "Expected_End_Date", "Project_Status") '
                    'VALUES (%s, %s, %s, %s, %s, %s) RETURNING *;',
                    (
                        project.Project_ID,
                        project.Project_Name,
                        project.Location,
                        project.Start_Date,
                        project.Expected_End_Date,
                        project.Project_Status,
                    )
                )
                return cursor.fetchone()
            except UniqueViolation:
                connection.rollback()
                raise HTTPException(status_code=409, detail="Project_ID already exists")


@router.put("/{project_id}")
def update_project(project_id: str, project: ProjectCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                'UPDATE "PROJECT" SET "Project_Name" = %s, "Location" = %s, "Start_Date" = %s, '
                '"Expected_End_Date" = %s, "Project_Status" = %s '
                'WHERE "Project_ID" = %s RETURNING *;',
                (
                    project.Project_Name,
                    project.Location,
                    project.Start_Date,
                    project.Expected_End_Date,
                    project.Project_Status,
                    project_id,
                )
            )
            updated = cursor.fetchone()
            if updated is None:
                raise HTTPException(status_code=404, detail="Project not found")
            return updated


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "PROJECT" WHERE "Project_ID" = %s;', (project_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")