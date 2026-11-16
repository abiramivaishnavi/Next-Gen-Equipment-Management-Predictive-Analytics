/**
 * Tiny icon set (inline SVG) so we don't need an icon library.
 * Usage: <Icon name="fuel" />   — unknown names draw a plain dot.
 */
const PATHS = {
    dashboard: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z",
    equipment: "M4 17h16M6 17V9h6l3 4h3v4M8 20a1.5 1.5 0 100-3 1.5 1.5 0 000 3zm9 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z",
    fuel: "M4 21V5a2 2 0 012-2h6a2 2 0 012 2v16M4 21h10M14 9h2a2 2 0 012 2v6a1.5 1.5 0 003 0V9l-3-3M6 8h6",
    clock: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-14v5l3 2",
    activity: "M3 12h4l3-8 4 16 3-8h4",
    shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zm0 5v5m0 3v.01",
    transfer: "M7 7h13m0 0l-3-3m3 3l-3 3M17 17H4m0 0l3-3m-3 3l3 3",
    folder: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z",
    info: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-9v5m0-8v.01",
    tool: "M14.7 6.3a4 4 0 00-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 005.4-5.4l-2.6 2.6-2.4-.6-.6-2.4 2.6-2.6z",
    alert: "M12 3l10 18H2L12 3zm0 7v5m0 3v.01",
    history: "M3 12a9 9 0 109-9 9 9 0 00-7 3.4M3 4v4h4M12 8v5l3 2",
    chart: "M4 20V4m0 16h16M8 16v-5m4 5V8m4 8v-3",
    rate: "M12 3v18m4-14H10a3 3 0 000 6h4a3 3 0 010 6H8",
    forecast: "M3 17l6-6 4 4 8-9m0 0h-5m5 0v5",
    check: "M5 13l4 4L19 7",
    users: "M16 20v-1a4 4 0 00-4-4H7a4 4 0 00-4 4v1M9.5 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM21 20v-1a4 4 0 00-3-3.9",
    logout: "M15 17l5-5-5-5M20 12H9m4 8H5a2 2 0 01-2-2V6a2 2 0 012-2h8",
};

function Icon({ name, size = 18 }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            style={{ flexShrink: 0 }}
        >
            {PATHS[name] ? <path d={PATHS[name]} /> : <circle cx="12" cy="12" r="2" />}
        </svg>
    );
}

export default Icon;
