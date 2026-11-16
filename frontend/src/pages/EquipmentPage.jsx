import EntityPage from "../components/EntityPage";

const equipmentConfig = {
    title: "Equipment",
    endpoint: "/equipment/",
    idField: "Equipment_ID",
    columns: [
        { name: "Equipment_ID", label: "Equipment ID", type: "text", required: true },
        { name: "Equipment_Type", label: "Type", type: "text", required: true },
        { name: "Equipment_Name", label: "Equipment Name", type: "text", required: true },
        { name: "Manufacturer", label: "Manufacturer", type: "text" },
        { name: "Model", label: "Model", type: "text" },
        { name: "Manufacturing_Year", label: "Manufacturing Year", type: "number", required: true },
        { name: "Fuel_Type", label: "Fuel Type", type: "text", required: true },
        { name: "Capacity", label: "Capacity", type: "number" },
        { name: "Purchase_Date", label: "Purchase Date", type: "date" },
        { name: "Current_Project_ID", label: "Current Project", editable: false },
        { name: "Current_Status", label: "Status", type: "text", required: true },
    ],
};

function EquipmentPage() {
    return <EntityPage config={equipmentConfig} />;
}

export default EquipmentPage;