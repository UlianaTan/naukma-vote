import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  GraduationCap,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { login, register, clearError, error } = useAuth();
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
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
        await login(email, password);
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
    <main className="min-h-screen bg-[#f3f6fb] p-3 sm:p-6 lg:p-10">
      <div className="mx-auto grid min-h-[min(780px,calc(100vh-3rem))] w-full max-w-6xl overflow-hidden rounded-[28px] bg-white shadow-[0_24px_80px_-32px_rgba(15,35,74,0.3)] lg:grid-cols-[0.92fr_1.08fr]">
        <aside className="relative hidden overflow-hidden bg-[#0b1b3d] px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-14">
          <div className="absolute -right-36 -top-28 h-96 w-96 rounded-full border border-white/10" />
          <div className="absolute -right-20 -top-12 h-64 w-64 rounded-full border border-white/10" />
          <div className="absolute -bottom-40 -left-28 h-96 w-96 rounded-full bg-[#2c5daf]/25 blur-3xl" />

          <div className="relative">
            <div className="flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/15">
                <GraduationCap className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold tracking-tight">NaUKMA Vote</p>
                <p className="text-xs text-blue-100/65">Вибори НаУКМА</p>
              </div>
            </div>
          </div>

          <div className="relative max-w-md pb-4">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-xs text-blue-100">
              <Sparkles className="h-3.5 w-3.5" />
              Голос кожного має значення
            </div>
            <h1 className="text-4xl font-semibold leading-[1.12] tracking-tight xl:text-[46px]">
              Твоя спільнота.
              <br />
              Твій вибір.
            </h1>
            <p className="mt-5 max-w-sm text-sm leading-6 text-blue-100/70">
              Бери участь у голосуваннях університетської спільноти — просто,
              зручно та з будь-якого пристрою.
            </p>
            <div className="mt-9 flex items-center gap-3 text-sm text-blue-100/80">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-emerald-400/15 text-emerald-200">
                <ShieldCheck className="h-4 w-4" />
              </span>
              Захищений вхід для спільноти НаУКМА
            </div>
          </div>

          <p className="relative text-xs text-blue-100/45">Національний університет «Києво-Могилянська академія»</p>
        </aside>

        <section className="flex items-center justify-center px-5 py-8 sm:px-10 sm:py-12 lg:px-12 xl:px-16">
          <div className="w-full max-w-[430px]">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#0b1b3d] text-white">
                <GraduationCap className="h-5 w-5" />
              </div>
              <div>
                <p className="font-semibold text-slate-900">NaUKMA Vote</p>
                <p className="text-xs text-slate-500">Вибори НаУКМА</p>
              </div>
            </div>

            <div className="mb-8">
              <p className="mb-2 text-sm font-medium text-[#315fa8]">
                {isRegistering ? "Новий обліковий запис" : "Раді вас бачити"}
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                {isRegistering ? "Створити акаунт" : "Вхід до системи"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {isRegistering
                  ? "Зареєструйтеся з університетською поштою, щоб долучитися до голосувань."
                  : "Увійдіть, щоб переглянути доступні голосування."}
              </p>
            </div>

            <div className="mb-7 grid grid-cols-2 rounded-xl bg-slate-100 p-1">
              <button
                type="button"
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

            <div className="mt-6 flex items-start gap-2.5 rounded-xl bg-slate-50 px-3.5 py-3 text-xs leading-5 text-slate-500">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#315fa8]" />
              <p>
                Реєстрація відкрита лише для пошти НаУКМА. Підтвердження від адміністратора не потрібне.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
