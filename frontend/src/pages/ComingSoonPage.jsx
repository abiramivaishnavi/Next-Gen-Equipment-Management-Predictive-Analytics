import { useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { titleFor } from "../menu";

// What each planned analytics screen will do (Phase 3 of the project). Shown instead of a bare "coming soon".
const PLANNED = {
    "/predictive-maintenance": {
        what: "Breakdown risk for every machine.",
        points: [
            "Estimates the probability that a machine breaks down within the next 30 days.",
            "Learns from the history already stored in EMS: machine age, operating hours, service gaps, past breakdowns and repairs.",
            "Machines are ranked, so the workshop can service the riskiest ones first.",
        ],
    },
    "/fuel-forecast": {
        what: "Fuel needed per project site, by week or month.",
        points: [
            "Uses planned project activities, the machines allocated to each site and past fuel consumption.",
            "Helps the Fleet Manager order fuel and plan the budget before it is needed.",
            "Litres (diesel, petrol) and kWh (electric) are forecast separately.",
        ],
    },
};

/** Placeholder for the Phase 3 analytics screens that are planned but not built yet. */
function ComingSoonPage() {
    const { user } = useAuth();
    const { pathname } = useLocation();
    const plan = PLANNED[pathname];

    return (
        <div className="panel" style={{ maxWidth: 640 }}>
            <h2>{titleFor(user.Role, pathname)}</h2>
            <span className="pill pill-neutral">Coming in Phase 3</span>
            {plan ? (
                <>
                    <p style={{ marginTop: 14 }}><strong>{plan.what}</strong></p>
                    <ul style={{ paddingLeft: 20, lineHeight: 1.6 }}>
                        {plan.points.map((t) => (
                            <li key={t}>{t}</li>
                        ))}
                    </ul>
                    <p className="panel-empty">This screen is part of the data science phase and is not built yet.</p>
                </>
            ) : (
                <p>This screen is planned (see the wireframes) and will be built in an upcoming step.</p>
            )}
        </div>
    );
}

export default ComingSoonPage;
