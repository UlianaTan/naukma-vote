export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
export const SESSION_EXPIRED_EVENT = 'naukma:session-expired';

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

let csrfToken: string | null = null;
let csrfPending: Promise<string> | null = null;
let refreshPending: Promise<void> | null = null;
let version = 0;

export function sessionVersion() { return version; }
export function clearSession() {
  csrfToken = null;
  version++;
}
export function sessionExpired() {
  clearSession();
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}
export function isMutation(method = 'GET') {
  return !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase());
}
export function canRefresh(path: string) {
  return !['/api/auth/login', '/api/auth/refresh', '/api/auth/logout', '/api/auth/csrf', '/api/auth/google/']
    .some(endpoint => path.startsWith(endpoint));
}

async function checked(response: Response) {
  if (!response.ok) throw new ApiError(response.status, await response.text() || response.statusText);
  return response;
}

export async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfPending) {
    csrfPending = (async () => {
      const response = await checked(await fetch(`${API_BASE_URL}/api/auth/csrf`, { credentials: 'include', cache: 'no-store' }));
      const data: { csrf_token: string } = await response.json();
      csrfToken = data.csrf_token;
      return csrfToken;
    })().finally(() => { csrfPending = null; });
  }
  return csrfPending;
}

export async function refreshSession(requestVersion: number): Promise<void> {
  if (refreshPending) return refreshPending;
  if (requestVersion !== version) return;
  refreshPending = (async () => {
    try {
      const token = await getCsrfToken();
      await checked(await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': token },
      }));
      version++;
    } catch (error) {
      // Temporary network failures do not sign the user out.
      if (error instanceof ApiError && [401, 403].includes(error.status)) sessionExpired();
      throw error;
    }
  })().finally(() => { refreshPending = null; });
  return refreshPending;
}

export async function sessionFetch(path: string, options: RequestInit): Promise<Response> {
  const requestVersion = version;
  const headers = new Headers(options.headers);
  try {
    if (isMutation(options.method) && path !== '/api/auth/login') headers.set('X-CSRF-Token', await getCsrfToken());
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) sessionExpired();
    throw error;
  }
  const send = () => fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: 'include' });
  let response = await send();
  if (response.status === 401 && canRefresh(path)) {
    await refreshSession(requestVersion);
    response = await send();
    if (response.status === 401) sessionExpired();
  }
  return checked(response);
}
