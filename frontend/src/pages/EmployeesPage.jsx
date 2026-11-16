import EntityPage from "../components/EntityPage";

const employeesConfig = {
    title: "Employees",
    endpoint: "/employees/",
    idField: "Employee_ID",
    columns: [
        { name: "Employee_ID", label: "Employee ID", type: "text", required: true },
        { name: "Employee_Name", label: "Name", type: "text", required: true },
        { name: "Email", label: "Email", type: "text", required: true },
        { name: "Phone", label: "Phone", type: "text" },
        { name: "Role_ID", label: "Role ID", type: "number", required: true },
        { name: "Employee_Status", label: "Status", type: "text", required: true },
    ],
};

function EmployeesPage() {
    return <EntityPage config={employeesConfig} />;
}

export default EmployeesPage;