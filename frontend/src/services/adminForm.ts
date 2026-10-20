import axios from 'axios';
import type { AdminElection } from './adminApi';

// SQLite serializes backend UTC dates without an offset; PostgreSQL includes it.
function serverDate(value: string): Date {
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : value + 'Z');
}

export function localDateTime(value: string): string {
  const date = serverDate(value);
  if (!Number.isFinite(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// A one-column CSV/TXT: optional email header, quoted cells, comma/semicolon/newline separators.
export function parseVoterEmails(text: string): string[] {
  return [...new Set(text.replace(/^\uFEFF/, '').split(/[\r\n,;]+/)
    .map(value => value.trim().replace(/^"(.*)"$/, '$1').trim().toLowerCase())
    .filter(value => value && !['email', 'email address', 'електронна пошта'].includes(value)))];
}

export function adminStatus(election: Pick<AdminElection, 'status' | 'starts_at' | 'ends_at'>, now = Date.now()) {
  if (election.status === 'draft') return 'Чернетка';
  if (election.status === 'closed') return 'Завершено';
  if (now >= serverDate(election.ends_at).getTime()) return 'Час голосування минув — очікується закриття';
  if (now < serverDate(election.starts_at).getTime()) return 'Очікує початку';
  return 'Триває';
}

export function uncertainMutation(error: unknown) {
  return !axios.isAxiosError(error) || !error.response || error.response.status >= 500;
}

export function adminError(error: unknown): string {
  if (!axios.isAxiosError(error)) return 'Не вдалося підтвердити виконання дії. Перевірте стан і повторіть спробу.';
  if (!error.response) return 'Немає зв’язку із сервером. Перевірте з’єднання.';
  const status = error.response.status;
  if (status === 401) return 'Сесія завершилася. Увійдіть знову.';
  if (status === 403) return 'Керувати голосуванням може лише його автор.';
  if (status === 404) return 'Голосування або запис не знайдено. Оновіть дані.';
  if (status >= 500) return 'Сервіс тимчасово недоступний. Перевірте стан перед повтором.';
  if (status === 422) return 'Перевірте поля: назву, кандидатів, початок і завершення голосування.';
  if (status === 409) return 'Дані вже змінилися або такий запис уже існує. Оновіть стан.';
  return 'Дію не дозволено для поточного стану голосування. Оновіть дані.';
}

export async function syncCandidates(
  api: {
    getElectionDetail: (id: string) => Promise<AdminElection>;
    removeCandidate: (id: string, candidateId: string) => Promise<unknown>;
    addCandidate: (id: string, data: { name: string; description?: string }) => Promise<unknown>;
  },
  id: string,
  names: string[],
) {
  const current = await api.getElectionDetail(id);
  if (current.status !== 'draft') throw new Error('Election is no longer a draft');
  for (const candidate of current.candidates) {
    if (!names.includes(candidate.name)) await api.removeCandidate(id, candidate.id);
  }
  for (const name of names) {
    if (!current.candidates.some(candidate => candidate.name === name)) await api.addCandidate(id, { name });
  }
  return api.getElectionDetail(id);
}
