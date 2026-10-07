// TODO: mock, замінити на реальний GET /api/elections/:id
import { useEffect, useState } from "react";
import { mockElections } from "../mocks/elections";
import type { Election } from "../types";

interface UseElectionResult {
  election: Election | null;
  isLoading: boolean;
  error: string | null;
}

export function useElection(id: string | undefined): UseElectionResult {
  const [election, setElection] = useState<Election | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError("Не вказано ідентифікатор голосування");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    const timer = setTimeout(() => {
      const found = mockElections.find((e) => e.id === id);
      if (found) {
        setElection(found);
      } else {
        setError("Голосування не знайдено");
      }
      setIsLoading(false);
    }, 400);

    return () => clearTimeout(timer);
  }, [id]);

  return { election, isLoading, error };
}