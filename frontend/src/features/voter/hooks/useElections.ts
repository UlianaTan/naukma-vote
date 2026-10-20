import { voterApi } from '../services/voterApi';
import { useVoterResource } from './useVoterResource';

export function useElections() {
  const { data, ...state } = useVoterResource('elections', voterApi.list, 'Не вдалося завантажити голосування.');
  return { elections: data ?? [], ...state };
}
