import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";

const num = (v, d = 0) => Number(v).toLocaleString("en-US", { maximumFractionDigits: d });
const RECORDS = [
    ["fuel-logs", "Fuel Logs"], ["utilization-logs", "Utilization Logs"], ["maintenance", "Maintenance"],
    ["breakdowns", "Breakdowns"], ["repairs", "Repairs"], ["incidents", "Incidents"], ["equipment", "Equipment"],
];

/** Fleet Manager: how each project is running + the maintenance picture (wireframe 17). */
export default function OperationalPage() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        apiClient
            .get("/overview/operational")
            .then((r) => setData(r.data))
            .catch((e) => setError(e.response?.data?.detail || "Can't reach the server. Is the backend running?"));
    }, []);

    if (error) return <p className="form-error">{error}</p>;
    if (!data) return <p className="card-sub">Loading...</p>;
    const { windows: w, projects, maintenance: m } = data;

    return (
        <div>
            <div className="kpi-grid">
                <div className="kpi">
                    <div className="kpi-label">Services overdue</div>
                    <div className="kpi-value">{m.services_overdue}</div>
                    <span className={`pill ${m.services_overdue ? "pill-bad" : "pill-ok"}`}>{m.services_due_soon} more due in {m.due_soon_days} days</span>
                </div>
                <div className="kpi">
                    <div className="kpi-label">Unresolved breakdowns</div>
                    <div className="kpi-value">{m.breakdowns_unresolved}</div>
                    <span className="pill pill-neutral">
                        {m.breakdowns_unresolved
                            ? `${m.breakdowns_unresolved - m.breakdowns_under_repair} open \u00b7 ${m.breakdowns_under_repair} under repair`
                            : "Nothing unresolved"}
                    </span>
                </div>
                <div className="kpi">
                    <div className="kpi-label">Servicing, last {w.cost_days} days</div>
                    <div className="kpi-value">SAR {num(m.service_cost_90d)}</div>
                    <span className="pill pill-neutral">scheduled services</span>
                </div>
                <div className="kpi">
                    <div className="kpi-label">Repairs, last {w.cost_days} days</div>
                    <div className="kpi-value">SAR {num(m.repair_cost_90d)}</div>
                    <span className="pill pill-neutral">parts + labour</span>
                </div>
            </div>

            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">By project</h3>
                        <div className="card-sub">
                            Usage and fuel cover the last {w.days} days up to the newest entries
                            ({w.usage_to ? `usage to ${w.usage_to}` : "no usage logged"}{w.fuel_to ? `, fuel to ${w.fuel_to}` : ""}).
                        </div>
                    </div>
                </div>
                <div className="table-scroll">
                    <table>
                        <thead>
                            <tr><th>Project</th><th>Status</th><th>Units</th><th>Under repair</th><th>Unresolved breakdowns</th><th>Operating hours</th><th>Fuel (L)</th><th>Electric (kWh)</th><th>Fuel cost (SAR)</th></tr>
                        </thead>
                        <tbody>
                            {projects.map((p) => (
                                <tr key={p.Project_ID}>
                                    <td>{p.Project_ID} - {p.Project_Name}</td>
                                    <td>{p.Project_Status}</td>
                                    <td>{p.units}</td>
                                    <td className={p.under_repair ? "tone-warn" : ""}>{p.under_repair}</td>
                                    <td className={p.open_breakdowns ? "tone-bad" : ""}>{p.open_breakdowns}</td>
                                    <td>{num(p.util_hours, 1)}</td>
                                    <td>{num(p.fuel_litres)}</td>
                                    <td>{num(p.fuel_kwh)}</td>
                                    <td>{num(p.fuel_cost, 2)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {projects.length === 0 && <div className="empty-row">No projects yet.</div>}
                </div>
            </div>

            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">Full records</h3>
                        <div className="card-sub">Search, filter and download the data behind these numbers.</div>
                    </div>
                </div>
                <div className="form-body" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <Link to="/manage-projects" className="btn-link" style={{ border: "1px solid var(--ems-border)", borderRadius: 8, padding: "8px 14px" }}>
                        Manage projects &rarr;
                    </Link>
                    {RECORDS.map(([key, label]) => (
                        <Link key={key} to={`/records/${key}`} className="btn-link" style={{ border: "1px solid var(--ems-border)", borderRadius: 8, padding: "8px 14px" }}>
                            {label} &rarr;
                        </Link>
                    ))}
                </div>
            </div>
        </div>
    );
}
