import { Link, useParams } from 'react-router-dom';
import { useElection } from '../hooks/useElection';
import { VoterError, VoterLoading } from '../components/VoterFeedback';

// Confirmation of participation only. Candidate totals belong to PublishedResultsPage.
export function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { election, isLoading, error, reload } = useElection(id);
  return <div className="max-w-xl mx-auto px-4 py-12 text-center space-y-4">
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {election && (election.has_voted ? <>
      <div className="text-4xl" aria-hidden="true">✅</div>
      <h1 className="text-xl font-semibold">Ваш голос враховано</h1>
      <p className="text-muted-foreground">Дякуємо за участь у голосуванні «{election.title}»</p>
    </> : <>
      <h1 className="text-xl font-semibold">Участь ще не підтверджена</h1>
      <p>Сервер поки не підтверджує вашу участь у голосуванні «{election.title}».</p>
      <button onClick={reload} className="underline">Перевірити ще раз</button>
      <Link to={`/vote/${id}`} className="block underline">Перейти до голосування</Link>
    </>)}
    <Link to="/" className="inline-block bg-primary text-primary-foreground rounded-md px-5 py-2.5 font-medium">До списку голосувань</Link>
  </div>;
}
