import { useEffect, useState } from "react";
import apiClient from "../api/client";

const TABS = ["All", "Pending", "Approved", "Rejected", "Cancelled"];

function apiError(err) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
    return err.response ? "Something went wrong." : "Can't reach the server. Is the backend running?";
}

// Status -> pill colour
function StatusPill({ status }) {
    const tone = { Pending: "pill-amber", Approved: "pill-ok", Completed: "pill-ok", Rejected: "pill-bad" }[status] || "pill-neutral";
    return <span className={`pill ${tone}`}>{status}</span>;
}

const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));

/** Small "label: value" line used inside the decision-context panel. */
function Line({ label, value, tone }) {
    return (
        <div className="ctx-line">
            <span className="ctx-label">{label}</span>
            <span className={tone ? `tone-${tone}` : ""}>{fmt(value)}</span>
        </div>
    );
}

/** Everything a Fleet Manager needs to judge one request. */
function ContextPanel({ ctx }) {
    if (!ctx) return <p className="card-sub">Loading details...</p>;
    const { equipment: e, health: h, from_project: f, to_project: t, transfer: tr, flags } = ctx;
    return (
        <div>
            {flags.length > 0 && (
                <ul className="ctx-flags">
                    {flags.map((text) => (
                        <li key={text}>{text}</li>
                    ))}
                </ul>
            )}
            <div className="ctx-grid">
                <div className="ctx-card">
                    <h4>Equipment</h4>
                    <Line label="Machine" value={`${e.Equipment_ID} - ${e.Equipment_Name}`} />
                    <Line label="Type" value={e.Equipment_Type} />
                    <Line label="Make / model" value={[e.Manufacturer, e.Model].filter(Boolean).join(" ") || null} />
                    <Line label="Built" value={e.Manufacturing_Year ? `${e.Manufacturing_Year} (${e.Age_Years} yrs old)` : null} />
                    <Line label="Status" value={e.Current_Status} />
                    <Line label="Now on" value={e.Current_Project_ID} />
                </div>
                <div className="ctx-card">
                    <h4>Condition</h4>
                    <Line label="Breakdowns (all time)" value={h.breakdowns_total} />
                    <Line label="Unresolved now" value={h.breakdowns_open} tone={h.breakdowns_open ? "bad" : "ok"} />
                    <Line label="Total downtime" value={`${h.downtime_hours} h`} />
                    <Line label="Last breakdown" value={h.last_breakdown} />
                    <Line label="Last service" value={h.last_service} />
                    <Line
                        label="Next service"
                        value={h.next_service ? `${h.next_service}${h.service_overdue_days > 0 ? ` (overdue ${h.service_overdue_days} d)` : ""}` : null}
                        tone={h.service_overdue_days > 0 ? "bad" : undefined}
                    />
                    <Line
                        label="Used, last 30 days"
                        value={h.last_log ? `${h.util_hours_30d} h in ${h.util_days_30d} log ${h.util_days_30d === 1 ? "entry" : "entries"} (to ${h.last_log})` : "no utilization logged"}
                    />
                </div>
                <div className="ctx-card">
                    <h4>From: {f ? f.Project_Name : tr.From_Project_ID}</h4>
                    {f && (
                        <>
                            <Line label="Location" value={f.Location} />
                            <Line label="Project status" value={f.Project_Status} />
                            <Line label="Units on site" value={f.Units_On_Site} />
                        </>
                    )}
                    <h4 style={{ marginTop: 12 }}>To: {t ? t.Project_Name : tr.To_Project_ID}</h4>
                    {t && (
                        <>
                            <Line label="Location" value={t.Location} />
                            <Line label="Project status" value={t.Project_Status} />
                            <Line label="Units on site" value={t.Units_On_Site} />
                            {t.Activities.length > 0 && (
                                <div className="ctx-activities">
                                    {t.Activities.map((a) => (
                                        <div key={a.Activity_Name + a.Start_Date}>
                                            {a.Activity_Name} <span className="ctx-label">({fmt(a.Start_Date)} to {fmt(a.End_Date)}, {fmt(a.Expected_Intensity)})</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}
                </div>
                <div className="ctx-card">
                    <h4>Request</h4>
                    <Line label="Requested by" value={tr.Requested_By_Name} />
                    <Line label="Date" value={tr.Request_Date} />
                    <Line label="Reason / notes" value={tr.Transfer_Notes} />
                    {tr.Transfer_Status !== "Pending" && (
                        <>
                            <Line label="Decision" value={`${tr.Transfer_Status} by ${fmt(tr.Approved_By_Name)}`} />
                            {tr.Rejection_Reason && <Line label="Rejection reason" value={tr.Rejection_Reason} />}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

/**
 * The transfer queue, with All / Pending / Approved / Rejected / Cancelled tabs.
 *   mode="mine"    : a Site Engineer's own requests (shows the decision and reason; a Pending one can be cancelled)
 *   mode="approve" : the Fleet Manager's queue: inline Approve / Reject, click a row for full details
 * The server decides what each role may see; this component just draws it.
 */
function TransferQueue({ mode, initialTab = "All", refreshKey = 0 }) {
    const approve = mode === "approve";
    const [tab, setTab] = useState(initialTab);
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState(null);
    const [actionError, setActionError] = useState(null);
    const [openId, setOpenId] = useState(null);
    const [contexts, setContexts] = useState({});
    const [rejectingId, setRejectingId] = useState(null);
    const [reason, setReason] = useState("");
    const [busy, setBusy] = useState(false);

    const load = () => {
        setLoading(true);
        apiClient
            .get("/transfers/queue", { params: { status: tab } })
            .then((res) => {
                setData(res.data);
                setError(null);
            })
            .catch((err) => setError(apiError(err)))
            .finally(() => setLoading(false));
    };

    useEffect(load, [tab, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

    const toggleRow = (id) => {
        if (!approve) return;
        const next = openId === id ? null : id;
        setOpenId(next);
        if (next && !contexts[next]) {
            apiClient
                .get(`/transfers/${next}/context`)
                .then((res) => setContexts((prev) => ({ ...prev, [next]: res.data })))
                .catch((err) => setActionError(apiError(err)));
        }
    };

    const done = (text) => {
        setMessage(text);
        setActionError(null);
        setRejectingId(null);
        setReason("");
        setOpenId(null);
        setContexts({});
        load();
        window.dispatchEvent(new Event("ems-data-changed")); // refresh the sidebar badge
    };

    const handleApprove = (t) => {
        setMessage(null);
        setActionError(null);
        if (!window.confirm(`Approve moving ${t.Equipment_ID} from ${t.From_Project_ID} to ${t.To_Project_ID}?`)) return;
        setBusy(true);
        apiClient
            .post(`/transfers/${t.Transfer_ID}/approve`)
            .then(() => done(`Transfer #${t.Transfer_ID} approved - ${t.Equipment_ID} is now on ${t.To_Project_ID}.`))
            .catch((err) => {
                setActionError(apiError(err));
                load(); // someone else may have decided it first - show the current state
                window.dispatchEvent(new Event("ems-data-changed"));
            })
            .finally(() => setBusy(false));
    };

    // Site Engineer: withdraw my own request while it is still Pending.
    const handleCancel = (t) => {
        setMessage(null);
        setActionError(null);
        if (!window.confirm(`Cancel your request to move ${t.Equipment_ID} to ${t.To_Project_ID}?`)) return;
        setBusy(true);
        apiClient
            .post(`/transfers/${t.Transfer_ID}/cancel`)
            .then(() => done(`Request #${t.Transfer_ID} cancelled.`))
            .catch((err) => {
                setActionError(apiError(err));
                load();
            })
            .finally(() => setBusy(false));
    };

    const handleReject = (t) => {
        setMessage(null);
        setActionError(null);
        if (!reason.trim()) return setActionError("Please enter a reason for rejecting this request.");
        setBusy(true);
        apiClient
            .post(`/transfers/${t.Transfer_ID}/reject`, { Rejection_Reason: reason.trim() })
            .then(() => done(`Transfer #${t.Transfer_ID} rejected.`))
            .catch((err) => {
                setActionError(apiError(err));
                load();
            })
            .finally(() => setBusy(false));
    };

    const rows = data?.rows || [];
    const columns = approve ? 8 : 6;

    return (
        <div>
            <div className="tabs" role="tablist">
                {TABS.map((name) => (
                    <button
                        key={name}
                        type="button"
                        role="tab"
                        className={`tab ${tab === name ? "tab-active" : ""}`}
                        onClick={() => { setTab(name); setOpenId(null); setRejectingId(null); }}
                    >
                        {name}
                        {data && <span className="tab-count">{data.counts[name]}</span>}
                    </button>
                ))}
            </div>

            {message && <p className="login-success" style={{ margin: "12px 18px 0" }}>{message}</p>}
            {actionError && <p className="form-error" style={{ margin: "12px 18px 0" }}>{actionError}</p>}
            {error && <p className="form-error" style={{ margin: "12px 18px 0" }}>{error}</p>}

            <div className="table-scroll" style={{ opacity: loading ? 0.55 : 1 }}>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Equipment</th>
                            <th>From &rarr; To</th>
                            {approve && <th>Requested by</th>}
                            <th>{approve ? "Reason" : "Requested"}</th>
                            <th>Status</th>
                            <th>{approve ? "Requested on" : "Decision"}</th>
                            {approve && <th>Actions</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((t) => [
                            <tr
                                key={t.Transfer_ID}
                                className={approve ? "row-click" : ""}
                                onClick={() => toggleRow(t.Transfer_ID)}
                            >
                                <td>{t.Transfer_ID}</td>
                                <td>
                                    {t.Equipment_ID} - {t.Equipment_Name}
                                    <div className="cell-sub">{t.Equipment_Status}</div>
                                </td>
                                <td>
                                    {t.From_Project_ID} &rarr; {t.To_Project_ID}
                                    {t.Is_Stale && <div className="cell-warn">Out of date (now on {t.Current_Project_ID})</div>}
                                </td>
                                {approve && <td>{t.Requested_By_Name}</td>}
                                <td>{approve ? fmt(t.Transfer_Notes) : fmt(t.Request_Date)}</td>
                                <td><StatusPill status={t.Transfer_Status} /></td>
                                {approve ? (
                                    <td>{fmt(t.Request_Date)}</td>
                                ) : (
                                    <td>
                                        {t.Transfer_Status === "Pending" && (
                                            <span className="row-actions">
                                                <span className="cell-sub">Waiting for a Fleet Manager</span>
                                                <button type="button" className="btn-outline" disabled={busy} onClick={() => handleCancel(t)}>
                                                    Cancel request
                                                </button>
                                            </span>
                                        )}
                                        {t.Transfer_Status === "Cancelled" && <span className="cell-sub">Cancelled by you</span>}
                                        {t.Transfer_Status !== "Pending" && t.Transfer_Status !== "Cancelled" && (
                                            <>
                                                {t.Transfer_Status} by {fmt(t.Approved_By_Name)}
                                                {t.Rejection_Reason && <div className="cell-sub">Reason: {t.Rejection_Reason}</div>}
                                            </>
                                        )}
                                    </td>
                                )}
                                {approve && (
                                    <td onClick={(e) => e.stopPropagation()}>
                                        {t.Transfer_Status === "Pending" ? (
                                            <span className="row-actions">
                                                <button
                                                    type="button"
                                                    disabled={busy || t.Is_Stale}
                                                    title={t.Is_Stale ? "The equipment has moved since this request - reject it and ask for a new one" : ""}
                                                    onClick={() => handleApprove(t)}
                                                >
                                                    Approve
                                                </button>
                                                <button
                                                    type="button"
                                                    className="btn-outline"
                                                    disabled={busy}
                                                    onClick={() => {
                                                        setActionError(null);
                                                        setReason("");
                                                        setRejectingId(rejectingId === t.Transfer_ID ? null : t.Transfer_ID);
                                                    }}
                                                >
                                                    Reject
                                                </button>
                                            </span>
                                        ) : (
                                            <span className="cell-sub">{t.Transfer_Status === "Cancelled" ? "Cancelled by requester" : t.Rejection_Reason ? `Reason: ${t.Rejection_Reason}` : "Decided"}</span>
                                        )}
                                    </td>
                                )}
                            </tr>,

                            rejectingId === t.Transfer_ID && (
                                <tr key={`${t.Transfer_ID}-reject`} className="row-extra">
                                    <td colSpan={columns}>
                                        <textarea
                                            placeholder="Reason for rejection (required) - the requester will see this"
                                            value={reason}
                                            maxLength={255}
                                            onChange={(e) => setReason(e.target.value)}
                                            rows={2}
                                            className="reject-box"
                                        />
                                        <span className="row-actions">
                                            <button type="button" disabled={busy} onClick={() => handleReject(t)}>Confirm reject</button>
                                            <button type="button" className="btn-outline" onClick={() => { setRejectingId(null); setReason(""); }}>Cancel</button>
                                        </span>
                                    </td>
                                </tr>
                            ),

                            approve && openId === t.Transfer_ID && (
                                <tr key={`${t.Transfer_ID}-ctx`} className="row-extra">
                                    <td colSpan={columns}>
                                        <ContextPanel ctx={contexts[t.Transfer_ID]} />
                                    </td>
                                </tr>
                            ),
                        ])}
                    </tbody>
                </table>
                {!loading && rows.length === 0 && !error && (
                    <div className="empty-row">
                        {tab === "Pending" ? "No pending requests." : tab === "All" ? "No transfer requests yet." : `No ${tab.toLowerCase()} requests.`}
                    </div>
                )}
            </div>
            {approve && rows.length > 0 && <p className="card-sub" style={{ padding: "0 18px 14px" }}>Click a row to see the equipment's condition, both projects and the reason before deciding.</p>}
        </div>
    );
}

export default TransferQueue;
