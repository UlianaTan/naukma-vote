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
  const [loaded, setLoaded] = useState<{
    id: string;
    election: Election | null;
  } | null>(null);

  useEffect(() => {
    if (!id) return;

    const timer = setTimeout(() => {
      setLoaded({ id, election: mockElections.find((e) => e.id === id) ?? null });
    }, 400);

    return () => clearTimeout(timer);
  }, [id]);

  if (!id) {
    return { election: null, isLoading: false, error: "Не вказано ідентифікатор голосування" };
  }
  if (loaded?.id !== id) {
    return { election: null, isLoading: true, error: null };
  }
  return {
    election: loaded.election,
    isLoading: false,
    error: loaded.election ? null : "Голосування не знайдено",
  };
}
