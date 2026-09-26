import { useEffect, useState } from "react";
import { mockElections } from "../mocks/elections";
import type { Election } from "../types";

interface UseElectionsResult {
  elections: Election[];
  isLoading: boolean;
  error: string | null;
}

export function useElections(): UseElectionsResult {
  const [elections, setElections] = useState<Election[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        setElections(mockElections.filter((e) => e.status === "active"));
        setIsLoading(false);
      } catch {
        setError("Не вдалося завантажити список голосувань");
        setIsLoading(false);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  return { elections, isLoading, error };
}
