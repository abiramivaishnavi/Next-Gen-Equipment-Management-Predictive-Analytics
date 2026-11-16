from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel
from database import get_connection
from security import get_current_user, require_roles
from datetime import date, time
from psycopg.errors import ForeignKeyViolation

router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Who may use this API (checked on the server, so it also holds if someone skips the screens):
#   read : any signed-in user
#   write: site_engineer
READ_ACCESS = Depends(get_current_user)
WRITE_ACCESS = Depends(require_roles("site_engineer"))


class IncidentCreate(BaseModel):
    Equipment_ID: str
    Project_ID: str
    Incident_Date: date
    Incident_Time: time
    Incident_Type: str
    Incident_Type_Other: str | None = None
    Severity: str
    Description: str | None = None


@router.get("/")
def get_incident_list(user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "INCIDENT" ORDER BY "Incident_ID";')
            return cursor.fetchall()


@router.get("/{incident_id}")
def get_incident(incident_id: int, user: dict = READ_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute('SELECT * FROM "INCIDENT" WHERE "Incident_ID" = %s;', (incident_id,))
            incident = cursor.fetchone()
            if incident is None:
                raise HTTPException(status_code=404, detail="Incident not found")
            return incident


@router.post("/", status_code=201)
def create_incident(incident: IncidentCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'INSERT INTO "INCIDENT" '
                    '("Equipment_ID", "Project_ID", "Incident_Date", "Incident_Time", '
                    '"Incident_Type", "Incident_Type_Other", "Severity", "Description") '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *;',
                    (
                        incident.Equipment_ID,
                        incident.Project_ID,
                        incident.Incident_Date,
                        incident.Incident_Time,
                        incident.Incident_Type,
                        incident.Incident_Type_Other,
                        incident.Severity,
                        incident.Description,
                    )
                )
                return cursor.fetchone()
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")


@router.put("/{incident_id}")
def update_incident(incident_id: int, incident: IncidentCreate, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            try:
                cursor.execute(
                    'UPDATE "INCIDENT" SET '
                    '"Equipment_ID" = %s, "Project_ID" = %s, "Incident_Date" = %s, "Incident_Time" = %s, '
                    '"Incident_Type" = %s, "Incident_Type_Other" = %s, "Severity" = %s, "Description" = %s '
                    'WHERE "Incident_ID" = %s RETURNING *;',
                    (
                        incident.Equipment_ID,
                        incident.Project_ID,
                        incident.Incident_Date,
                        incident.Incident_Time,
                        incident.Incident_Type,
                        incident.Incident_Type_Other,
                        incident.Severity,
                        incident.Description,
                        incident_id,
                    )
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise HTTPException(status_code=404, detail="Incident not found")
                return updated
            except ForeignKeyViolation:
                connection.rollback()
                raise HTTPException(status_code=400, detail="Invalid Equipment_ID or Project_ID")


@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: int, user: dict = WRITE_ACCESS):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM "INCIDENT" WHERE "Incident_ID" = %s;', (incident_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Incident not found")