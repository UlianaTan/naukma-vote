import axios from 'axios';
import type { AdminElection, AdminElectionResults } from './adminApi';

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

export interface DraftCandidate { id?: string; name: string }

export async function syncCandidates(
  api: {
    getElectionDetail: (id: string) => Promise<AdminElection>;
    removeCandidate: (id: string, candidateId: string) => Promise<unknown>;
    addCandidate: (id: string, data: { name: string }) => Promise<unknown>;
    updateCandidate: (id: string, candidateId: string, data: { name: string }) => Promise<unknown>;
  },
  id: string,
  desired: DraftCandidate[],
) {
  const current = await api.getElectionDetail(id);
  if (current.status !== 'draft') throw new Error('Election is no longer a draft');
  // New rows can already exist after a lost add response. Match those by name;
  // existing rows always retain identity even when the name changes.
  const targets = desired.map(row => ({ ...row,
    id: row.id ?? current.candidates.find(candidate => candidate.name === row.name)?.id }));
  for (const row of targets) {
    if (row.id && !current.candidates.some(candidate => candidate.id === row.id)) {
      throw new Error('Кандидата змінено в іншому вікні. Оновіть чернетку.');
    }
  }
  for (const candidate of current.candidates) {
    if (!targets.some(row => row.id === candidate.id)) await api.removeCandidate(id, candidate.id);
  }
  for (const row of targets) {
    if (row.id) {
      if (current.candidates.find(candidate => candidate.id === row.id)?.name !== row.name) {
        await api.updateCandidate(id, row.id, { name: row.name });
      }
    } else await api.addCandidate(id, { name: row.name });
  }
  return api.getElectionDetail(id);
}

export async function reconcilePublication(
  api: {
    publishResults: (id: string) => Promise<unknown>;
    unpublishResults: (id: string) => Promise<unknown>;
    getAdminResults: (id: string) => Promise<AdminElectionResults>;
  },
  id: string,
  published: boolean,
) {
  let actionError = '';
  try {
    if (published) await api.publishResults(id);
    else await api.unpublishResults(id);
  } catch (error) { actionError = adminError(error); }
  try {
    const results = await api.getAdminResults(id);
    // A failed/lost mutation response is resolved only by the requested state,
    // not merely by a successful GET.
    if (results.results_published === published) actionError = '';
    else actionError ||= 'Зміну публікації не підтверджено. Повторіть дію.';
    return { results, actionError, loadError: '' };
  } catch (error) {
    return { results: null, actionError: actionError || 'Не вдалося підтвердити стан публікації. Оновіть результати перед наступною дією.', loadError: adminError(error) };
  }
}
