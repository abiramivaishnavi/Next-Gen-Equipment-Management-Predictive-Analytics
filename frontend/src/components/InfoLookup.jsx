import { useEffect, useState } from "react";
import apiClient from "../api/client";

const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));

function Line({ label, value, tone }) {
    return (
        <div className="ctx-line">
            <span className="ctx-label">{label}</span>
            <span className={tone ? `tone-${tone}` : ""}>{fmt(value)}</span>
        </div>
    );
}

function apiError(err) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    return err.response ? "Something went wrong." : "Can't reach the server. Is the backend running?";
}

/** One machine: profile + condition. Read-only. */
function EquipmentProfile({ data }) {
    const { equipment: e, health: h } = data;
    return (
        <div className="ctx-grid">
            <div className="ctx-card">
                <h4>{e.Equipment_ID} - {e.Equipment_Name}</h4>
                <Line label="Type" value={e.Equipment_Type} />
                <Line label="Make / model" value={[e.Manufacturer, e.Model].filter(Boolean).join(" ") || null} />
                <Line label="Built" value={e.Manufacturing_Year ? `${e.Manufacturing_Year} (${e.Age_Years} yrs old)` : null} />
                <Line label="Fuel type" value={e.Fuel_Type} />
                <Line label="Capacity" value={e.Capacity != null ? `${e.Capacity} ${e.Capacity_Unit || ""}`.trim() : null} />
                <Line label="Purchased" value={e.Purchase_Date} />
            </div>
            <div className="ctx-card">
                <h4>Where it is</h4>
                <Line label="Status" value={e.Current_Status} />
                <Line label="Project" value={e.Current_Project_ID ? `${e.Current_Project_ID} - ${e.Current_Project_Name || ""}` : "Not assigned"} />
                <Line label="Location" value={e.Current_Project_Location} />
                <Line label="Transfer pending" value={h.pending_transfer_id ? `Yes (#${h.pending_transfer_id})` : "No"} tone={h.pending_transfer_id ? "warn" : undefined} />
            </div>
            <div className="ctx-card">
                <h4>Condition</h4>
                <Line label="Breakdowns (all time)" value={h.breakdowns_total} />
                <Line label="Unresolved now" value={h.breakdowns_open} tone={h.breakdowns_open ? "bad" : "ok"} />
                <Line label="Total downtime" value={`${h.downtime_hours} h`} />
                <Line label="Last service" value={h.last_service} />
                <Line
                    label="Next service"
                    value={h.next_service ? `${h.next_service}${h.service_overdue_days > 0 ? ` (overdue ${h.service_overdue_days} d)` : ""}` : null}
                    tone={h.service_overdue_days > 0 ? "bad" : undefined}
                />
            </div>
            <div className="ctx-card">
                <h4>Recent activity ({h.window_days} days)</h4>
                <Line label="Operating hours" value={h.last_log ? `${h.util_hours} h (to ${h.last_log})` : "none logged"} />
                <Line label="Fuel" value={h.last_fuel ? `${h.fuel_litres} ${h.fuel_unit === "litres" ? "L" : h.fuel_unit} (to ${h.last_fuel})` : "none logged"} />
            </div>
        </div>
    );
}

/**
 * Read-only lookup (mentor item 8): search equipment -> profile, search project -> its equipment.
 * No adding or editing here - data entry happens on the register pages.
 *   mode="information" : one search box over equipment AND projects (both read-only)
 *   mode="projects"    : the project list (all projects shown first), click one to see its equipment
 */
function InfoLookup({ mode }) {
    const projectsOnly = mode === "projects";
    const [q, setQ] = useState("");
    const [appliedQ, setAppliedQ] = useState("");
    const [equipment, setEquipment] = useState([]);
    const [projects, setProjects] = useState([]);
    const [view, setView] = useState(null);       // { type: "equipment" | "project", id }
    const [backTo, setBackTo] = useState(null);   // project id we came from (equipment opened from a project)
    const [detail, setDetail] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    // search (after a short typing pause)
    useEffect(() => {
        if (q === appliedQ) return;
        const t = setTimeout(() => setAppliedQ(q), 300);
        return () => clearTimeout(t);
    }, [q, appliedQ]);

    useEffect(() => {
        setLoading(true);
        setError(null);
        const params = { q: appliedQ || undefined };
        Promise.all([
            apiClient.get("/info/projects", { params }),
            projectsOnly ? Promise.resolve(null) : apiClient.get("/info/equipment", { params }),
        ])
            .then(([p, e]) => {
                setProjects(p ? p.data : []);
                setEquipment(e ? e.data : []);
            })
            .catch((err) => setError(apiError(err)))
            .finally(() => setLoading(false));
    }, [appliedQ, projectsOnly]);

    // details of the selected row
    useEffect(() => {
        if (!view) {
            setDetail(null);
            return;
        }
        setDetail(null);
        const key = `${view.type}:${view.id}`;
        apiClient
            .get(view.type === "equipment" ? `/info/equipment/${view.id}` : `/info/projects/${view.id}`)
            .then((res) => setDetail({ key, data: res.data }))
            .catch((err) => setError(apiError(err)));
    }, [view]);

    const [downloading, setDownloading] = useState(false);

    // Download the open profile as a PDF (the file comes back as a Blob).
    const downloadPdf = () => {
        if (!view) return;
        setDownloading(true);
        setError(null);
        apiClient
            .get(`/info/${view.type === "equipment" ? "equipment" : "projects"}/${view.id}/export`, { responseType: "blob" })
            .then((res) => {
                const url = URL.createObjectURL(res.data);
                const link = document.createElement("a");
                link.href = url;
                link.download = `${view.type}-${view.id}.pdf`;
                link.click();
                URL.revokeObjectURL(url);
            })
            .catch(async (err) => {
                let message = apiError(err);
                try {
                    const body = JSON.parse(await err.response.data.text());
                    if (typeof body.detail === "string") message = body.detail;
                } catch { /* keep the generic message */ }
                setError(message);
            })
            .finally(() => setDownloading(false));
    };

    const ready = Boolean(view && detail && detail.key === `${view.type}:${view.id}`);

    const openEquipment = (id, fromProject = null) => {
        setBackTo(fromProject);
        setView({ type: "equipment", id });
    };

    return (
        <div>
            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">{projectsOnly ? "Find a project" : "Find equipment or a project"}</h3>
                        <div className="card-sub">
                            {projectsOnly
                                ? "Look up a project and the equipment on it. This page is read-only."
                                : "Type an equipment ID, name, type or project - for example eq-007, crane, Apex. Click a project to see the equipment it is using. Read-only."}
                        </div>
                    </div>
                </div>
                <div className="filters" style={{ gridTemplateColumns: "minmax(220px, 480px)" }}>
                    <div className="field">
                        <input
                            type="search"
                            value={q}
                            onChange={(e) => setQ(e.target.value)}
                            placeholder={projectsOnly ? "Search projects..." : "Search equipment or projects..."}
                            autoFocus
                        />
                    </div>
                </div>
                {error && <p className="form-error" style={{ margin: "0 18px 14px" }}>{error}</p>}

                <div className="lookup-lists" style={{ opacity: loading ? 0.6 : 1 }}>
                    {!projectsOnly && (
                        <div>
                            <div className="lookup-title">Equipment ({equipment.length}{equipment.length === 25 ? "+" : ""})</div>
                            {equipment.map((e) => (
                                <button
                                    key={e.Equipment_ID}
                                    type="button"
                                    className={`lookup-row ${view?.type === "equipment" && view.id === e.Equipment_ID ? "lookup-active" : ""}`}
                                    onClick={() => openEquipment(e.Equipment_ID)}
                                >
                                    <strong>{e.Equipment_ID}</strong> {e.Equipment_Name}
                                    <span className="cell-sub">{e.Equipment_Type} · {e.Current_Status} · {e.Current_Project_ID || "no project"}</span>
                                </button>
                            ))}
                            {!loading && equipment.length === 0 && <div className="empty-row">No equipment matches.</div>}
                        </div>
                    )}
                    <div>
                        <div className="lookup-title">Projects ({projects.length})</div>
                        {projects.map((p) => (
                            <button
                                key={p.Project_ID}
                                type="button"
                                className={`lookup-row ${view?.type === "project" && view.id === p.Project_ID ? "lookup-active" : ""}`}
                                onClick={() => { setBackTo(null); setView({ type: "project", id: p.Project_ID }); }}
                            >
                                <strong>{p.Project_ID}</strong> {p.Project_Name}
                                <span className="cell-sub">{fmt(p.Location)} · {fmt(p.Project_Status)} · {p.Units_On_Site} unit(s)</span>
                            </button>
                        ))}
                        {!loading && projects.length === 0 && <div className="empty-row">No projects match.</div>}
                    </div>
                </div>
            </div>

            {view && (
                <div className="card-panel">
                    <div className="card-head">
                        <div>
                            <h3 className="card-title">{view.type === "equipment" ? "Equipment profile" : "Project details"}</h3>
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                            <button type="button" className="btn-outline" disabled={!ready || downloading} onClick={downloadPdf}>
                                {downloading ? "Preparing..." : "Download PDF"}
                            </button>
                        </div>
                        {backTo && (
                            <button type="button" className="btn-outline" onClick={() => { setView({ type: "project", id: backTo }); setBackTo(null); }}>
                                &larr; Back to {backTo}
                            </button>
                        )}
                    </div>
                    <div className="form-body">
                        {/* only show details that belong to the row now selected (avoids a flash of the previous type) */}
                        {!ready && <p className="card-sub">Loading...</p>}
                        {ready && view.type === "equipment" && <EquipmentProfile data={detail.data} />}
                        {ready && view.type === "project" && (
                            <div className="ctx-grid">
                                <div className="ctx-card">
                                    <h4>{detail.data.project.Project_ID} - {detail.data.project.Project_Name}</h4>
                                    <Line label="Location" value={detail.data.project.Location} />
                                    <Line label="Status" value={detail.data.project.Project_Status} />
                                    <Line label="Start" value={detail.data.project.Start_Date} />
                                    <Line label="Expected end" value={detail.data.project.Expected_End_Date} />
                                    <Line label="Units on site" value={detail.data.equipment.length} />
                                    {detail.data.activities.length > 0 && (
                                        <div className="ctx-activities">
                                            <div className="ctx-label">Planned activities</div>
                                            {detail.data.activities.map((a) => (
                                                <div key={a.Activity_Name + a.Start_Date}>
                                                    {a.Activity_Name} <span className="ctx-label">({fmt(a.Start_Date)} to {fmt(a.End_Date)}, {fmt(a.Expected_Intensity)})</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <div className="ctx-card" style={{ gridColumn: "span 2" }}>
                                    <h4>Equipment on this project</h4>
                                    {detail.data.equipment.length === 0 && <p className="card-sub">No equipment is assigned to this project.</p>}
                                    {detail.data.equipment.map((e) => (
                                        <button key={e.Equipment_ID} type="button" className="lookup-row" onClick={() => openEquipment(e.Equipment_ID, view.id)}>
                                            <strong>{e.Equipment_ID}</strong> {e.Equipment_Name}
                                            <span className="cell-sub">{e.Equipment_Type} · {e.Current_Status}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default InfoLookup;
