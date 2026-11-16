import EntityPage from "../components/EntityPage";

const breakdownsConfig = {
    title: "Breakdowns",
    endpoint: "/breakdowns/",
    idField: "Breakdown_ID",
    columns: [
        { name: "Breakdown_ID", label: "Breakdown ID", editable: false },
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
        { name: "Breakdown_Date", label: "Breakdown Date", type: "date", required: true },
        { name: "Description", label: "Description", type: "text" },
        { name: "Downtime_Hours", label: "Downtime Hours", type: "number" },
        { name: "Breakdown_Status", label: "Status", type: "text", required: true },
    ],
};

function BreakdownsPage() {
    return <EntityPage config={breakdownsConfig} />;
}

export default BreakdownsPage;