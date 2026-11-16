import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { MENUS, pageInfo } from "../menu";
import Icon from "./Icon";
import "./layout.css";

// Small heading above the menu, per role.
const SECTION = {
    site_engineer: "Site operations",
    mechanic: "Workshop",
    fleet_manager: "Operations",
};

function initials(name) {
    return (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}

/**
 * The frame around every signed-in page:
 *   sidebar : logo, the menu for THIS user's role, current diesel rate
 *   top strip: fleet counts, who is signed in, Logout
 *   page head: small label + title + one-line description, then the page itself
 */
function Layout() {
    const { user, loading, logout } = useAuth();
    const navigate = useNavigate();
    const { pathname } = useLocation();
    const [meta, setMeta] = useState(null);

    // Small numbers for the top strip / sidebar badge. Refreshed on every page change AND whenever a
    // page announces that data changed (a transfer was requested / approved / rejected), so the
    // "pending" badge updates immediately.
    useEffect(() => {
        if (!user) return;
        const loadMeta = () =>
            apiClient
                .get("/dashboard/meta")
                .then((res) => setMeta(res.data))
                .catch(() => setMeta(null));
        loadMeta();
        window.addEventListener("ems-data-changed", loadMeta);
        return () => window.removeEventListener("ems-data-changed", loadMeta);
    }, [user, pathname]);

    // Not signed in (or still checking a saved login)? Don't draw the menu for nobody.
    if (loading) return <p style={{ padding: 24 }}>Loading...</p>;
    if (!user) return <Navigate to="/login" replace />;

    const menu = MENUS[user.Role] || [];
    const info = pageInfo(user.Role, pathname);

    const handleLogout = () => {
        logout();
        navigate("/login");
    };

    return (
        <div className="app-shell">
            <aside className="sidebar">
                <div className="brand">
                    <span className="brand-logo">
                        <Icon name="equipment" size={20} />
                    </span>
                    <div>
                        <div className="brand-name">EMS</div>
                        <div className="brand-sub">Next-Gen Equipment Management System</div>
                    </div>
                </div>

                <div className="nav-label">{SECTION[user.Role] || "Menu"}</div>
                <nav className="nav">
                    {menu.map((item) => (
                        <NavLink key={item.to} to={item.to} end>
                            <Icon name={item.icon} />
                            <span>{item.label}</span>
                            {item.to === "/transfer-approvals" && meta?.pending_transfers > 0 && (
                                <span className="nav-badge">{meta.pending_transfers}</span>
                            )}
                            {item.to === "/employees" && meta?.pending_accounts > 0 && (
                                <span className="nav-badge" title="Accounts waiting to be activated">{meta.pending_accounts}</span>
                            )}
                        </NavLink>
                    ))}
                </nav>

                {meta?.diesel_rate != null && (
                    <div className="sidebar-foot">
                        <div className="foot-label">Diesel rate</div>
                        <div className="foot-value">SAR {meta.diesel_rate.toFixed(2)} / L</div>
                    </div>
                )}
            </aside>

            <div className="main-col">
                <header className="topbar">
                    <div className="strip">
                        <span className="dot" />
                        {meta ? `Next-Gen Equipment Management System · ${meta.projects} project sites · ${meta.assets} assets tracked` : "Next-Gen Equipment Management System"}
                    </div>
                    <div className="topbar-right">
                        <div className="user-text user-chip">
                            <div className="user-name">{user.Employee_Name}</div>
                            <div className="user-role">{user.Role_Name}</div>
                        </div>
                        <span className="avatar">{initials(user.Employee_Name)}</span>
                        <button className="btn-outline" onClick={handleLogout}>
                            <Icon name="logout" size={16} /> Logout
                        </button>
                    </div>
                </header>

                <div className="page-head">
                    <div className="eyebrow">{info.eyebrow}</div>
                    <h1 className="page-title">{info.label}</h1>
                    <p className="page-desc">{info.desc}</p>
                </div>

                <main className="content">
                    <Outlet />
                </main>
            </div>
        </div>
    );
}

export default Layout;
