import EntityPage from "../components/EntityPage";

const rolesConfig = {
    title: "Roles",
    endpoint: "/roles/",
    idField: "Role_ID",
    columns: [
        { name: "Role_ID", label: "Role ID", editable: false },
        { name: "Role_Name", label: "Role Name", type: "text", required: true },
        { name: "Role_Description", label: "Description", type: "text" },
    ],
};

function RolesPage() {
    return <EntityPage config={rolesConfig} />;
}

export default RolesPage;