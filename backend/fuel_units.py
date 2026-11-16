"""
Fuel units in ONE place.

A fuel entry is stored as a plain number (FUEL_LOG.Fuel_Consumed). What that number MEANS depends on the
machine's fuel type:
    Diesel / Petrol  -> litres
    Electric         -> kWh
    anything else    -> "units"   (e.g. a gas type someone typed in - add a rule here when needed)

No database column is needed: the unit follows from EQUIPMENT.Fuel_Type. Adding litres and kWh together would
be meaningless, so the dashboards add up litres for liquid fuels only and show electricity separately.
"""

LIQUID_TYPES = ("diesel", "petrol", "gasoline")
ELECTRIC_TYPES = ("electric", "electricity")

# The same lists as SQL, for queries that join FUEL_LOG to EQUIPMENT (alias e).
LIQUID_SQL = 'lower(e."Fuel_Type") IN (\'diesel\', \'petrol\', \'gasoline\')'
ELECTRIC_SQL = 'lower(e."Fuel_Type") IN (\'electric\', \'electricity\')'


def fuel_kind(fuel_type) -> str:
    """'litres', 'kwh' or 'units'."""
    name = (fuel_type or "").strip().lower()
    if name in LIQUID_TYPES:
        return "litres"
    if name in ELECTRIC_TYPES:
        return "kwh"
    return "units"


def unit_label(fuel_type) -> str:
    """Short text for the unit: 'litres', 'kWh' or 'units'."""
    return {"litres": "litres", "kwh": "kWh", "units": "units"}[fuel_kind(fuel_type)]
