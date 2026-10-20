import { useRef, useState } from 'react';
import { sessionEpoch } from '../../../lib/session';
import { voterApi, voterError, VoteUncertainError } from '../services/voterApi';

export function useSubmitVote() {
  const pending = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);

  async function submitVote(electionId: string, candidateId: string) {
    if (pending.current || needsVerification) return null;
    pending.current = true;
    setIsSubmitting(true);
    setError(null);
    const epoch = sessionEpoch();
    try {
      await voterApi.vote(electionId, candidateId);
      return epoch === sessionEpoch();
    } catch (error) {
      if (epoch === sessionEpoch()) {
        setNeedsVerification(error instanceof VoteUncertainError);
        setError(error instanceof VoteUncertainError ? error.message : voterError(error, 'Не вдалося відправити голос.'));
      }
      return false;
    } finally {
      pending.current = false;
      setIsSubmitting(false);
    }
  }

  return { submitVote, isSubmitting, error, needsVerification };
}
