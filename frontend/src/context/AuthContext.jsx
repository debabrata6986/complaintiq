import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("ciq_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(false);

  const setSession = useCallback((data) => {
    localStorage.setItem("ciq_token", data.access_token);
    localStorage.setItem("ciq_user", JSON.stringify(data.user));
    setUser(data.user);
  }, []);

  const login = useCallback(async (email, password) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      setSession(data);
      return data.user;
    } finally {
      setLoading(false);
    }
  }, [setSession]);

  const register = useCallback(async (payload) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", payload);
      setSession(data);
      return data.user;
    } finally {
      setLoading(false);
    }
  }, [setSession]);

  const logout = useCallback(() => {
    localStorage.removeItem("ciq_token");
    localStorage.removeItem("ciq_user");
    setUser(null);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("ciq_token");
    if (!token) return;
    api.get("/auth/me").then(({ data }) => {
      setUser(data);
      localStorage.setItem("ciq_user", JSON.stringify(data));
    }).catch(() => {});
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
