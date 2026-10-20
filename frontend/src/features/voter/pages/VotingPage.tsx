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
  return <div className="max-w-xl mx-auto px-4 py-8 space-y-4">
    <Link to="/" className="text-sm underline">← Усі голосування</Link>
    {submitError && <p role="alert" className="rounded-md bg-destructive/10 p-3 text-destructive">{submitError}</p>}
    {needsVerification && <Link to={`/vote/${id}/done`} className="block underline">Перевірити, чи враховано голос</Link>}
    {isLoading && <VoterLoading />}
    {error && <VoterError message={error} retry={reload} />}
    {election && <>
      <h1 className="text-xl font-semibold">{election.title}</h1>
      {election.description && <p className="text-muted-foreground">{election.description}</p>}
      <p className="text-sm text-muted-foreground">Початок: {formatElectionDate(election.starts_at)}<br />Завершення: {formatElectionDate(election.ends_at)}</p>
      {election.has_voted ? <div className="rounded-md bg-muted p-4">
        <p>Ви вже проголосували в цьому голосуванні.</p>
        <Link to={`/vote/${id}/done`} className="underline">Підтвердження участі</Link>
      </div> : state !== 'active' ? <p className="rounded-md bg-muted p-4">
        {state === 'upcoming' ? 'Голосування ще не почалося.' : 'Голосування закрите.'}
      </p> : <>
        <fieldset disabled={!canVote || isSubmitting} className="space-y-3 disabled:opacity-60">
          <legend className="text-sm font-medium mb-2">Оберіть кандидата:</legend>
          {election.candidates.map(candidate => <label key={candidate.id} className={`block border rounded-md p-4 cursor-pointer ${selectedCandidateId === candidate.id ? 'border-primary bg-accent' : ''}`}>
            <div className="flex items-start gap-3">
              <input type="radio" name="candidate" value={candidate.id} checked={selectedCandidateId === candidate.id} onChange={() => setSelectedCandidateId(candidate.id)} className="mt-1" />
              <div><div className="font-medium">{candidate.name}</div>{candidate.description && <div className="text-sm text-muted-foreground">{candidate.description}</div>}</div>
            </div>
          </label>)}
        </fieldset>
        <button onClick={() => void handleSubmit()} disabled={!canVote || isSubmitting || !election.candidates.some(candidate => candidate.id === selectedCandidateId)} className="w-full bg-primary text-primary-foreground rounded-md py-2.5 font-medium disabled:opacity-50">
          {isSubmitting ? 'Відправка…' : 'Проголосувати'}
        </button>
      </>}
      {election.status === 'closed' && election.results_published
        ? <Link to={`/vote/${id}/results`} className="block underline">Переглянути результати</Link>
        : <p className="text-sm text-muted-foreground">Результати будуть доступні після закриття голосування та публікації автором.</p>}
    </>}
  </div>;
}
