import { clearSession, sessionFetch } from './session';
export { API_BASE_URL, ApiError } from './session';

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await sessionFetch(path, {
    ...options, headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (path === '/api/auth/logout') clearSession();
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) => request<T>(path, {
    method: 'POST', body: body === undefined ? undefined : JSON.stringify(body),
  }),
};
