import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { useAuth } from "../auth/AuthContext";
import TransferQueue from "../components/TransferQueue";

const today = () => new Date().toISOString().slice(0, 10);

function apiError(err) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
    return err.response ? "Something went wrong." : "Can't reach the server. Is the backend running?";
}

/**
 * Site Engineer: raise a transfer request and follow its outcome.
 * Nothing about "who" or "from where" is typed: Requested By is you (from your login) and
 * From Project is wherever the equipment is right now.
 */
function TransfersPage() {
    const { user } = useAuth();
    const [options, setOptions] = useState({ equipment: [], projects: [] });
    const [equipmentId, setEquipmentId] = useState("");
    const [toProject, setToProject] = useState("");
    const [notes, setNotes] = useState("");
    const [error, setError] = useState(null);
    const [message, setMessage] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0); // bump to reload the queue below

    const loadOptions = () =>
        apiClient
            .get("/transfers/request-options")
            .then((res) => setOptions(res.data))
            .catch((err) => setError(apiError(err)));

    useEffect(() => {
        loadOptions();
    }, []);

    const equipment = options.equipment.find((e) => e.Equipment_ID === equipmentId);
    const fromProject = equipment?.Current_Project_ID || "";
    const destinations = options.projects.filter((p) => p.Project_ID !== fromProject);

    const pickEquipment = (id) => {
        setEquipmentId(id);
        setToProject(""); // the old destination might be the new From project
        setMessage(null);
        setError(null);
    };

    const submit = (e) => {
        e.preventDefault();
        setError(null);
        setMessage(null);
        setSubmitting(true);
        apiClient
            .post("/transfers/request", { Equipment_ID: equipmentId, To_Project_ID: toProject, Transfer_Notes: notes || null })
            .then((res) => {
                setMessage(`Request #${res.data.Transfer_ID} sent to the Fleet Manager: ${equipmentId} from ${res.data.From_Project_ID} to ${toProject}.`);
                setEquipmentId("");
                setToProject("");
                setNotes("");
                setRefreshKey((k) => k + 1);
                window.dispatchEvent(new Event("ems-data-changed"));
                loadOptions(); // this machine now has a pending request, so it is greyed out
            })
            .catch((err) => {
                setError(apiError(err));
                loadOptions(); // the situation may have changed (someone else requested it first)
            })
            .finally(() => setSubmitting(false));
    };

    return (
        <div>
            <form onSubmit={submit} className="card-panel entity-form">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">New transfer request</h3>
                        <div className="card-sub">A Fleet Manager reviews every request. You can follow it in the list below.</div>
                    </div>
                </div>
                <div className="form-body">
                    <div className="form-grid">
                        <div className="field">
                            <label className="field-label">Equipment *</label>
                            <select value={equipmentId} onChange={(e) => pickEquipment(e.target.value)} required>
                                <option value="">Select equipment</option>
                                {options.equipment.map((eq) => (
                                    <option key={eq.Equipment_ID} value={eq.Equipment_ID} disabled={Boolean(eq.Block_Reason)}>
                                        {eq.Equipment_ID} - {eq.Equipment_Name}{eq.Current_Project_ID ? ` · ${eq.Current_Project_ID}` : ""}
                                        {eq.Block_Reason ? ` (${eq.Block_Reason})` : ""}
                                    </option>
                                ))}
                            </select>
                            {equipment && (
                                <div className="profile-strip">
                                    {equipment.Equipment_Type} · {equipment.Current_Status} · on {equipment.Current_Project_ID}
                                </div>
                            )}
                        </div>
                        <div className="field">
                            <label className="field-label">From project (auto)</label>
                            <input
                                type="text"
                                readOnly
                                disabled
                                value={equipment ? `${fromProject} - ${equipment.Current_Project_Name || ""}` : ""}
                                placeholder="Filled in from the equipment"
                            />
                        </div>
                        <div className="field">
                            <label className="field-label">To project *</label>
                            <select value={toProject} onChange={(e) => setToProject(e.target.value)} required disabled={!equipment}>
                                <option value="">{equipment ? "Select destination" : "Select equipment first"}</option>
                                {destinations.map((p) => (
                                    <option key={p.Project_ID} value={p.Project_ID}>
                                        {p.Project_ID} - {p.Project_Name}
                                        {p.Location ? ` (${p.Location})` : ""}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="field">
                            <label className="field-label">Requested by</label>
                            <input type="text" readOnly disabled value={user ? `${user.Employee_Name} (you)` : ""} />
                        </div>
                        <div className="field">
                            <label className="field-label">Request date</label>
                            <input type="text" readOnly disabled value={today()} />
                        </div>
                        <div className="field">
                            <label className="field-label">Reason / notes (optional)</label>
                            <textarea
                                rows={3}
                                maxLength={255}
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="e.g. needed for the crane lift at the new site from Sunday"
                            />
                        </div>
                    </div>
                    <div className="form-actions">
                        <button type="submit" disabled={submitting || !equipmentId || !toProject}>
                            {submitting ? "Sending..." : "Submit request"}
                        </button>
                    </div>
                    {message && <p className="login-success" style={{ marginTop: 14 }}>{message}</p>}
                    {error && <p className="form-error">{error}</p>}
                </div>
            </form>

            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">My transfer requests</h3>
                        <div className="card-sub">Your requests and what the Fleet Manager decided, including any rejection reason.</div>
                    </div>
                </div>
                <TransferQueue mode="mine" refreshKey={refreshKey} />
            </div>
        </div>
    );
}

export default TransfersPage;
