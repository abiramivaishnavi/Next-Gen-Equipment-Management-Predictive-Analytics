import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import apiClient from "../api/client";

const KIND_PILL = { Service: "pill-ok", Breakdown: "pill-bad", Repair: "pill-amber" };
const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
const money = (v) => (v === null || v === undefined ? "—" : Number(v).toFixed(2));

function apiError(err) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    return err.response ? "Something went wrong." : "Can't reach the server. Is the backend running?";
}

/** Mechanic: the full service + breakdown + repair history of ONE machine (wireframe 14). */
export default function MaintenanceHistoryPage() {
    const [params, setParams] = useSearchParams();
    const [equipment, setEquipment] = useState([]);
    const [equipmentId, setEquipmentId] = useState(params.get("equipment") || "");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        apiClient.get("/equipment/").then((r) => setEquipment(r.data)).catch((e) => setError(apiError(e)));
    }, []);

    useEffect(() => {
        if (!equipmentId) {
            setData(null);
            return;
        }
        setLoading(true);
        setError(null);
        apiClient
            .get(`/history/${equipmentId}`, { params: { date_from: dateFrom || undefined, date_to: dateTo || undefined } })
            .then((r) => setData(r.data))
            .catch((e) => setError(apiError(e)))
            .finally(() => setLoading(false));
    }, [equipmentId, dateFrom, dateTo]);

    const pick = (id) => {
        setEquipmentId(id);
        setParams(id ? { equipment: id } : {});
    };

    const s = data?.summary;
    return (
        <div>
            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">Choose a machine</h3>
                        <div className="card-sub">Everything done to it: scheduled services, breakdowns and repairs, newest first.</div>
                    </div>
                </div>
                <div className="filters">
                    <div className="field">
                        <label className="field-label">Equipment</label>
                        <select value={equipmentId} onChange={(e) => pick(e.target.value)}>
                            <option value="">Select equipment</option>
                            {equipment.map((e) => (
                                <option key={e.Equipment_ID} value={e.Equipment_ID}>{e.Equipment_ID} - {e.Equipment_Name}{e.Current_Project_ID ? ` · ${e.Current_Project_ID}` : ""}</option>
                            ))}
                        </select>
                    </div>
                    <div className="field">
                        <label className="field-label">From date</label>
                        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} disabled={!equipmentId} />
                    </div>
                    <div className="field">
                        <label className="field-label">To date</label>
                        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} disabled={!equipmentId} />
                    </div>
                    <div className="field filters-reset">
                        <button type="button" className="btn-outline" disabled={!dateFrom && !dateTo} onClick={() => { setDateFrom(""); setDateTo(""); }}>
                            Clear dates
                        </button>
                    </div>
                </div>
                {error && <p className="form-error" style={{ margin: "0 18px 14px" }}>{error}</p>}
            </div>

            {!equipmentId && <div className="card-panel"><div className="empty-row">Select a machine to see its history.</div></div>}

            {data && (
                <>
                    <div className="profile-strip" style={{ margin: "0 0 14px" }}>
                        {data.equipment.Equipment_ID} - {data.equipment.Equipment_Name} · {data.equipment.Equipment_Type} · {data.equipment.Current_Status} · on {fmt(data.equipment.Current_Project_ID)}
                    </div>
                    <div className="kpi-grid">
                        <div className="kpi"><div className="kpi-label">Services</div><div className="kpi-value">{s.services}</div></div>
                        <div className="kpi"><div className="kpi-label">Breakdowns</div><div className="kpi-value">{s.breakdowns}</div><span className="pill pill-neutral">{s.downtime_hours} h downtime</span></div>
                        <div className="kpi"><div className="kpi-label">Repairs</div><div className="kpi-value">{s.repairs}</div><span className="pill pill-neutral">{s.labour_hours} labour h</span></div>
                        <div className="kpi"><div className="kpi-label">Total cost (SAR)</div><div className="kpi-value">{money(s.total_cost)}</div></div>
                    </div>
                    <div className="card-panel">
                        <div className="table-scroll" style={{ opacity: loading ? 0.55 : 1 }}>
                            <table>
                                <thead>
                                    <tr><th>Date</th><th>Type</th><th>What</th><th>Details</th><th>Hours</th><th>Cost (SAR)</th><th>Next service</th></tr>
                                </thead>
                                <tbody>
                                    {data.events.map((e, i) => (
                                        <tr key={`${e.kind}-${e.date}-${i}`}>
                                            <td>{fmt(e.date)}</td>
                                            <td><span className={`pill ${KIND_PILL[e.kind] || "pill-neutral"}`}>{e.kind}</span></td>
                                            <td>{e.title}</td>
                                            <td>{fmt(e.detail)}</td>
                                            <td>{fmt(e.hours)}</td>
                                            <td>{money(e.cost)}</td>
                                            <td>{fmt(e.next_date)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {data.events.length === 0 && <div className="empty-row">No history for this machine{dateFrom || dateTo ? " in that date range" : ""}.</div>}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
