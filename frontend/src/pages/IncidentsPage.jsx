import EntityPage from "../components/EntityPage";

const incidentsConfig = {
    title: "Incidents",
    endpoint: "/incidents/",
    idField: "Incident_ID",
    columns: [
        { name: "Incident_ID", label: "Incident ID", editable: false },
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
        { name: "Incident_Date", label: "Incident Date", type: "date", required: true },
        { name: "Incident_Time", label: "Incident Time (approx.)", type: "time", required: true },
        {
            name: "Incident_Type",
            label: "Incident Type",
            type: "choice",
            required: true,
            options: ["Safety Violation", "Near Miss", "Equipment Tip-Over Risk", "Minor Collision", "Property Damage"],
            allowOther: true,
            otherPlaceholder: "Describe the incident type",
        },
        {
            name: "Severity",
            label: "Severity",
            type: "choice",
            required: true,
            options: ["Minor", "Major", "Critical"],
        },
        { name: "Description", label: "Description", type: "textarea" },
    ],
};

function IncidentsPage() {
    return <EntityPage config={incidentsConfig} />;
}

export default IncidentsPage;