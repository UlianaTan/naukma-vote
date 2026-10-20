import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../../lib/api";
import { API_BASE_URL, SESSION_EXPIRED_EVENT } from "../../../lib/session";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    api
      .get<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  }, []);

  function login() {
    const next = encodeURIComponent(`${window.location.origin}/`);
    window.location.href = `${API_BASE_URL}/api/auth/google/login?next=${next}`;
  }

  async function logout() {
    try {
      await api.post("/api/auth/logout");
      setUser(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Не вдалося вийти");
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth має використовуватись всередині AuthProvider");
  return ctx;
}
