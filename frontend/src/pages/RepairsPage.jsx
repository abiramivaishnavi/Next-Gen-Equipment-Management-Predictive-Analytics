import EntityPage from "../components/EntityPage";

const repairsConfig = {
    title: "Repairs",
    endpoint: "/repairs/",
    idField: "Repair_ID",
    columns: [
        { name: "Repair_ID", label: "Repair ID", editable: false },
        {
            name: "Breakdown_ID",
            label: "Breakdown ID",
            type: "select",
            required: true,
            optionsEndpoint: "/breakdowns/",
            optionValue: (item) => item.Breakdown_ID,
            optionLabel: (item) =>
                `#${item.Breakdown_ID} - ${item.Equipment_ID} - ${item.Breakdown_Date} (${item.Breakdown_Status})`,
            profileFields: [
                { name: "Equipment_ID", label: "Equipment" },
                { name: "Breakdown_Date", label: "Breakdown Date" },
                { name: "Breakdown_Status", label: "Status" },
            ],
        },
        { name: "Repair_Date", label: "Repair Date", type: "date", required: true },
        { name: "Parts_Replaced", label: "Parts Replaced", type: "text" },
        { name: "Labor_Hours", label: "Labor Hours", type: "number" },
        { name: "Parts_Cost", label: "Parts Cost (SAR)", type: "number" },
        { name: "Labor_Cost", label: "Labor Cost (SAR)", type: "number" },
        { name: "Repair_Details", label: "Repair Details", type: "text" },
    ],
};

function RepairsPage() {
    return <EntityPage config={repairsConfig} />;
}

export default RepairsPage;