import { Info, UserRound } from "lucide-react";
import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useElection } from '../hooks/useElection';
import { useSubmitVote } from '../hooks/useSubmitVote';
import { electionState, formatElectionDate } from '../electionState';
import { VoterError, VoterLoading } from '../components/VoterFeedback';

export function VotingPage() {
  const { id } = useParams<{ id: string }>();
  return <VotingForm key={id} id={id} />;
}

function VotingForm({ id }: { id: string | undefined }) {
  const navigate = useNavigate();
  const { election, isLoading, error, reload } = useElection(id);
  const { submitVote, isSubmitting, error: submitError, needsVerification } = useSubmitVote();
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  async function handleSubmit() {
    if (!id || !election || !selectedCandidateId || election.has_voted || electionState(election) !== 'active') return;
    const accepted = await submitVote(id, selectedCandidateId);
    if (accepted === true) navigate(`/vote/${id}/done`);
    else if (accepted === false) reload();
  }

  const state = election ? electionState(election, now) : null;
  const canVote = election && state === 'active' && !election.has_voted && !needsVerification;
  return <div className="mx-auto max-w-6xl space-y-6">
    <Link to="/" className="vote-back">← Усі голосування</Link>
    {submitError && <p role="alert" className="rounded-md bg-destructive/10 p-3 text-destructive">{submitError}</p>}
    {needsVerification && <Link to={`/vote/${id}/done`} className="block underline">Перевірити, чи враховано голос</Link>}
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {election && <>
      <h1 className="text-2xl font-bold sm:text-3xl">{election.title}</h1>
      {election.description && <p className="text-muted-foreground">{election.description}</p>}
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">Початок: {formatElectionDate(election.starts_at)}<br />Завершення: {formatElectionDate(election.ends_at)}</p>
      {election.has_voted ? <div className="rounded-md bg-muted p-4">
        <p>Ви вже проголосували в цьому голосуванні.</p>
        <Link to={`/vote/${id}/done`} className="underline">Підтвердження участі</Link>
      </div> : state !== 'active' ? <p className="rounded-md bg-muted p-4">
        {state === 'upcoming' ? 'Голосування ще не почалося.' : 'Голосування закрите.'}
      </p> : <>
        <div className="flex gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800"><Info size={20} className="shrink-0" /><p><strong>Ознайомтеся з кандидатами та зробіть свій вибір</strong><span className="mt-1 block text-xs leading-relaxed">Ви можете обрати лише одного кандидата. Після зарахування голосу змінити вибір неможливо.</span></p></div>
        <fieldset disabled={!canVote || isSubmitting} className="space-y-3 disabled:opacity-60">
          <legend className="text-sm font-semibold mb-3">Оберіть кандидата:</legend>
          {election.candidates.map(candidate => <label key={candidate.id} className={`vote-panel block p-5 cursor-pointer transition-colors ${selectedCandidateId === candidate.id ? '!border-blue-500 ring-1 ring-blue-500' : ''}`}>
            <div className="flex items-center gap-4">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-400" aria-hidden="true"><UserRound size={23} /></span>
              <input type="radio" name="candidate" value={candidate.id} checked={selectedCandidateId === candidate.id} onChange={() => setSelectedCandidateId(candidate.id)} className="order-last ml-auto h-5 w-5 shrink-0 accent-emerald-600" />
              <div className="min-w-0 break-words"><div className="font-medium">{candidate.name}</div>{candidate.description && <div className="mt-1 text-sm leading-relaxed text-muted-foreground">{candidate.description}</div>}</div>
            </div>
          </label>)}
        </fieldset>
        <button onClick={() => void handleSubmit()} disabled={!canVote || isSubmitting || !election.candidates.some(candidate => candidate.id === selectedCandidateId)} className="vote-button w-full sm:ml-auto sm:flex sm:w-auto">
          {isSubmitting ? 'Відправка…' : 'Проголосувати'}
        </button>
      </>}
      {election.status === 'closed' && election.results_published
        ? <Link to={`/vote/${id}/results`} className="block underline">Переглянути результати</Link>
        : <p className="mt-1 text-sm leading-relaxed text-muted-foreground">Результати будуть доступні після закриття голосування та публікації автором.</p>}
    </>}
  </div>;
}
