/**
 * Small per-page tweaks that are applied on top of a page's own config, matched by endpoint and
 * column name. If a column below doesn't exist in a page's config it is simply ignored.
 *
 *  autoid : the ID is generated for you (shown read-only; the server's next free number is
 *           fetched again right before saving, so two people can't pick the same one)
 *  combo  : a text box with suggestions taken from values already used in the database, so
 *           "loader", "Loader" and "Wheel Loader" don't end up as three different categories.
 *           New values are still allowed.
 *           pricedKey: name of a list in the same response; a typed value that is not in that list
 *           gets the warning "No fuel price set for ..." (used for Fuel Type).
 *  unitFrom / unitSourceField : the number's unit depends on the machine picked in another column
 *           (Fuel Consumed = litres for diesel/petrol, kWh for electric).
 *  defaultValue : value a NEW entry starts with.
 *  displayLookup : { endpoint, key, text } - a read-only ID field also shows a name next to it,
 *           e.g. Project_ID "PRJ-010" is shown as "PRJ-010 - Highway Section B" (display only; the ID is what is saved).
 *  unitOnly : a table-only column that shows the unit (litres / kWh) of the machine in the row.
 */

// Today as YYYY-MM-DD in the user's own time zone - the latest date a log entry may have.
function localToday() {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Unit of a fuel amount, by fuel type. Same rule as backend/fuel_units.py. */
export function fuelUnit(fuelType) {
    const name = String(fuelType || "").trim().toLowerCase();
    if (["diesel", "petrol", "gasoline"].includes(name)) return "litres";
    if (["electric", "electricity"].includes(name)) return "kWh";
    return "units";
}

export const CAPACITY_UNITS = ["tonnes", "m3", "kW", "litres"];

// The project a NEW machine starts on (optional; only Active / On Hold projects). Shown when adding only -
// after that, moving a machine to another project is a Transfer request that the Fleet Manager approves.
const START_PROJECT_COLUMN = {
    editable: true, addOnly: true, type: "select", label: "Current Project", required: false,
    optionsEndpoint: "/projects/",
    optionValue: (p) => p.Project_ID,
    optionLabel: (p) => `${p.Project_ID} - ${p.Project_Name}`,
    optionFilter: (p) => ["Active", "On Hold"].includes(p.Project_Status),
};

export const OVERRIDES = {
    "/equipment/": {
        Equipment_ID: { type: "autoid", nextIdEndpoint: "/records/equipment/next-id" },
        Equipment_Type: { type: "combo", optionsEndpoint: "/records/equipment/choices", optionsKey: "Equipment_Type" },
        Manufacturer: { type: "combo", optionsEndpoint: "/records/equipment/choices", optionsKey: "Manufacturer" },
        Fuel_Type: {
            type: "combo", optionsEndpoint: "/records/equipment/choices", optionsKey: "Fuel_Type",
            pricedKey: "Fuel_Type_Priced",
        },
        Current_Status: { type: "combo", optionsEndpoint: "/records/equipment/choices", optionsKey: "Current_Status" },
        // A machine cannot be built or bought in the future (the server also checks that the purchase date is
        // not before the manufacturing year).
        get Manufacturing_Year() { return { max: new Date().getFullYear() }; },
        get Purchase_Date() { return { max: localToday() }; },
        Current_Project_ID: START_PROJECT_COLUMN,
    },
};

// New columns that are inserted right after an existing one: { endpoint: { afterColumn: [column, ...] } }
const ADD_AFTER = {
    "/equipment/": {
        Purchase_Date: [{ name: "Current_Project_ID", ...START_PROJECT_COLUMN }], // only if the page doesn't list it
        Capacity: [
            { name: "Capacity_Unit", label: "Capacity Unit", type: "choice", options: CAPACITY_UNITS, required: false, defaultValue: "tonnes" },
        ],
    },
    // Unit (litres / kWh) as its own table column, right after the amount. Not part of the form.
    "/fuel-logs/": {
        Fuel_Consumed: [
            { name: "Fuel_Unit", label: "Unit", editable: false, unitOnly: true, unitFrom: "Equipment_ID", unitSourceField: "Fuel_Type" },
        ],
    },
};

// Incident time is a best guess by the person reporting, so say so on the form.
// IDs typed by hand are turned into capitals as you type (prj-002 -> PRJ-002).
OVERRIDES["/projects/"] = { Project_ID: { uppercase: true } };
OVERRIDES["/incidents/"] = { Incident_Time: { label: "Incident Time (approx.)" } };

// Entries cannot be dated in the future (the server also checks this, plus "before the machine arrived").
// Fuel_Consumed shows the unit of the machine's fuel type.
// The project field also shows the project NAME, the cost header says the currency, and the table gets a Unit column.
OVERRIDES["/fuel-logs/"] = {
    get Fuel_Date() { return { max: localToday() }; },
    Fuel_Consumed: { label: "Fuel Consumed", unitFrom: "Equipment_ID", unitSourceField: "Fuel_Type" },
    Project_ID: { displayLookup: { endpoint: "/projects/", key: "Project_ID", text: (p) => p.Project_Name } },
    Fuel_Cost: { label: "Fuel Cost (SAR)" },
};
OVERRIDES["/utilization-logs/"] = {
    get Log_Date() { return { label: "Week Of (log date)", max: localToday() }; },
};

// Planned work: intensity is one of three fixed values (the fuel forecast groups by it), and a plan can only
// be added to a project that is still running (Active or On Hold).
export const OPEN_PROJECT_STATUSES = ["Active", "On Hold"];
OVERRIDES["/project-activities/"] = {
    Expected_Intensity: { type: "choice", options: ["Low", "Medium", "High"], required: true },
    Project_ID: {
        optionFilter: (p) => OPEN_PROJECT_STATUSES.includes(p.Project_Status),
        // so the engineer sees which machines are at the project while planning its work
        relatedList: {
            endpoint: "/equipment/", matchField: "Current_Project_ID", title: "Machines at this project",
            label: (e) => `${e.Equipment_ID} ${e.Equipment_Type || ""}`.trim(),
        },
    },
};

// Fuel prices are per litre for diesel/petrol and per kWh for electricity.
// Fuel Type: pick from the types already used (machines + earlier prices), or type a new one.
OVERRIDES["/fuel-rates/"] = {
    Fuel_Type: { type: "combo", optionsEndpoint: "/records/equipment/choices", optionsKey: "Fuel_Type" },
    Rate_Per_Liter: { label: "Rate per unit (SAR per litre / kWh)" },
};

// Service entries cannot be dated in the future (the server also checks this, plus "not before purchase").
// Meter reading is the machine's engine-hours counter at the time of the service.
OVERRIDES["/maintenance/"] = {
    get Service_Date() { return { max: localToday() }; },
    Meter_Reading: { label: "Meter reading (engine hours)" },
};

// Breakdown status is one of three fixed values, so nobody can type "under repair" / "Under repair" / "UR".
OVERRIDES["/breakdowns/"] = {
    Breakdown_Status: { type: "choice", options: ["Open", "Under Repair", "Resolved"], required: true },
};

// Equipment dropdowns also show the project the machine is on now: "EQ-008 - Dozer · PRJ-010".
// Handy when several machines have the same type. Only the dropdown changes: in the table the plain label is kept
// (`tableLabel`), because a machine's CURRENT project says nothing about where an old entry was made.
function withProjectInEquipmentLabel(col) {
    if (col.type !== "select" || col.name !== "Equipment_ID" || !String(col.optionsEndpoint || "").startsWith("/equipment")) {
        return col;
    }
    const base = col.optionLabel;
    return {
        ...col,
        tableLabel: col.tableLabel || base,
        optionLabel: (item) => {
            const text = base(item);
            const project = item.Current_Project_ID;
            return project && !String(text).includes(project) ? `${text} · ${project}` : text;
        },
    };
}

export function applyOverrides(endpoint, columns) {
    const extra = OVERRIDES[endpoint];
    const added = ADD_AFTER[endpoint];
    const changed = extra ? columns.map((col) => (extra[col.name] ? { ...col, ...extra[col.name] } : col)) : columns;
    if (!added) return changed.map(withProjectInEquipmentLabel);
    const result = [];
    changed.forEach((col) => {
        result.push(col);
        // only add a column the page doesn't already define
        (added[col.name] || []).forEach((n) => {
            if (!changed.some((c) => c.name === n.name)) result.push(n);
        });
    });
    return result.map(withProjectInEquipmentLabel);
}
