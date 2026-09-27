import { useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

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

        {authError === "invalid_domain" && (
          <div className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
            Увійти можна лише через університетський акаунт (@ukma.edu.ua)
          </div>
        )}
        {authError && authError !== "invalid_domain" && (
          <div className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
            Сталася помилка входу. Спробуйте ще раз.
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
