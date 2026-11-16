from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import get_connection
from routers import role,employee,project,equipment, transfer, project_activity, utilization_log, fuel_log, incident, maintenance, breakdown, repair, fuel_rate, auth, dashboard
from routers import records

app = FastAPI(
    title="Equipment Management System API",
    description="Backend API for the EMS internship project",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # React dev server, adjust if different
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(role.router)
app.include_router(employee.router)
app.include_router(project.router)
app.include_router(equipment.router)
app.include_router(transfer.router)
app.include_router(project_activity.router)
app.include_router(utilization_log.router)
app.include_router(fuel_log.router)
app.include_router(incident.router)
app.include_router(maintenance.router)
app.include_router(breakdown.router)
app.include_router(repair.router)
app.include_router(fuel_rate.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(records.router)
@app.get("/")
def root():
    return {"message": "Equipment Management System API is running"}


@app.get("/db-test")
def database_test():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            database_name = cursor.fetchone()[0]
    return {"message": "Database connection successful", "database": database_name}