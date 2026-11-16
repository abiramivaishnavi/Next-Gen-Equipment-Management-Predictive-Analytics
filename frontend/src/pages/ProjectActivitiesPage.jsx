import EntityPage from "../components/EntityPage";

// Planned activities of a project (the basis for fuel forecasting). Project is picked from a list.
const activitiesConfig = {
    title: "Project Activity",
    endpoint: "/project-activities/",
    idField: "Activity_ID",
    columns: [
        { name: "Activity_ID", label: "Activity ID", editable: false },
        {
            name: "Project_ID",
            label: "Project ID",
            type: "select",
            required: true,
            optionsEndpoint: "/projects/",
            optionValue: (item) => item.Project_ID,
            optionLabel: (item) => `${item.Project_ID} - ${item.Project_Name}`,
            profileFields: [{ name: "Location", label: "Location" }],
        },
        { name: "Activity_Name", label: "Activity Name", required: true },
        { name: "Start_Date", label: "Start Date", type: "date", required: true },
        { name: "End_Date", label: "End Date", type: "date" },
        { name: "Expected_Intensity", label: "Expected Intensity" },
    ],
};

function ProjectActivitiesPage() {
    return <EntityPage config={activitiesConfig} />;
}

export default ProjectActivitiesPage;
