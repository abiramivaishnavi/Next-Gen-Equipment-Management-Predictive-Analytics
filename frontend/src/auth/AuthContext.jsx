import { createContext, useContext, useEffect, useState } from "react";
import apiClient, { getToken, saveToken, clearToken } from "../api/client";

const AuthContext = createContext(null);

/**
 * Keeps track of "who is signed in" for the whole app.
 * Any component can call useAuth() to get { user, loading, login, logout }.
 */
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    // true while we check a saved token on first load (prevents a login-page flash on refresh)
    const [loading, setLoading] = useState(true);

    // On first load: if a token was saved, ask the server who it belongs to.
    useEffect(() => {
        if (!getToken()) {
            setLoading(false);
            return;
        }
        apiClient
            .get("/auth/me")
            .then((res) => setUser(res.data))
            .catch(() => clearToken())
            .finally(() => setLoading(false));
    }, []);

    // The API client fires this when any request comes back 401 (e.g. session expired).
    useEffect(() => {
        const onUnauthorized = () => setUser(null);
        window.addEventListener("ems-unauthorized", onUnauthorized);
        return () => window.removeEventListener("ems-unauthorized", onUnauthorized);
    }, []);

    const login = async (email, password) => {
        const res = await apiClient.post("/auth/login", { email, password });
        saveToken(res.data.access_token);
        setUser(res.data.user);
        return res.data.user;
    };

    const logout = () => {
        clearToken();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
