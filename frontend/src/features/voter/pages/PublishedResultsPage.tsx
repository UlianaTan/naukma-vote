import { Link, useParams } from 'react-router-dom';
import { usePublishedResults } from '../hooks/usePublishedResults';
import { VoterError, VoterLoading } from '../components/VoterFeedback';
import { formatElectionDate } from '../electionState';

export function PublishedResultsPage() {
  const { id } = useParams<{ id: string }>();
  // This endpoint is available to every signed-in user after publication.
  // Do not fetch whitelist-restricted election details to gate this page.
  const { results, isLoading, error, reload } = usePublishedResults(id);
  return <div className="mx-auto max-w-6xl space-y-6">
    <Link to="/" className="vote-back">← Усі голосування</Link>
    <h1 className="text-2xl font-bold sm:text-3xl">Опубліковані результати</h1>
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {results && <>
      <h2 className="text-xl font-semibold">{results.title}</h2>
      {results.closed_at && <p className="text-sm text-muted-foreground">Закрито: {formatElectionDate(results.closed_at)}</p>}
      <div className="vote-panel p-6"><p className="text-sm text-slate-500">Усього зарахованих голосів</p><p className="mt-2 text-3xl font-bold">{results.total_votes}</p></div>
      {results.outcome === 'no_votes' ? <p>У цьому голосуванні не подано жодного голосу.</p>
        : <p className="font-medium">{results.outcome === 'tie' ? 'Нічия: ' : 'Переможець: '}
          {results.results.filter(candidate => results.winner_ids.includes(candidate.candidate_id)).map(candidate => candidate.name).join(', ')}
        </p>}
      <ul className="space-y-4" aria-label="Результати за кандидатами">{results.results.map(candidate => {
        const winner = results.winner_ids.includes(candidate.candidate_id);
        return <li key={candidate.candidate_id} className={`vote-panel p-5 sm:p-6 ${winner ? '!border-emerald-400' : ''}`}>
          <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-semibold">{candidate.name}</h3><span className={winner ? 'text-sm font-semibold text-emerald-700' : 'text-sm text-slate-500'}>{candidate.percent.toLocaleString('uk-UA', { maximumFractionDigits: 2 })}% · {candidate.votes_count} голосів</span></div>
          {winner && <p className="mt-2 text-xs font-medium text-emerald-700">{results.outcome === 'tie' ? 'Найбільша кількість голосів · нічия' : 'Переможець'}</p>}
          <div role="progressbar" aria-label={candidate.name} aria-valuenow={candidate.percent} aria-valuemin={0} aria-valuemax={100} className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${winner ? 'bg-emerald-500' : 'bg-slate-400'}`} style={{width: `${Math.min(100, Math.max(0, candidate.percent))}%`}} /></div>
        </li>;
      })}</ul>
      <button onClick={reload} className="vote-button-secondary">Оновити результати</button>
    </>}
  </div>;
}
