import { Link } from "react-router-dom";

// Every register that has a searchable "all records" page.
const REGISTERS = [
    { key: "equipment", label: "Equipment", desc: "Asset registry: type, manufacturer, status, project." },
    { key: "fuel-logs", label: "Fuel Logs", desc: "Diesel issued to each machine, with cost." },
    { key: "utilization-logs", label: "Utilization Logs", desc: "Operating hours per machine and project." },
    { key: "incidents", label: "Incidents", desc: "Accidents, near misses and safety events." },
    { key: "maintenance", label: "Maintenance", desc: "Scheduled service records and next service dates." },
    { key: "breakdowns", label: "Breakdowns", desc: "Unscheduled failures and downtime." },
    { key: "repairs", label: "Repairs", desc: "Repairs, parts replaced and labour hours." },
    { key: "transfers", label: "Transfers", desc: "Equipment moves between project sites." },
];

/** Reports page: pick a register, then search, filter and download it. */
function RecordsHubPage() {
    return (
        <div className="hub-grid">
            {REGISTERS.map((r) => (
                <Link key={r.key} to={`/records/${r.key}`} className="hub-card">
                    <div className="hub-title">{r.label}</div>
                    <div className="hub-desc">{r.desc}</div>
                    <div className="hub-go">Search &amp; download &rarr;</div>
                </Link>
            ))}
        </div>
    );
}

export default RecordsHubPage;
