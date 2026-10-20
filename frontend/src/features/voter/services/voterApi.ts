import { api, ApiError } from '../../../lib/api';
import type { Election, PublishedResults, SubmitVoteResponse } from '../types';

function electionPath(id: string) {
  if (!/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(id)) {
    throw new Error('Некоректне посилання на голосування.');
  }
  return `/api/v1/elections/${id}`;
}

export function voterError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Сесія завершилася. Увійдіть знову.';
    if (error.status >= 500) return 'Сервіс тимчасово недоступний. Спробуйте пізніше.';
    // Show only known user-facing backend messages, never a raw JSON body or traceback.
    try {
      const detail: unknown = JSON.parse(error.message).detail;
      if (typeof detail === 'string' && [
        'Голосування не знайдено', 'Вас немає у списку виборців для цього голосування',
        'Ви вже проголосували в цьому голосуванні', 'Голосування ще не розпочалось',
        'Голосування наразі не активне або завершилось', 'Недійсний кандидат для цього голосування',
        'Результати доступні лише після закриття голосування', 'Результати ще не опубліковані організатором',
      ].includes(detail)) return detail;
    } catch { /* Non-JSON error responses use the status fallback. */ }
    if (error.status === 403) return 'Немає доступу до цієї дії.';
    if (error.status === 404) return 'Голосування не знайдено.';
    if (error.status === 409) return 'Ви вже проголосували в цьому голосуванні.';
    if (error.status === 422) return 'Некоректні дані запиту. Оновіть сторінку.';
    return fallback;
  }
  if (error instanceof TypeError) return 'Не вдалося зв’язатися із сервером. Перевірте з’єднання та повторіть спробу.';
  if (error instanceof Error && error.message === 'Некоректне посилання на голосування.') return error.message;
  return fallback;
}

export class VoteUncertainError extends Error {
  constructor() {
    super('Не вдалося підтвердити збереження голосу. Перевірте його стан перед наступною дією.');
    this.name = 'VoteUncertainError';
  }
}

export const voterApi = {
  list: () => api.get<Election[]>('/api/v1/elections'),
  get: (id: string) => api.get<Election>(electionPath(id)),
  results: (id: string) => api.get<PublishedResults>(`${electionPath(id)}/results`),
  async vote(id: string, candidateId: string): Promise<SubmitVoteResponse> {
    const path = electionPath(id);
    if (!candidateId) throw new Error('Оберіть кандидата перед відправкою.');
    try {
      const result = await api.post<SubmitVoteResponse>(`${path}/vote`, { candidate_id: candidateId });
      if (result.status !== 'success') throw new VoteUncertainError();
      return result;
    } catch (error) {
      const duplicate = error instanceof ApiError && error.status === 409;
      const uncertain = !(error instanceof ApiError) || error.status >= 500;
      if (!duplicate && !uncertain) throw error;
      // A lost response is not proof that the transaction failed. Never resend POST automatically.
      try {
        if ((await voterApi.get(id)).has_voted) {
          return { status: 'success', message: 'Ваш голос враховано' };
        }
      } catch { /* Keep the result uncertain if participation could not be checked. */ }
      if (duplicate) throw error;
      throw new VoteUncertainError();
    }
  },
};
