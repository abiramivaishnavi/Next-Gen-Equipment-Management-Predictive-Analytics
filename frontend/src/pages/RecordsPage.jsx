import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import apiClient from "../api/client";

const PAGE_SIZE = 25;
const EMPTY_FILTERS = { q: "", equipment_id: "", project_id: "", date_from: "", date_to: "" };

// Turn "Fuel_Consumed" into "Fuel Consumed"
const heading = (name) => name.replace(/_/g, " ");

// Show a time as HH:MM and empty values as a dash.
function show(value) {
    if (value === null || value === undefined || value === "") return "—";
    if (/^\d{2}:\d{2}:\d{2}/.test(String(value))) return String(value).slice(0, 5);
    return String(value);
}

// A failed download comes back as a Blob, so read the message out of it.
async function downloadError(err) {
    try {
        const text = await err.response.data.text();
        return JSON.parse(text).detail || "Download failed.";
    } catch {
        return "Download failed. Is the backend running?";
    }
}

/**
 * "All records" page for one register (route: /records/:key, e.g. /records/fuel-logs).
 * The database does the searching, filtering and paging, so it stays fast with thousands of rows.
 */
function RecordsPage() {
    const { key } = useParams();
    const navigate = useNavigate();

    const [filters, setFilters] = useState(EMPTY_FILTERS);
    const [appliedQ, setAppliedQ] = useState(""); // search text after a short typing pause
    const [page, setPage] = useState(1);
    const [data, setData] = useState(null); // { rows, total, label, has_date }
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [downloading, setDownloading] = useState(null);
    const [equipment, setEquipment] = useState([]);
    const [projects, setProjects] = useState([]);
    const requestNumber = useRef(0); // so a slow old answer can't overwrite a newer one

    // New register -> start fresh.
    useEffect(() => {
        setFilters(EMPTY_FILTERS);
        setAppliedQ("");
        setPage(1);
        setData(null);
    }, [key]);

    // Dropdown lists for the filters (small tables, loaded once).
    useEffect(() => {
        apiClient.get("/equipment/").then((r) => setEquipment(r.data)).catch(() => {});
        apiClient.get("/projects/").then((r) => setProjects(r.data)).catch(() => {});
    }, []);

    // Wait a moment after typing before asking the server.
    useEffect(() => {
        if (filters.q === appliedQ) return; // nothing new typed
        const timer = setTimeout(() => {
            setAppliedQ(filters.q);
            setPage(1);
        }, 350);
        return () => clearTimeout(timer);
    }, [filters.q, appliedQ]);

    const params = {
        q: appliedQ || undefined,
        equipment_id: filters.equipment_id || undefined,
        project_id: filters.project_id || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
    };

    useEffect(() => {
        const mine = ++requestNumber.current;
        setLoading(true);
        setError(null);
        apiClient
            .get(`/records/${key}`, { params: { ...params, page, page_size: PAGE_SIZE } })
            .then((res) => {
                if (mine !== requestNumber.current) return;
                setData(res.data);
                setLoading(false);
            })
            .catch((err) => {
                if (mine !== requestNumber.current) return;
                setError(err.response?.data?.detail || "Could not load the records. Is the backend running?");
                setLoading(false);
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key, appliedQ, filters.equipment_id, filters.project_id, filters.date_from, filters.date_to, page]);

    const setFilter = (name, value) => {
        setFilters((prev) => ({ ...prev, [name]: value }));
        if (name !== "q") setPage(1);
    };

    const download = (format, everything) => {
        const id = `${format}${everything ? "-all" : ""}`;
        setDownloading(id);
        apiClient
            .get(`/records/${key}/export`, {
                params: { ...params, format, all: everything ? true : undefined },
                responseType: "blob",
            })
            .then((res) => {
                const url = URL.createObjectURL(res.data);
                const link = document.createElement("a");
                link.href = url;
                link.download = `${key}${everything ? "-all" : ""}-${new Date().toISOString().slice(0, 10)}.${format}`;
                link.click();
                URL.revokeObjectURL(url);
            })
            .catch(async (err) => setError(await downloadError(err)))
            .finally(() => setDownloading(null));
    };

    const rows = data?.rows || [];
    const total = data?.total || 0;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const columns = rows.length ? Object.keys(rows[0]) : [];
    const filtering = Object.values({ ...filters }).some(Boolean);
    const label = data?.label || key.replace(/-/g, " ");

    return (
        <div>
            <button type="button" className="btn-outline back-btn" onClick={() => navigate(-1)}>
                &larr; Back
            </button>

            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">{label} - all records</h3>
                        <div className="card-sub">
                            Search or filter, then download exactly what you see - or download everything.
                        </div>
                    </div>
                    <div className="list-tools">
                        <button type="button" disabled={!!downloading} onClick={() => download("csv", false)}>
                            {downloading === "csv" ? "Preparing..." : "Download CSV"}
                        </button>
                        <button type="button" disabled={!!downloading} onClick={() => download("pdf", false)}>
                            {downloading === "pdf" ? "Preparing..." : "Download PDF"}
                        </button>
                        <button type="button" className="btn-outline" disabled={!!downloading} onClick={() => download("csv", true)}>
                            {downloading === "csv-all" ? "Preparing..." : "Download all data (CSV)"}
                        </button>
                    </div>
                </div>

                <div className="filters">
                    <div className="field">
                        <label className="field-label">Search</label>
                        <input
                            type="search"
                            placeholder="e.g. eq-007, dozer, prj 3, 2026-01"
                            value={filters.q}
                            onChange={(e) => setFilter("q", e.target.value)}
                        />
                    </div>
                    <div className="field">
                        <label className="field-label">Equipment</label>
                        <select value={filters.equipment_id} onChange={(e) => setFilter("equipment_id", e.target.value)}>
                            <option value="">All equipment</option>
                            {equipment.map((eq) => (
                                <option key={eq.Equipment_ID} value={eq.Equipment_ID}>
                                    {eq.Equipment_ID} - {eq.Equipment_Name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="field">
                        <label className="field-label">Project</label>
                        <select value={filters.project_id} onChange={(e) => setFilter("project_id", e.target.value)}>
                            <option value="">All projects</option>
                            {projects.map((p) => (
                                <option key={p.Project_ID} value={p.Project_ID}>
                                    {p.Project_ID} - {p.Project_Name}
                                </option>
                            ))}
                        </select>
                    </div>
                    {(data?.has_date ?? true) && (
                        <>
                            <div className="field">
                                <label className="field-label">From date</label>
                                <input type="date" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} />
                            </div>
                            <div className="field">
                                <label className="field-label">To date</label>
                                <input type="date" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} />
                            </div>
                        </>
                    )}
                    <div className="field filters-reset">
                        <button
                            type="button"
                            className="btn-outline"
                            disabled={!filtering}
                            onClick={() => { setFilters(EMPTY_FILTERS); setAppliedQ(""); setPage(1); }}
                        >
                            Clear filters
                        </button>
                    </div>
                </div>

                {error && <p className="form-error" style={{ margin: "0 18px 12px" }}>{error}</p>}

                <div className="table-scroll" style={{ opacity: loading ? 0.55 : 1 }}>
                    <table>
                        <thead>
                            <tr>
                                {columns.map((c) => (
                                    <th key={c}>{heading(c)}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((row) => (
                                <tr key={row[data.pk]}>
                                    {columns.map((c) => (
                                        <td key={c}>{show(row[c])}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {!loading && rows.length === 0 && !error && <div className="empty-row">No records match.</div>}
                </div>

                <div className="pager">
                    <span className="list-count">
                        {total === 0 ? "0 records" : `Showing ${(page - 1) * PAGE_SIZE + 1}-${Math.min(page * PAGE_SIZE, total)} of ${total}`}
                    </span>
                    <span>
                        <button type="button" className="btn-outline" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>
                            Previous
                        </button>
                        <span className="pager-page">Page {page} of {pages}</span>
                        <button type="button" className="btn-outline" disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>
                            Next
                        </button>
                    </span>
                </div>
            </div>
        </div>
    );
}

export default RecordsPage;
