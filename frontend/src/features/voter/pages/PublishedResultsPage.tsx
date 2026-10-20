import { Link, useParams } from 'react-router-dom';
import { usePublishedResults } from '../hooks/usePublishedResults';
import { VoterError, VoterLoading } from '../components/VoterFeedback';
import { formatElectionDate } from '../electionState';

export function PublishedResultsPage() {
  const { id } = useParams<{ id: string }>();
  // This endpoint is available to every signed-in user after publication.
  // Do not fetch whitelist-restricted election details to gate this page.
  const { results, isLoading, error, reload } = usePublishedResults(id);
  return <div className="max-w-2xl mx-auto px-4 py-8 space-y-4">
    <Link to="/" className="text-sm underline">← Усі голосування</Link>
    <h1 className="text-xl font-semibold">Опубліковані результати</h1>
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {results && <>
      <h2 className="text-lg font-medium">{results.title}</h2>
      {results.closed_at && <p className="text-sm text-muted-foreground">Закрито: {formatElectionDate(results.closed_at)}</p>}
      <p>Усього голосів: {results.total_votes}</p>
      {results.outcome === 'no_votes' ? <p>У цьому голосуванні не подано жодного голосу.</p>
        : <p className="font-medium">{results.outcome === 'tie' ? 'Нічия: ' : 'Переможець: '}
          {results.results.filter(candidate => results.winner_ids.includes(candidate.candidate_id)).map(candidate => candidate.name).join(', ')}
        </p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Кількість голосів за кандидатів</caption>
          <thead><tr className="border-b"><th className="py-3 pr-3">Кандидат</th><th className="py-3 pr-3">Голоси</th><th className="py-3">Відсоток</th></tr></thead>
          <tbody>{results.results.map(candidate => <tr key={candidate.candidate_id} className="border-b">
            <td className="py-3 pr-3">{candidate.name}</td><td className="py-3 pr-3">{candidate.votes_count}</td><td className="py-3">{candidate.percent.toLocaleString('uk-UA', { maximumFractionDigits: 2 })}%</td>
          </tr>)}</tbody>
        </table>
      </div>
      <button onClick={reload} className="underline">Оновити результати</button>
    </>}
  </div>;
}
