import { useCallback } from 'react';
import { voterApi } from '../services/voterApi';
import { useVoterResource } from './useVoterResource';

export function useElection(id: string | undefined) {
  const load = useCallback(() => voterApi.get(id ?? ''), [id]);
  const { data, ...state } = useVoterResource(id ?? '', load, 'Не вдалося завантажити голосування.');
  return { election: data, ...state };
}
