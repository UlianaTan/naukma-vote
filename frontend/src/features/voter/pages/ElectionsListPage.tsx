import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { VoterError } from "../components/VoterFeedback";
import { electionState, electionStateLabel, formatElectionDate } from "../electionState";
import { useElections } from "../hooks/useElections";

export function ElectionsListPage() {
  const { user, logout, error: authError } = useAuth();
  const { elections, isLoading, error, reload } = useElections();

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-xl font-semibold">Мої доступні голосування</h1>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{user?.email}</span>
          <button onClick={logout} className="underline">
            Вийти
          </button>
        </div>
      </header>

      {authError && <p role="alert" className="mb-4 text-destructive">{authError}</p>}

      <Link to="/admin" className="inline-block mb-6 underline">Мої голосування — створити та керувати</Link>

      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 bg-muted rounded-md animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && error && <VoterError message={error} retry={reload} />}

      <button onClick={reload} disabled={isLoading} className="block mb-4 underline disabled:opacity-50">Оновити список</button>

      {!isLoading && !error && elections.length === 0 && (
        <div className="text-center text-muted-foreground py-12">
          Наразі немає доступних голосувань
        </div>
      )}

      {!isLoading && !error && elections.length > 0 && (
        <ul className="space-y-3">
          {elections.map(election => {
            const state = electionState(election);
            return <li key={election.id} className="border rounded-md p-4 space-y-2">
              <h2 className="font-medium">{election.title}</h2>
              {election.description && <p className="text-sm text-muted-foreground">{election.description}</p>}
              <p className="text-sm">{electionStateLabel[state]}{election.has_voted ? ' · Ви вже проголосували' : ''}</p>
              <p className="text-sm text-muted-foreground">{formatElectionDate(election.starts_at)} — {formatElectionDate(election.ends_at)}</p>
              <div className="flex flex-wrap gap-4 text-sm underline">
                <Link to={election.has_voted ? `/vote/${election.id}/done` : `/vote/${election.id}`}>
                  {election.has_voted ? 'Підтвердження участі' : state === 'active' ? 'Голосувати' : 'Переглянути голосування'}
                </Link>
                {election.status === 'closed' && election.results_published && <Link to={`/vote/${election.id}/results`}>Переглянути результати</Link>}
              </div>
              {state === 'closed' && !election.results_published && <p className="text-sm text-muted-foreground">Результати ще не опубліковані автором.</p>}
            </li>;
          })}
        </ul>
      )}
    </div>
  );
}
