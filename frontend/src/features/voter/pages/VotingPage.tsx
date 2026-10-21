import { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useElection } from "../hooks/useElection";
import { useSubmitVote } from "../hooks/useSubmitVote";

export function VotingPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { election, isLoading, error } = useElection(id);
  const { submitVote, isSubmitting, error: submitError } = useSubmitVote();
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  async function handleSubmit() {
    if (!id || !selectedCandidateId) return;
    try {
      await submitVote(id, selectedCandidateId);
      navigate(`/vote/${id}/done`);
    } catch {
      // помилка вже збережена в submitError
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-xl mx-auto px-4 py-8 space-y-4">
        <div className="h-6 bg-muted rounded w-2/3 animate-pulse" />
        <div className="h-24 bg-muted rounded animate-pulse" />
      </div>
    );
  }

  if (error || !election) {
    return (
      <div className="max-w-xl mx-auto px-4 py-8">
        <div className="bg-destructive/10 text-destructive rounded-md p-4 text-sm">
          {error ?? "Голосування не знайдено"}
        </div>
        <Link to="/" className="inline-block mt-4 underline text-sm">
          ← Повернутись до списку
        </Link>
      </div>
    );
  }

  if (election.status !== "active") {
    return (
      <div className="max-w-xl mx-auto px-4 py-8">
        <div className="bg-muted text-muted-foreground rounded-md p-4 text-sm">
          Це голосування наразі {election.status === "closed" ? "закрите" : "ще не почалось"}.
        </div>
        <Link to="/" className="inline-block mt-4 underline text-sm">
          ← Повернутись до списку
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <Link to="/" className="text-sm text-muted-foreground underline">
        ← Усі голосування
      </Link>

      <h1 className="text-xl font-semibold mt-4">{election.title}</h1>
      <p className="text-muted-foreground mt-1">{election.description}</p>

      <fieldset className="mt-6 space-y-3">
        <legend className="text-sm font-medium mb-2">Оберіть кандидата:</legend>
        {election.candidates.map((candidate) => (
          <label
            key={candidate.id}
            className={`block border rounded-md p-4 cursor-pointer transition-colors ${
              selectedCandidateId === candidate.id
                ? "border-primary bg-accent"
                : "hover:bg-accent/50"
            }`}
          >
            <div className="flex items-start gap-3">
              <input
                type="radio"
                name="candidate"
                value={candidate.id}
                checked={selectedCandidateId === candidate.id}
                onChange={() => setSelectedCandidateId(candidate.id)}
                className="mt-1"
              />
              <div>
                <div className="font-medium">{candidate.name}</div>
                <div className="text-sm text-muted-foreground mt-0.5">
                  {candidate.description}
                </div>
              </div>
            </div>
          </label>
        ))}
      </fieldset>

      {submitError && (
        <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm mt-4">
          {submitError}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!selectedCandidateId || isSubmitting}
        className="w-full bg-primary text-primary-foreground rounded-md py-2.5 font-medium mt-6 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? "Відправка..." : "Проголосувати"}
      </button>
    </div>
  );
}
