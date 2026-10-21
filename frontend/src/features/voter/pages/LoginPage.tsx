import { Shield, ArrowRight } from "lucide-react";
import { VoteBrand, VoteFooter } from "../../../components/layout/VoterLayout";
import { useSearchParams } from "react-router-dom";
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
  const { login, sessionError, retrySession } = useAuth();
  const [searchParams] = useSearchParams();
  const authError = searchParams.get("error");

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

        <button
          onClick={login}
          className="vote-button w-full"
        >
          Увійти через Google <ArrowRight size={17} />
        </button>
        <p className="border-t border-slate-100 pt-5 text-xs leading-relaxed text-slate-500">Використовуйте Google-акаунт із підтвердженою університетською адресою @ukma.edu.ua.</p>
      </div></main><VoteFooter />
    </div>
  );
}
