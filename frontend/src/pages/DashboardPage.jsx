import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";

// The "quick action" buttons on each role's dashboard (as in the mock-ups).
const QUICK_ACTIONS = {
    site_engineer: [
        { label: "Record Fuel", to: "/fuel-logs", icon: "fuel" },
        { label: "Log an Incident", to: "/incidents", icon: "shield" },
        { label: "Log Operating Hours", to: "/utilization-logs", icon: "clock" },
        { label: "Request Equipment Transfer", to: "/transfers", icon: "transfer" },
    ],
    mechanic: [
        { label: "Log a Service", to: "/maintenance", icon: "tool" },
        { label: "Report a Breakdown", to: "/breakdowns", icon: "alert" },
        { label: "Log a Repair", to: "/repairs", icon: "tool" },
    ],
    fleet_manager: [
        { label: "Approve Transfer Requests", to: "/transfer-approvals", icon: "transfer", countKey: "pending_count" },
        { label: "Maintain Fuel Rates", to: "/fuel-rates", icon: "rate" },
        { label: "Manage Employees", to: "/employees", icon: "users" },
    ],
};

function Kpi({ item }) {
    return (
        <div className="kpi">
            <div className="kpi-head">
                <div className="kpi-label">{item.label}</div>
                {item.icon && <Icon name={item.icon} size={16} />}
            </div>
            <div className="kpi-value">{item.value}</div>
            <span className={`pill pill-${item.tone || "neutral"}`}>{item.sub}</span>
        </div>
    );
}

function Panel({ panel }) {
    if (!panel) return null;
    return (
        <div className="panel">
            <h3>{panel.title}</h3>
            {panel.rows.length === 0 && <p className="panel-empty">No data yet.</p>}

            {panel.type === "bars" &&
                panel.rows.map((r) => (
                    <div className="bar-row" key={r.label}>
                        <div className="bar-head">
                            <span>{r.label}</span>
                            <span>{r.value}</span>
                        </div>
                        <div className="bar-track">
                            <div className={`bar-fill fill-${r.tone}`} style={{ width: `${r.pct}%` }} />
                        </div>
                    </div>
                ))}

            {panel.type === "table" && panel.rows.length > 0 && (
                <table>
                    <thead>
                        <tr>
                            {panel.columns.map((c) => (
                                <th key={c}>{c}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {panel.rows.map((row, i) => (
                            <tr key={i}>
                                {row.map((cell, j) => (
                                    <td key={j}>{cell}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
}

/**
 * Landing page after login — one per role (wireframes 2, 10 and 15).
 * All numbers come from GET /dashboard/summary, which looks at who is signed in.
 */
function DashboardPage() {
    const { user } = useAuth();
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        apiClient
            .get("/dashboard/summary")
            .then((res) => setData(res.data))
            .catch((err) => setError(err.response?.data?.detail || "Could not load the dashboard."));
    }, []);

    const actions = QUICK_ACTIONS[user.Role] || [];

    if (error) return <p className="login-error">{error}</p>;
    if (!data) return <p>Loading dashboard...</p>;

    return (
        <div>

            <div className="kpi-grid">
                {data.kpis.map((k) => (
                    <Kpi key={k.label} item={k} />
                ))}
            </div>

            <div className="dash-grid">
                <div className="dash-col">
                    <div className="panel">
                        <h3>{data.alerts_title}</h3>
                        {data.alerts.length === 0 && <p className="panel-empty">Nothing needs attention right now.</p>}
                        {data.alerts.map((a, i) => (
                            <div key={i} className={`alert alert-${a.tone}`}>
                                <div>
                                    <div className="alert-title">{a.title}</div>
                                    <div className="alert-detail">{a.detail}</div>
                                </div>
                                <span className={`badge badge-${a.tone}`}>{a.badge}</span>
                            </div>
                        ))}
                    </div>

                    <div className="panel">
                        <h3>{data.recent.title}</h3>
                        {data.recent.rows.length === 0 && <p className="panel-empty">Nothing to show yet.</p>}
                        {data.recent.rows.map((r, i) => (
                            <div className="recent-row" key={i}>
                                <div>
                                    <div className="recent-title">{r.title}</div>
                                    <div className="recent-detail">{r.detail}</div>
                                </div>
                                <div className="recent-right">{r.right}</div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="dash-col">
                    <div className="panel">
                        <h3>Quick actions</h3>
                        {actions.map((a) => (
                            <Link key={a.to} to={a.to} className="action-link">
                                <Icon name={a.icon} size={17} />
                                {a.label}
                                {a.countKey && data[a.countKey] > 0 && (
                                    <span className="action-count">{data[a.countKey]} pending</span>
                                )}
                            </Link>
                        ))}
                    </div>
                    <Panel panel={data.panel} />
                </div>
            </div>
        </div>
    );
}

export default DashboardPage;
