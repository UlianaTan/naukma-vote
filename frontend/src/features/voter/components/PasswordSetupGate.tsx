import { useState, type FormEvent, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { VoteBrand, VoteFooter } from "../../../components/layout/VoterLayout";
import { useAuth } from "../hooks/useAuth";

export function PasswordSetupGate({ children }: { children: ReactNode }) {
  const { user, isLoading, sessionError } = useAuth();
  if (isLoading || sessionError || !user?.needs_password_setup) return children;
  return <PasswordSetupForm />;
}

function PasswordSetupForm() {
  const { user, setupPassword, logout, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const mismatch = confirmation.length > 0 && password !== confirmation;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || password !== confirmation) return;
    setBusy(true);
    try {
      await setupPassword(password);
      if (location.pathname === "/login") navigate("/", { replace: true });
    } catch {
      // AuthProvider exposes the error beside this form; retain entered values.
    } finally {
      setBusy(false);
    }
  }

  async function leave() {
    if (busy) return;
    setBusy(true);
    try { await logout(); }
    finally { setBusy(false); }
  }

  return <div className="vote-background flex min-h-screen flex-col">
    <header className="border-b border-slate-200 bg-white px-5 py-4 sm:px-8"><VoteBrand /></header>
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <section className="vote-panel w-full max-w-md space-y-6 p-6 sm:p-9" aria-labelledby="setup-title">
        <div className="space-y-3">
          <LockKeyhole className="text-primary" size={32} aria-hidden="true" />
          <h1 id="setup-title" className="text-2xl font-bold">Створіть пароль для NaUKMA Vote</h1>
          <p className="text-sm leading-6 text-slate-600">Ви увійшли через Google як <strong className="break-all">{user?.email}</strong>. Створіть окремий пароль, щоб надалі входити також через пошту.</p>
          <p className="text-sm leading-6 text-slate-500">Це не пароль Google чи університетської пошти. Після збереження більше не проситимемо його створювати.</p>
        </div>
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <form onSubmit={submit} className="space-y-5">
          <div>
            <label htmlFor="setup-password" className="mb-2 block text-sm font-semibold">Новий пароль</label>
            <div className="relative">
              <input id="setup-password" type={visible ? "text" : "password"} autoComplete="new-password"
                required minLength={12} maxLength={1024} disabled={busy} value={password}
                aria-describedby="setup-password-help"
                onChange={event => { setPassword(event.target.value); clearError(); }}
                className="h-12 w-full rounded-xl border border-slate-300 px-3 pr-12 text-sm outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100" />
              <button type="button" onClick={() => setVisible(value => !value)} disabled={busy}
                aria-label={visible ? "Приховати пароль" : "Показати пароль"} aria-pressed={visible}
                className="absolute right-2 top-2 rounded-lg p-2 text-slate-500 hover:bg-slate-100">
                {visible ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <p id="setup-password-help" className="mt-2 text-xs text-slate-500">Від 12 до 1024 символів.</p>
          </div>
          <div>
            <label htmlFor="setup-confirmation" className="mb-2 block text-sm font-semibold">Повторіть пароль</label>
            <input id="setup-confirmation" type={visible ? "text" : "password"} autoComplete="new-password"
              required minLength={12} maxLength={1024} disabled={busy} value={confirmation}
              aria-invalid={mismatch} aria-describedby={mismatch ? "setup-mismatch" : undefined}
              onChange={event => { setConfirmation(event.target.value); clearError(); }}
              className={`h-12 w-full rounded-xl border px-3 text-sm outline-none focus:ring-2 focus:ring-blue-100 ${mismatch ? "border-red-500" : "border-slate-300"}`} />
            {mismatch && <p id="setup-mismatch" role="alert" className="mt-2 text-xs text-red-700">Паролі не збігаються.</p>}
          </div>
          <button type="submit" disabled={busy || password.length < 12 || password !== confirmation}
            className="vote-button w-full disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? "Зберігаємо…" : "Зберегти пароль і продовжити"}
          </button>
        </form>
        <button type="button" onClick={() => void leave()} disabled={busy}
          className="w-full text-sm text-slate-500 underline disabled:opacity-50">Вийти з акаунта</button>
      </section>
    </main>
    <VoteFooter />
  </div>;
}
