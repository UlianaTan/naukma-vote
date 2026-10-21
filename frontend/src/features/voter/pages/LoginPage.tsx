import { useState, type FormEvent } from "react";
import { Shield, ArrowRight, Mail, LockKeyhole, Eye, EyeOff, Check } from "lucide-react";
import { VoteBrand, VoteFooter } from "../../../components/layout/VoterLayout";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const authMessages: Record<string, string> = {
  access_denied: "Вхід скасовано. Ви можете спробувати ще раз.",
  invalid_state: "Спроба входу застаріла або була перервана. Почніть вхід ще раз.",
  invalid_domain: "Увійти можна лише через університетський Google-акаунт (@ukma.edu.ua).",
  unverified_email: "Google не підтвердив вашу електронну адресу. Оберіть інший акаунт.",
  invalid_profile: "Не вдалося перевірити дані Google-акаунта. Спробуйте ще раз.",
  google_unavailable: "Не вдалося зв’язатися з Google. Спробуйте пізніше.",
  auth_unavailable: "Вхід тимчасово недоступний. Спробуйте пізніше або зверніться до підтримки.",
  account_conflict: "Не вдалося безпечно пов’язати обліковий запис. Зверніться до підтримки.",
};

export function LoginPage() {
  const { login, loginWithPassword, register, clearError, error, sessionError, retrySession } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const authError = searchParams.get("error");

  const navigate = useNavigate();
  const [isRegistering, setIsRegistering] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function clearFormError() {
    setFormError(null);
    clearError();
    setSearchParams({}, { replace: true });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    clearFormError();
    if (isRegistering && password !== confirmPassword) {
      setFormError("Паролі не збігаються. Перевірте обидва поля.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (isRegistering) {
        await register(email, password);
      } else {
        await loginWithPassword(email, password);
      }
      navigate("/", { replace: true });
    } catch {
      // The auth provider exposes a localized message beside the form.
    } finally {
      setIsSubmitting(false);
    }
  }

  function switchMode(registering: boolean) {
    setIsRegistering(registering);
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
    clearFormError();
  }

  const visibleError = formError || error;
  const passwordsMatch = confirmPassword.length > 0 && password === confirmPassword;

  return (
    <div className="vote-background flex min-h-screen flex-col"><header className="border-b border-slate-200 bg-white px-5 py-4 sm:px-8"><VoteBrand /></header><main className="flex flex-1 flex-col items-center justify-center px-4 py-12"><div className="mb-7 flex h-24 w-24 items-center justify-center rounded-3xl border border-blue-100 bg-white/70 text-primary"><Shield size={52} strokeWidth={1.3} /></div>
      <div className="vote-panel max-w-md w-full text-center space-y-6 p-7 sm:p-10">
        <div><p className="mb-2 text-xs font-bold tracking-widest text-blue-800">NAUKMA VOTE</p><h1 className="text-2xl font-bold">Вхід у систему голосувань</h1></div>
        <p className="text-muted-foreground">
          Вхід лише для акаунтів <span className="font-medium">@ukma.edu.ua</span>
        </p>

        {sessionError && (
          <div role="alert" className="space-y-2 text-sm">
            <p>{sessionError}</p>
            <button onClick={retrySession} className="underline">Повторити перевірку сесії</button>
          </div>
        )}
        {authError && (
          <div role="alert" className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
            {Object.hasOwn(authMessages, authError)
              ? authMessages[authError]
              : "Сталася помилка входу. Спробуйте ще раз."}
          </div>
        )}

        <div className="text-left">
            <div className="mb-7 grid grid-cols-2 rounded-xl bg-slate-100 p-1">
              <button
                type="button"
                disabled={isSubmitting}
                aria-pressed={!isRegistering}
                onClick={() => switchMode(false)}
                className={`rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                  !isRegistering ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Увійти
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                aria-pressed={isRegistering}
                onClick={() => switchMode(true)}
                className={`rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                  isRegistering ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Реєстрація
              </button>
            </div>

            {visibleError && (
              <div
                role="alert"
                className="mb-5 flex gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
              >
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-rose-100 font-bold">!</span>
                <p className="leading-5">{visibleError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Університетська пошта</span>
                <span className="relative block">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-400" />
                  <input
                    type="email"
                    autoComplete={isRegistering ? "email" : "username"}
                    required
                    maxLength={255}
                    value={email}
                    onChange={event => {
                      setEmail(event.target.value);
                      clearFormError();
                    }}
                    placeholder="імʼя@ukma.edu.ua"
                    className="h-12 w-full rounded-xl border border-slate-200 bg-white pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-[#315fa8] focus:ring-4 focus:ring-blue-100"
                  />
                </span>
                {isRegistering && (
                  <span className="mt-2 block text-xs text-slate-500">
                    Підійде лише адреса, що закінчується на <strong className="font-semibold text-slate-700">@ukma.edu.ua</strong>
                  </span>
                )}
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Пароль</span>
                <span className="relative block">
                  <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-400" />
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete={isRegistering ? "new-password" : "current-password"}
                    required
                    minLength={isRegistering ? 12 : 1}
                    maxLength={1024}
                    value={password}
                    onChange={event => {
                      setPassword(event.target.value);
                      clearFormError();
                    }}
                    placeholder={isRegistering ? "Не менше 12 символів" : "Введіть ваш пароль"}
                    className="h-12 w-full rounded-xl border border-slate-200 bg-white pl-11 pr-12 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-[#315fa8] focus:ring-4 focus:ring-blue-100"
                  />
                  <button
                    type="button"
                    aria-label={showPassword ? "Приховати пароль" : "Показати пароль"}
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                  >
                    {showPassword ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
                  </button>
                </span>
                {isRegistering && (
                  <span className="mt-2 flex items-center gap-1.5 text-xs text-slate-500">
                    <Check className={`h-3.5 w-3.5 ${password.length >= 12 ? "text-emerald-600" : "text-slate-300"}`} />
                    Щонайменше 12 символів
                  </span>
                )}
              </label>

              {isRegistering && (
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-slate-700">Повторіть пароль</span>
                  <span className="relative block">
                    <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-slate-400" />
                    <input
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={1024}
                      value={confirmPassword}
                      onChange={event => {
                        setConfirmPassword(event.target.value);
                        clearFormError();
                      }}
                      placeholder="Введіть пароль ще раз"
                      aria-invalid={confirmPassword.length > 0 && !passwordsMatch}
                      className={`h-12 w-full rounded-xl border bg-white pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:ring-4 ${
                        confirmPassword.length === 0
                          ? "border-slate-200 hover:border-slate-300 focus:border-[#315fa8] focus:ring-blue-100"
                          : passwordsMatch
                            ? "border-emerald-300 focus:border-emerald-500 focus:ring-emerald-50"
                            : "border-rose-300 focus:border-rose-500 focus:ring-rose-50"
                      }`}
                    />
                  </span>
                  {confirmPassword.length > 0 && (
                    <span className={`mt-2 block text-xs ${passwordsMatch ? "text-emerald-700" : "text-rose-700"}`}>
                      {passwordsMatch ? "Паролі збігаються" : "Паролі поки не збігаються"}
                    </span>
                  )}
                </label>
              )}

              <button
                type="submit"
                disabled={isSubmitting || (isRegistering && !passwordsMatch)}
                className="group flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#0b1b3d] px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-[#142d5d] focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-55"
              >
                {isSubmitting
                  ? (isRegistering ? "Створюємо акаунт…" : "Входимо…")
                  : (isRegistering ? "Створити акаунт" : "Увійти")}
                {!isSubmitting && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />}
              </button>
            </form>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-200" />або<span className="h-px flex-1 bg-slate-200" /></div>
        <button
          disabled={isSubmitting}
          onClick={login}
          className="vote-button w-full"
        >
          Увійти через Google <ArrowRight size={17} />
        </button>
        <p className="border-t border-slate-100 pt-5 text-xs leading-relaxed text-slate-500">Для реєстрації створіть окремий пароль NaUKMA Vote. Пароль від університетської пошти вводити не потрібно.</p>
      </div></main><VoteFooter />
    </div>
  );
}
