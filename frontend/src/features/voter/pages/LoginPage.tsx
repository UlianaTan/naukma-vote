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
  const { login } = useAuth();
  const [searchParams] = useSearchParams();
  const authError = searchParams.get("error");

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="max-w-sm w-full text-center space-y-6">
        <h1 className="text-2xl font-semibold">NaUKMA Vote</h1>
        <p className="text-muted-foreground">
          Вхід лише для акаунтів <span className="font-medium">@ukma.edu.ua</span>
        </p>

        {authError && (
          <div role="alert" className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
            {Object.hasOwn(authMessages, authError)
              ? authMessages[authError]
              : "Сталася помилка входу. Спробуйте ще раз."}
          </div>
        )}

        <button
          onClick={login}
          className="w-full bg-primary text-primary-foreground rounded-md py-2.5 font-medium"
        >
          Увійти через Google
        </button>
      </div>
    </div>
  );
}
