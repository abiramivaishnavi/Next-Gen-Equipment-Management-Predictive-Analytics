import axios from "axios";

const apiClient = axios.create({
    baseURL: "http://127.0.0.1:8001",
});

// ---- login token helpers ------------------------------------------------
// The token is the "badge" the server gives us at login. We keep it in the browser
// (localStorage) so a page refresh doesn't sign the user out.
// Wrapped in try/catch because some browsers block storage in private windows.
export const TOKEN_KEY = "ems_token";

export function getToken() {
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch {
        return null;
    }
}

export function saveToken(token) {
    try {
        localStorage.setItem(TOKEN_KEY, token);
    } catch {
        /* storage blocked - the session just won't survive a refresh */
    }
}

export function clearToken() {
    try {
        localStorage.removeItem(TOKEN_KEY);
    } catch {
        /* nothing to do */
    }
}

// Attach the token to EVERY request automatically, so no page has to remember to.
apiClient.interceptors.request.use((config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

// If the server says "401 - not signed in / session expired" on any normal request,
// forget the token and tell the app so it can send the user back to the login page.
// (Login attempts themselves also return 401 for a wrong password - those are
// excluded, otherwise a typo would look like an expired session.)
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        const isLoginCall = error.config?.url?.includes("/auth/login");
        if (error.response?.status === 401 && !isLoginCall) {
            clearToken();
            window.dispatchEvent(new Event("ems-unauthorized"));
        }
        return Promise.reject(error);
    }
);

export default apiClient;
