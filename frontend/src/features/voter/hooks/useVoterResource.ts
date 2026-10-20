import { useCallback, useEffect, useState } from 'react';
import { sessionEpoch } from '../../../lib/session';
import { voterError } from '../services/voterApi';

export function useVoterResource<T>(key: string, load: () => Promise<T>, fallback: string) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ key: string; attempt: number; data: T | null; error: string | null } | null>(null);
  const reload = useCallback(() => setAttempt(value => value + 1), []);
  useEffect(() => {
    let active = true;
    const epoch = sessionEpoch();
    Promise.resolve().then(load).then(
      data => { if (active && epoch === sessionEpoch()) setState({ key, attempt, data, error: null }); },
      error => { if (active && epoch === sessionEpoch()) setState({ key, attempt, data: null, error: voterError(error, fallback) }); },
    );
    return () => { active = false; };
  }, [key, attempt, load, fallback]);
  const current = state?.key === key && state.attempt === attempt;
  return { data: current ? state.data : null, error: current ? state.error : null, isLoading: !current, reload };
}
