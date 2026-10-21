import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../../lib/api";
import { SESSION_EXPIRED_EVENT } from "../../../lib/session";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  clearError: () => void;
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

  async function login(email: string, password: string) {
    setError(null);
    try {
      const result = await api.post<{ user: User }>("/api/auth/login", { email, password });
      setUser(result.user);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401
        ? "Неправильна адреса електронної пошти або пароль."
        : "Не вдалося виконати вхід. Спробуйте пізніше.");
      throw e;
    }
  }

  async function register(email: string, password: string) {
    setError(null);
    try {
      const result = await api.post<{ user: User }>("/api/auth/register", { email, password });
      setUser(result.user);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 409
        ? "Обліковий запис із цією адресою вже існує. Увійдіть у нього."
        : e instanceof ApiError && e.status === 400
          ? "Реєстрація доступна лише для адрес @ukma.edu.ua."
          : e instanceof ApiError && e.status === 422
            ? "Перевірте адресу та пароль (не менше 12 символів)."
            : "Не вдалося зареєструватися. Спробуйте пізніше.");
      throw e;
    }
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
    <AuthContext.Provider value={{ user, isLoading, error, login, register, clearError: () => setError(null), logout }}>
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
