import EntityPage from "../components/EntityPage";

const maintenanceConfig = {
    title: "Maintenance",
    endpoint: "/maintenance/",
    idField: "Maintenance_ID",
    columns: [
        { name: "Maintenance_ID", label: "Maintenance ID", editable: false },
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
                { name: "Current_Project_ID", label: "Project" },
            ],
        },
        { name: "Service_Date", label: "Service Date", type: "date", required: true },
        {
            name: "Maintenance_Type",
            label: "Maintenance Type",
            type: "choice",
            required: true,
            options: ["Routine Service", "Filter Replacement", "Inspection", "Oil Change"],
        },
        { name: "Meter_Reading", label: "Meter Reading", type: "number" },
        { name: "Service_Details", label: "Service Details", type: "text" },
        { name: "Next_Service_Date", label: "Next Service Date", type: "date" },
        { name: "Total_Cost", label: "Total Cost (SAR)", type: "number" },
    ],
};

function MaintenancePage() {
    return <EntityPage config={maintenanceConfig} />;
}

export default MaintenancePage;