import EntityPage from "../components/EntityPage";

const fuelLogsConfig = {
    title: "Fuel Logs",
    endpoint: "/fuel-logs/",
    idField: "Fuel_Log_ID",
    columns: [
        { name: "Fuel_Log_ID", label: "Fuel Log ID", editable: false },
        {
            name: "Equipment_ID",
            label: "Equipment ID",
            type: "select",
            required: true,
            optionsEndpoint: "/equipment/",
            optionValue: (item) => item.Equipment_ID,
            optionLabel: (item) => `${item.Equipment_ID} - ${item.Equipment_Name}`,
            profileFields: [
                { name: "Equipment_Type", label: "Type" },
                { name: "Current_Status", label: "Status" },
            ],
        },
        {
            name: "Project_ID",
            label: "Project ID",
            type: "derived",
            derivedFrom: "Equipment_ID",
            derivedSourceField: "Current_Project_ID",
            required: true,
        },
        { name: "Fuel_Date", label: "Fuel Date", type: "date", required: true },
        { name: "Fuel_Consumed", label: "Fuel Consumed (litres)", type: "number", required: true },
        { name: "Fuel_Cost", label: "Fuel Cost (SAR, auto)", editable: false },
    ],
};

function FuelLogsPage() {
    return <EntityPage config={fuelLogsConfig} />;
}

export default FuelLogsPage;