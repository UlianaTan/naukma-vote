import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useElections } from "../hooks/useElections";

export function ElectionsListPage() {
  const { user, logout } = useAuth();
  const { elections, isLoading, error } = useElections();

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-xl font-semibold">Активні голосування</h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{user?.email}</span>
          <button onClick={logout} className="underline">
            Вийти
          </button>
        </div>
      </header>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-muted rounded-md animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && error && (
        <div className="bg-destructive/10 text-destructive rounded-md p-4 text-sm">
          {error}
        </div>
      )}

      {!isLoading && !error && elections.length === 0 && (
        <div className="text-center text-muted-foreground py-12">
          Наразі немає доступних голосувань
        </div>
      )}

      {!isLoading && !error && elections.length > 0 && (
        <ul className="space-y-3">
          {elections.map((election) => (
            <li key={election.id}>
              <Link
                to={`/vote/${election.id}`}
                className="block border rounded-md p-4 hover:bg-accent transition-colors"
              >
                <h2 className="font-medium">{election.title}</h2>
                <p className="text-sm text-muted-foreground mt-1">{election.description}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
