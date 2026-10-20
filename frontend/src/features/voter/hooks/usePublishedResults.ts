import { useCallback } from 'react';
import { voterApi } from '../services/voterApi';
import { useVoterResource } from './useVoterResource';

export function usePublishedResults(id: string | undefined) {
  const load = useCallback(() => voterApi.results(id ?? ''), [id]);
  const { data, ...state } = useVoterResource(id ?? '', load, 'Не вдалося завантажити результати.');
  return { results: data, ...state };
}
