import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../../../lib/api";
import { API_BASE_URL, SESSION_EXPIRED_EVENT, sessionEpoch, assertSessionEpoch, clearSession } from "../../../lib/session";
import { loadSession } from "../../../lib/loadSession";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  sessionError: string | null;
  retrySession: () => void;
  login: () => void;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  clearError: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sessionError, setSessionError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  function retrySession() {
    setSessionError(null);
    setIsLoading(true);
    setAttempt(value => value + 1);
  }

  useEffect(() => {
    let active = true;
    const epoch = sessionEpoch();
    const expired = () => {
      setUser(null);
      setSessionError(null);
      setIsLoading(false);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    loadSession<User>()
      .then(result => {
        if (!active || epoch !== sessionEpoch()) return;
        if (result.kind === "authenticated") setUser(result.user);
        else if (result.kind === "anonymous") setUser(null);
        else setSessionError("Не вдалося перевірити сесію. Перевірте з’єднання та повторіть спробу.");
      })
      .finally(() => {
        if (active && epoch === sessionEpoch()) setIsLoading(false);
      });
    return () => {
      active = false;
      window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
    };
  }, [attempt]);

  function login() {
    const next = encodeURIComponent(`${window.location.origin}/`);
    window.location.href = `${API_BASE_URL}/api/auth/google/login?next=${next}`;
  }

  async function loginWithPassword(email: string, password: string) {
    setError(null);
    const epoch = sessionEpoch();
    try {
      const result = await api.post<{ user: User }>("/api/auth/login", { email, password });
      assertSessionEpoch(epoch);
      clearSession();
      setUser(result.user);
      setSessionError(null);
      setIsLoading(false);
    } catch (e) {
      if (epoch !== sessionEpoch()) throw e;
      setError(e instanceof ApiError && e.status === 401
        ? "Неправильна адреса електронної пошти або пароль."
        : "Не вдалося виконати вхід. Спробуйте пізніше.");
      throw e;
    }
  }

  async function register(email: string, password: string) {
    setError(null);
    const epoch = sessionEpoch();
    try {
      const result = await api.post<{ user: User }>("/api/auth/register", { email, password });
      assertSessionEpoch(epoch);
      clearSession();
      setUser(result.user);
      setSessionError(null);
      setIsLoading(false);
    } catch (e) {
      if (epoch !== sessionEpoch()) throw e;
      setError(e instanceof ApiError && e.status === 409
        ? "Обліковий запис із цією адресою вже існує. Увійдіть за паролем або через Google."
        : e instanceof ApiError && e.status === 400
          ? "Реєстрація доступна лише для адрес @ukma.edu.ua."
          : e instanceof ApiError && e.status === 422
            ? "Перевірте адресу та пароль (не менше 12 символів)."
            : "Не вдалося зареєструватися. Спробуйте пізніше.");
      throw e;
    }
  }

  async function logout() {
    setError(null);
    try {
      await api.post("/api/auth/logout");
      setUser(null);
      setSessionError(null);
      setIsLoading(false);
    } catch {
      setError("Не вдалося вийти. Перевірте з’єднання та спробуйте ще раз.");
    }
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, error, sessionError, retrySession, login, loginWithPassword, register, clearError: () => setError(null), logout }}>
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
