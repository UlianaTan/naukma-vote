import { api, ApiError } from './api';

export type SessionResult<T> =
  | { kind: 'authenticated'; user: T }
  | { kind: 'anonymous' }
  | { kind: 'unavailable' };

// A failed connection says nothing about whether browser cookies are valid.
export async function loadSession<T>(): Promise<SessionResult<T>> {
  try { return { kind: 'authenticated', user: await api.get<T>('/api/auth/me') }; }
  catch (error) {
    return error instanceof ApiError && error.status === 401
      ? { kind: 'anonymous' } : { kind: 'unavailable' };
  }
}
