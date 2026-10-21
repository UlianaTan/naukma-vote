import { Check, ShieldCheck } from "lucide-react";
import { Link, useParams } from 'react-router-dom';
import { useElection } from '../hooks/useElection';
import { VoterError, VoterLoading } from '../components/VoterFeedback';

// Confirmation of participation only. Candidate totals belong to PublishedResultsPage.
export function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { election, isLoading, error, reload } = useElection(id);
  return <div className="vote-panel mx-auto my-8 max-w-2xl px-6 py-12 text-center space-y-6 sm:my-16 sm:px-12">
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {election && (election.has_voted ? <>
      <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 text-emerald-600" aria-hidden="true"><Check size={38} /></div>
      <h1 className="text-2xl font-bold">Ваш голос успішно зараховано!</h1>
      <p className="text-muted-foreground">Дякуємо за участь у голосуванні «{election.title}»</p>
    <p className="flex items-center justify-center gap-2 text-xs text-slate-500"><ShieldCheck size={16} />З міркувань приватності ваш вибір не відображається.</p></> : <>
      <h1 className="text-2xl font-bold">Участь ще не підтверджена</h1>
      <p>Сервер поки не підтверджує вашу участь у голосуванні «{election.title}».</p>
      <button onClick={reload} className="underline">Перевірити ще раз</button>
      <Link to={`/vote/${id}`} className="block underline">Перейти до голосування</Link>
    </>)}
    <Link to="/" className="vote-button">До списку голосувань</Link>
  </div>;
}
