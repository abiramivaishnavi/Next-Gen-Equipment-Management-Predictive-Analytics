"""
Keeps EQUIPMENT.Current_Status in step with the breakdown log.

Rule (decided with the project mentor review, item "breakdown <-> machine status"):
  * a machine with at least one UNRESOLVED breakdown (Open / Under Repair) is 'Under Repair'
  * when its last unresolved breakdown is resolved (or deleted) it goes back to 'Active'
  * a 'Decommissioned' machine is never touched

Call sync_machine_status(cursor, equipment_id) from inside the SAME transaction that changed the breakdown,
so the breakdown and the machine can never disagree (both saved, or neither).
"""

UNDER_REPAIR = "Under Repair"
BACK_TO_SERVICE = "Active"


def sync_machine_status(cursor, equipment_id):
    if not equipment_id:
        return
    # Lock the machine row so two mechanics saving at the same moment cannot cross each other.
    cursor.execute(
        'SELECT "Current_Status" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s FOR UPDATE;', (equipment_id,)
    )
    machine = cursor.fetchone()
    if machine is None:
        return
    status = machine["Current_Status"] or ""
    if status.lower() == "decommissioned":
        return

    cursor.execute(
        'SELECT COUNT(*) AS n FROM "BREAKDOWN" '
        'WHERE "Equipment_ID" = %s AND lower("Breakdown_Status") <> \'resolved\';',
        (equipment_id,),
    )
    unresolved = cursor.fetchone()["n"]

    if unresolved > 0 and status != UNDER_REPAIR:
        new_status = UNDER_REPAIR
    elif unresolved == 0 and status.lower() == UNDER_REPAIR.lower():
        new_status = BACK_TO_SERVICE
    else:
        return
    cursor.execute(
        'UPDATE "EQUIPMENT" SET "Current_Status" = %s WHERE "Equipment_ID" = %s;', (new_status, equipment_id)
    )
