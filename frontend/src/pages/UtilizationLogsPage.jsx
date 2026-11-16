import EntityPage from "../components/EntityPage";

// Operating hours of one machine for a period (the sample data holds one weekly total per machine). Equipment is picked from a list (not typed) and the
// project is filled in from the machine's current project, so a log can't point at the wrong site.
const utilizationConfig = {
    title: "Utilization Logs",
    endpoint: "/utilization-logs/",
    idField: "Utilization_ID",
    columns: [
        { name: "Utilization_ID", label: "Utilization ID", editable: false },
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
        { name: "Log_Date", label: "Week Of (log date)", type: "date", required: true },
        { name: "Operating_Hours", label: "Operating Hours (period total, up to 168)", type: "number", required: true, min: 0, max: 168, step: 0.25 },
    ],
};

function UtilizationLogsPage() {
    return <EntityPage config={utilizationConfig} />;
}

export default UtilizationLogsPage;
