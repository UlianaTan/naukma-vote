import type { Election } from './types';

export function electionState(election: Election, now = Date.now()) {
  if (election.status === 'closed' || now >= Date.parse(election.ends_at)) return 'closed';
  if (election.status === 'draft' || now < Date.parse(election.starts_at)) return 'upcoming';
  return 'active';
}

export const electionStateLabel = { active: 'Триває', upcoming: 'Ще не почалося', closed: 'Закрите' };
export function formatElectionDate(value: string) {
  return new Date(value).toLocaleString('uk-UA', { dateStyle: 'medium', timeStyle: 'short' });
}
