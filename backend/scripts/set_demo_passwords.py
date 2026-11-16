"""
One-off script: give every employee the SAME demo password so the prototype can be
demonstrated. DEMO ONLY - a real deployment would have each person set their own.

Run from the backend folder:
    python scripts/set_demo_passwords.py
    python scripts/set_demo_passwords.py MyOwnDemoPassword     (optional custom password)
"""

import sys
from pathlib import Path

# Let this script import database.py / security.py from the backend folder.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from psycopg.rows import dict_row  # noqa: E402
from database import get_connection  # noqa: E402
from security import hash_password, role_key  # noqa: E402

demo_password = sys.argv[1] if len(sys.argv) > 1 else "Ems@2026"

with get_connection() as connection:
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            'SELECT e."Employee_ID", e."Employee_Name", e."Email", r."Role_Name" '
            'FROM "EMPLOYEE" e LEFT JOIN "ROLE" r ON r."Role_ID" = e."Role_ID" '
            'ORDER BY r."Role_Name", e."Employee_ID";'
        )
        employees = cursor.fetchall()

        for emp in employees:
            cursor.execute(
                'UPDATE "EMPLOYEE" SET "Password_Hash" = %s WHERE "Employee_ID" = %s;',
                (hash_password(demo_password), emp["Employee_ID"]),
            )

print(f"Demo password set for {len(employees)} employees: {demo_password}\n")
print(f"{'Employee':<10} {'Name':<24} {'Role':<22} Email")
for emp in employees:
    print(f"{emp['Employee_ID']:<10} {emp['Employee_Name']:<24} {str(emp['Role_Name']):<22} {emp['Email']}")
print("\nRole keys the app will use:", sorted({role_key(e['Role_Name']) for e in employees}))