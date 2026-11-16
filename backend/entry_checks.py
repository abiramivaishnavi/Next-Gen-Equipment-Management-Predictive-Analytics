"""
Date checks for Fuel and Utilization entries, so a wrong date is refused with a clear message instead of
being saved. Rules (all must pass):
  1. the date is not in the future
  2. the date is not before the machine was purchased (when a purchase date is recorded)
  3. the date is not before the machine ARRIVED at its current project: the latest Approved/Completed
     transfer's Effective_Transfer_Date (Request_Date if that is empty). A machine that was never
     transferred has no such limit.

Rule 3 is what stops a backdated entry from being saved against the machine's CURRENT project when the
machine was somewhere else on that date.

Callers run this only when an entry is created, or its date / machine is changed - so editing the litres or
hours of an old row (without touching its date) always stays possible.
"""

from datetime import date

from fastapi import HTTPException


def check_entry_date(cursor, equipment_id: str, entry_date: date, what: str, verb: str = "added"):
    """what = 'Fuel' or 'Operating-hours' (used in the message); verb = 'added' or 'saved'."""
    today = date.today()
    if entry_date > today:
        raise HTTPException(
            status_code=400,
            detail=f"{what} date {entry_date} is in the future. Entry not {verb}.",
        )

    cursor.execute(
        'SELECT "Purchase_Date", "Current_Project_ID" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;',
        (equipment_id,),
    )
    machine = cursor.fetchone()
    if machine is None:
        raise HTTPException(status_code=400, detail="Invalid Equipment_ID")

    purchased = machine["Purchase_Date"]
    if purchased and entry_date < purchased:
        raise HTTPException(
            status_code=400,
            detail=f"{what} date {entry_date} is before {equipment_id} was purchased ({purchased}). Entry not {verb}.",
        )

    cursor.execute(
        'SELECT "To_Project_ID", COALESCE("Effective_Transfer_Date", "Request_Date") AS arrived '
        'FROM "TRANSFER" WHERE "Equipment_ID" = %s AND "Transfer_Status" IN (\'Approved\', \'Completed\') '
        'ORDER BY COALESCE("Effective_Transfer_Date", "Request_Date") DESC, "Transfer_ID" DESC LIMIT 1;',
        (equipment_id,),
    )
    arrival = cursor.fetchone()
    if arrival and arrival["arrived"] and entry_date < arrival["arrived"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{what} date {entry_date} is before {equipment_id} arrived at {arrival['To_Project_ID']} "
                f"({arrival['arrived']}). Entry not {verb}."
            ),
        )


def check_utilization_entry(cursor, equipment_id: str, log_date: date, hours: float, verb: str = "added",
                            exclude_id: int | None = None, check_week: bool = True):
    """Extra checks for Utilization (operating-hours) entries. Rules:
      1. hours are between 0 and 168 (one week has 24 x 7 = 168 hours)
      2. one entry per machine per calendar week (Monday-Sunday), so a week is never counted twice
      3. hours cannot be more than 24 x the days the machine has been at its current project, when it
         arrived less than a week before the log date (arrival day itself is not counted)
    exclude_id = the row being edited (so it is not compared with itself).
    check_week = False when only the hours of an old row are edited (its date/machine did not change)."""
    if hours < 0 or hours > 168:
        raise HTTPException(
            status_code=400,
            detail=f"Operating hours must be between 0 and 168 (a week has 24 x 7 = 168 hours). You entered {hours:g}. Entry not {verb}.",
        )

    if check_week:
        cursor.execute(
            'SELECT "Utilization_ID", "Log_Date", "Operating_Hours" FROM "UTILIZATION_LOG" '
            'WHERE "Equipment_ID" = %s AND date_trunc(\'week\', "Log_Date") = date_trunc(\'week\', %s::date) '
            'AND (%s::int IS NULL OR "Utilization_ID" <> %s::int) LIMIT 1;',
            (equipment_id, log_date, exclude_id, exclude_id),
        )
        clash = cursor.fetchone()
        if clash:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{equipment_id} already has an entry for the week of {log_date} "
                    f"(entry #{clash['Utilization_ID']}, {clash['Log_Date']}, {float(clash['Operating_Hours']):g} h). "
                    f"Only one entry per machine per week - edit that entry instead. Entry not {verb}."
                ),
            )

    cursor.execute(
        'SELECT "To_Project_ID", COALESCE("Effective_Transfer_Date", "Request_Date") AS arrived '
        'FROM "TRANSFER" WHERE "Equipment_ID" = %s AND "Transfer_Status" IN (\'Approved\', \'Completed\') '
        'ORDER BY COALESCE("Effective_Transfer_Date", "Request_Date") DESC, "Transfer_ID" DESC LIMIT 1;',
        (equipment_id,),
    )
    arrival = cursor.fetchone()
    if arrival and arrival["arrived"]:
        days_there = (log_date - arrival["arrived"]).days
        if days_there < 7:
            days_there = max(days_there, 1)
            most = 24 * days_there
            if hours > most:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{equipment_id} arrived at {arrival['To_Project_ID']} on {arrival['arrived']}, so by {log_date} "
                        f"it has been there {days_there} day(s): at most {most} hours (24 h x {days_there}). "
                        f"You entered {hours:g}. Entry not {verb}."
                    ),
                )


def check_service_date(cursor, equipment_id: str, service_date: date, verb: str = "added"):
    """Date check for scheduled-service (Maintenance) records. Rules:
      1. the service date is not in the future (a service that has not happened yet is not a record)
      2. the service date is not before the machine was purchased (when a purchase date is recorded)
    Backdated entries (any past date) are fine - a mechanic may log a service a few days late.
    The 'arrived at current project' rule used for fuel / hours is NOT applied: workshop services can
    happen anywhere, whichever project the machine is on."""
    if service_date > date.today():
        raise HTTPException(
            status_code=400,
            detail=f"Service date {service_date} is in the future. Record not {verb}.",
        )
    cursor.execute('SELECT "Purchase_Date" FROM "EQUIPMENT" WHERE "Equipment_ID" = %s;', (equipment_id,))
    machine = cursor.fetchone()
    if machine is None:
        raise HTTPException(status_code=400, detail="Invalid Equipment_ID")
    purchased = machine["Purchase_Date"]
    if purchased and service_date < purchased:
        raise HTTPException(
            status_code=400,
            detail=f"Service date {service_date} is before {equipment_id} was purchased ({purchased}). Record not {verb}.",
        )
