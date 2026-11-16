/**
 * Single source of truth for "who sees what" — taken from the approved wireframes.
 * The sidebar menu AND the route protection both read from here, so they can't drift apart.
 *
 * Each entry: { label, to, icon, eyebrow, desc }.  `to` must match a route in App.jsx.
 * eyebrow/desc are the small heading text shown above each page.
 * Roles (keys come from the server's /auth/me):  site_engineer | mechanic | fleet_manager
 */
export const MENUS = {
    site_engineer: [
        { label: "Dashboard", to: "/", icon: "dashboard", eyebrow: "Overview", desc: "Live snapshot of the fleet and what needs attention." },
        { label: "Equipment", to: "/equipment", icon: "equipment", eyebrow: "Registry", desc: "Register and maintain the machinery on your sites." },
        { label: "Fuel Logs", to: "/fuel-logs", icon: "fuel", eyebrow: "Consumption", desc: "Record diesel issued to equipment. Cost is calculated automatically at the current rate." },
        { label: "Utilization Logs", to: "/utilization-logs", icon: "clock", eyebrow: "Operations", desc: "Record the operating hours of each machine against a project." },
        { label: "Project Activity", to: "/project-activities", icon: "activity", eyebrow: "Planning", desc: "Planned activities per project — the basis for fuel forecasting." },
        { label: "Incidents", to: "/incidents", icon: "shield", eyebrow: "Safety", desc: "Log accidents and safety incidents involving equipment." },
        { label: "Transfers", to: "/transfers", icon: "transfer", eyebrow: "Logistics", desc: "Request inter-site equipment moves. Fleet Managers approve or reject pending requests." },
        { label: "Information", to: "/information", icon: "info", eyebrow: "Lookup", desc: "Search equipment and projects (read-only). Click a project to see the equipment it is using." },
    ],
    mechanic: [
        { label: "Dashboard", to: "/", icon: "dashboard", eyebrow: "Overview", desc: "Workshop snapshot: open breakdowns, downtime and services due." },
        { label: "Maintenance", to: "/maintenance", icon: "tool", eyebrow: "Workshop", desc: "Scheduled service records for each machine." },
        { label: "Breakdowns", to: "/breakdowns", icon: "alert", eyebrow: "Workshop", desc: "Log unscheduled breakdowns. Status closes automatically when a repair is logged." },
        { label: "Repairs", to: "/repairs", icon: "tool", eyebrow: "Workshop", desc: "Repair records with parts replaced, labour hours and cost." },
        { label: "Maintenance History", to: "/maintenance-history", icon: "history", eyebrow: "History", desc: "Full service and repair history of a machine." },
    ],
    fleet_manager: [
        { label: "Dashboard", to: "/", icon: "dashboard", eyebrow: "Overview", desc: "Operational snapshot across all project sites." },
        { label: "Transfer Approval", to: "/transfer-approvals", icon: "transfer", eyebrow: "Logistics", desc: "Review pending transfer requests and approve or reject them." },
        { label: "Operational & Maintenance", to: "/operational-data", icon: "activity", eyebrow: "Oversight", desc: "Operational and maintenance data across the fleet." },
        { label: "Reports", to: "/reports", icon: "chart", eyebrow: "Insights", desc: "Pick a register, then search, filter and download its data." },
        { label: "Predictive Maintenance", to: "/predictive-maintenance", icon: "shield", eyebrow: "Analytics", desc: "Breakdown-risk predictions (next phase)." },
        { label: "Fuel Forecast", to: "/fuel-forecast", icon: "forecast", eyebrow: "Analytics", desc: "Fuel requirement forecast (next phase)." },
        { label: "Fuel Rates", to: "/fuel-rates", icon: "rate", eyebrow: "Settings", desc: "Maintain the fuel price (per litre, or per kWh for electricity) used to cost every fuel entry." }, // not in the wireframe, but someone must maintain fuel prices
        { label: "Employees", to: "/employees", icon: "users", eyebrow: "Administration", desc: "System users and their roles. New accounts wait here until you set them to Active." }, // not in the wireframe: somebody must approve new accounts
    ],
};

// Pages a role may open by typing the URL even though they're not in its menu.
// (Roles / Manage Projects admin pages: kept for the Fleet Manager only.)
export const HIDDEN_ACCESS = {
    fleet_manager: ["/roles", "/manage-projects"],
};

export const HIDDEN_PAGES = {
    "/manage-projects": { label: "Manage Projects", eyebrow: "Administration", desc: "Add or edit project sites (Fleet Manager only)." },
    "/roles": { label: "Roles", eyebrow: "Administration", desc: "The roles that control access." },
};

export function canOpen(role, path) {
    // "All records" pages (search / filter / download) are open to every signed-in role.
    if (path.startsWith("/records/")) return Boolean(MENUS[role]);
    const menuPaths = (MENUS[role] || []).map((item) => item.to);
    const hidden = HIDDEN_ACCESS[role] || [];
    return menuPaths.includes(path) || hidden.includes(path);
}

/** Title / eyebrow / description for the page header. */
export function pageInfo(role, path) {
    if (path.startsWith("/records/")) {
        return { label: "Records", eyebrow: "Data", desc: "Search, filter and download saved data." };
    }
    const item = (MENUS[role] || []).find((m) => m.to === path) || HIDDEN_PAGES[path];
    return item || { label: "EMS", eyebrow: "", desc: "" };
}

export function titleFor(role, path) {
    return pageInfo(role, path).label;
}
