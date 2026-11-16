import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";
import "../components/layout.css";

// Demo helper for presentations: one-click fill for a sample account of each role.
// All demo accounts share one password (set by scripts/set_demo_passwords.py).
// Set to false before showing this to anyone as a "real" system.
const SHOW_DEMO_HINT = true;
const DEMO_PASSWORD = "Ems@2026";
const DEMO_ACCOUNTS = [
    { role: "Fleet Manager", icon: "check", email: "linda.perry16@ems-demo.com", desc: "Approves transfers · full fleet visibility" },
    { role: "Site Engineer", icon: "equipment", email: "jenna.finley1@ems-demo.com", desc: "Requests transfers · logs fuel and incidents" },
    { role: "Workshop Mechanic", icon: "tool", email: "patrick.velez11@ems-demo.com", desc: "Breakdowns · servicing · repairs" },
];

// Roles a person can pick for themselves. Fleet Manager is not offered on purpose:
// that role approves transfers, so an existing Fleet Manager has to grant it.
const SELF_SERVICE_ROLES = [
    { value: "site_engineer", label: "Site Engineer" },
    { value: "mechanic", label: "Workshop Mechanic" },
];

function formatError(err, fallback) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        // FastAPI validation errors: show the first one in plain words
        const first = detail[0];
        const field = first?.loc?.slice(-1)[0];
        if (field === "password") return "Password must be at least 8 characters.";
        if (field === "name") return "Please enter your full name.";
        return first?.msg || fallback;
    }
    if (!err.response) return "Can't reach the server. Is the backend running?";
    return fallback;
}

function LoginPage() {
    const { user, login } = useAuth();
    const navigate = useNavigate();
    const [mode, setMode] = useState("signin"); // "signin" | "register"
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [phone, setPhone] = useState("");
    const [role, setRole] = useState("site_engineer");
    const [confirm, setConfirm] = useState("");
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    // Already signed in? No need to see the login page.
    if (user) return <Navigate to="/" replace />;

    const switchMode = (next) => {
        setMode(next);
        setError(null);
        setPassword("");
        setConfirm("");
    };

    const handleSignIn = (e) => {
        e.preventDefault();
        setError(null);
        setSuccess(null);
        setSubmitting(true);
        login(email, password)
            .then(() => navigate("/"))
            .catch((err) => setError(formatError(err, "Sign in failed. Please try again.")))
            .finally(() => setSubmitting(false));
    };

    const handleRegister = (e) => {
        e.preventDefault();
        setError(null);
        if (password.length < 8) return setError("Password must be at least 8 characters.");
        if (password !== confirm) return setError("The two passwords don't match.");
        setSubmitting(true);
        apiClient
            .post("/auth/register", { name, email, phone: phone || null, password, role })
            .then((res) => {
                setSuccess(res.data.message);
                switchMode("signin");
            })
            .catch((err) => setError(formatError(err, "Could not create the account. Please try again.")))
            .finally(() => setSubmitting(false));
    };

    return (
        <div className="login-wrap">
            <section className="login-hero">
                <div className="hero-logo">
                    <span className="brand-logo">
                        <Icon name="equipment" size={20} />
                    </span>
                    EMS
                </div>

                <div>
                    <div className="hero-eyebrow">Equipment Management System</div>
                    <h1 className="hero-title">One source of truth for every machine on every site.</h1>
                    <p className="hero-text">
                        Track heavy machinery across project sites — fuel, maintenance, breakdowns and
                        inter-site transfers — in a single operational view.
                    </p>
                </div>

                <div className="hero-foot">Next-Gen Equipment Management System · Internal tool · Authorised personnel only</div>
            </section>

            <section className="login-side">
                {mode === "signin" ? (
                    <form className="login-card" onSubmit={handleSignIn}>
                        <h2 className="login-title">Sign in</h2>
                        <p className="login-lead">Use your EMS credentials{SHOW_DEMO_HINT ? ", or pick a demo role below." : "."}</p>

                        {success && <p className="login-success">{success}</p>}

                        <label>
                            Work email
                            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                placeholder="employee.user@company.com" required autoFocus />
                        </label>
                        <label>
                            Password
                            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                        </label>

                        {error && <p className="login-error">{error}</p>}

                        <button type="submit" disabled={submitting}>
                            {submitting ? "Signing in..." : "Sign in"}
                        </button>
                        <p className="login-help">Forgot your password? Contact your administrator.</p>
                        <p className="login-switch">
                            New to EMS?{" "}
                            <button type="button" className="link-btn" onClick={() => { setSuccess(null); switchMode("register"); }}>
                                Create an account
                            </button>
                        </p>

                        {SHOW_DEMO_HINT && (
                            <div className="demo-box">
                                <div className="demo-title">Demo accounts · password {DEMO_PASSWORD}</div>
                                {DEMO_ACCOUNTS.map((acc) => (
                                    <button type="button" className="demo-card" key={acc.email}
                                        onClick={() => { setEmail(acc.email); setPassword(DEMO_PASSWORD); }}>
                                        <span className="demo-icon"><Icon name={acc.icon} size={18} /></span>
                                        <span>
                                            <div className="demo-role">{acc.role}</div>
                                            <div className="demo-desc">{acc.desc}</div>
                                        </span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </form>
                ) : (
                    <form className="login-card" onSubmit={handleRegister}>
                        <h2 className="login-title">Create account</h2>
                        <p className="login-lead">A Fleet Manager approves new accounts before they can sign in.</p>

                        <label>
                            Full name
                            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
                        </label>
                        <label>
                            Work email
                            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                placeholder="employee.user@company.com" required />
                        </label>
                        <div className="name-row">
                            <label>
                                Phone (optional)
                                <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
                            </label>
                            <label>
                                Role
                                <select value={role} onChange={(e) => setRole(e.target.value)}>
                                    {SELF_SERVICE_ROLES.map((r) => (
                                        <option key={r.value} value={r.value}>{r.label}</option>
                                    ))}
                                </select>
                            </label>
                        </div>
                        <label>
                            Password (at least 8 characters)
                            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                        </label>
                        <label>
                            Confirm password
                            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
                        </label>
                        <p className="login-note">Fleet Manager accounts are created by an existing Fleet Manager.</p>

                        {error && <p className="login-error">{error}</p>}

                        <button type="submit" disabled={submitting}>
                            {submitting ? "Creating account..." : "Create account"}
                        </button>
                        <p className="login-switch">
                            Already have an account?{" "}
                            <button type="button" className="link-btn" onClick={() => switchMode("signin")}>
                                Sign in
                            </button>
                        </p>
                    </form>
                )}
            </section>
        </div>
    );
}

export default LoginPage;
