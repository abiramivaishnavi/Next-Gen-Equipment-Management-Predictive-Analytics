from fastapi import FastAPI
from database import get_connection

app = FastAPI(
    title="Equipment Management System API",
    description="Backend API for the EMS internship project",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Equipment Management System API is running"
    }


@app.get("/db-test")
def database_test():
    connection = get_connection()

    cursor = connection.cursor()
    cursor.execute("SELECT current_database();")

    database_name = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return {
        "message": "Database connection successful",
        "database": database_name
    }