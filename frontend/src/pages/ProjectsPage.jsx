import EntityPage from "../components/EntityPage";

const projectsConfig = {
    title: "Projects",
    endpoint: "/projects/",
    idField: "Project_ID",
    columns: [
        { name: "Project_ID", label: "Project ID", type: "text", required: true },
        { name: "Project_Name", label: "Project Name", type: "text", required: true },
        { name: "Location", label: "Location", type: "text" },
        { name: "Start_Date", label: "Start Date", type: "date", required: true },
        { name: "Expected_End_Date", label: "Expected End Date", type: "date" },
        { name: "Project_Status", label: "Status", type: "text", required: true },
    ],
};

function ProjectsPage() {
    return <EntityPage config={projectsConfig} />;
}

export default ProjectsPage;