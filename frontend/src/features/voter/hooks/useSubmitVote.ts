// TODO: mock, замінити на реальний POST /api/elections/:id/vote
import { useState } from "react";
import type { SubmitVoteResponse } from "../types";

interface UseSubmitVoteResult {
  submitVote: (electionId: string, candidateId: string) => Promise<SubmitVoteResponse>;
  isSubmitting: boolean;
  error: string | null;
}

const ALREADY_VOTED_ELECTION_IDS = new Set<string>();

export function useSubmitVote(): UseSubmitVoteResult {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitVote(electionId: string, candidateId: string): Promise<SubmitVoteResponse> {
    setIsSubmitting(true);
    setError(null);

    try {
      await new Promise((resolve) => setTimeout(resolve, 600));

      if (ALREADY_VOTED_ELECTION_IDS.has(electionId)) {
        throw new Error("Ви вже проголосували в цьому голосуванні");
      }
      if (!candidateId) {
        throw new Error("Оберіть кандидата перед відправкою");
      }

      ALREADY_VOTED_ELECTION_IDS.add(electionId);
      return { success: true, votedAt: new Date().toISOString() };
    } catch (e) {
      const message = e instanceof Error ? e.message : "Не вдалося відправити голос";
      setError(message);
      throw e;
    } finally {
      setIsSubmitting(false);
    }
  }

  return { submitVote, isSubmitting, error };
}