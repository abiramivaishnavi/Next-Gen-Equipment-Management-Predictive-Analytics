import { Navigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { canOpen } from "../menu";

/**
 * Wrap a page in this to protect it:
 *   - not signed in            -> sent to the login page
 *   - signed in, wrong role    -> "not allowed" message
 *   - otherwise                -> the page
 * NOTE: this only controls what the SCREEN shows. The real protection is on the
 * server (the API rejects requests the role isn't allowed to make).
 */
function RequireAccess({ children }) {
    const { user, loading } = useAuth();
    const location = useLocation();

    if (loading) return <p>Loading...</p>;
    if (!user) return <Navigate to="/login" replace />;

    if (!canOpen(user.Role, location.pathname)) {
        return (
            <div className="not-allowed">
                <h2>Not allowed</h2>
                <p>Your role ({user.Role_Name}) doesn't have access to this page.</p>
                <Link to="/">Back to your dashboard</Link>
            </div>
        );
    }
    return children;
}

export default RequireAccess;
