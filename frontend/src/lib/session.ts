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
let epoch = 0;
let csrfGeneration = 0;

export function sessionVersion() { return version; }
export function sessionEpoch() { return epoch; }
export function assertSessionEpoch(expected: number) {
  if (expected !== epoch) throw new Error('Сесію змінено. Повторіть дію.');
}
export function invalidateCsrfToken(usedToken: string | null) {
  if (csrfToken === usedToken) {
    csrfToken = null;
    csrfPending = null;
    csrfGeneration++;
  }
}
export function clearSession() {
  csrfToken = null;
  csrfPending = null;
  refreshPending = null;
  csrfGeneration++;
  epoch++;
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
  return !['/api/auth/login', '/api/auth/register', '/api/auth/refresh', '/api/auth/logout', '/api/auth/csrf', '/api/auth/google/']
    .some(endpoint => path.startsWith(endpoint));
}
export function isCsrfMismatch(status: number, data: unknown) {
  return status === 403 && typeof data === 'object' && data !== null
    && 'detail' in data && data.detail === 'Missing or invalid CSRF token';
}
async function responseHasCsrfMismatch(response: Response) {
  if (response.status !== 403) return false;
  try { return isCsrfMismatch(response.status, await response.clone().json()); }
  catch { return false; }
}
async function checked(response: Response) {
  if (!response.ok) throw new ApiError(response.status, await response.text() || response.statusText);
  return response;
}

export async function getCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfPending) {
    const requestEpoch = epoch;
    const generation = csrfGeneration;
    const pending = (async () => {
      const response = await fetch(`${API_BASE_URL}/api/auth/csrf`, { credentials: 'include', cache: 'no-store' });
      assertSessionEpoch(requestEpoch);
      await checked(response);
      const data: { csrf_token: string } = await response.json();
      assertSessionEpoch(requestEpoch);
      if (generation !== csrfGeneration) throw new Error('CSRF-токен змінено. Повторіть дію.');
      if (typeof data.csrf_token !== 'string' || !data.csrf_token) throw new Error('Не вдалося отримати CSRF-токен.');
      csrfToken = data.csrf_token;
      return csrfToken;
    })();
    csrfPending = pending;
    void pending.finally(() => { if (csrfPending === pending) csrfPending = null; }).catch(() => {});
  }
  return csrfPending;
}

export async function refreshSession(requestVersion: number): Promise<void> {
  if (refreshPending) return refreshPending;
  if (requestVersion !== version) return;
  const requestEpoch = epoch;
  const pending = (async () => {
    try {
      let token = await getCsrfToken();
      const send = () => {
        assertSessionEpoch(requestEpoch);
        return fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': token },
        });
      };
      let response = await send();
      assertSessionEpoch(requestEpoch);
      if (await responseHasCsrfMismatch(response)) {
        assertSessionEpoch(requestEpoch);
        invalidateCsrfToken(token);
        token = await getCsrfToken();
        response = await send();
      }
      assertSessionEpoch(requestEpoch);
      await checked(response);
      assertSessionEpoch(requestEpoch);
      version++;
    } catch (error) {
      // CSRF/origin failures do not prove that the refresh session expired.
      if (requestEpoch === epoch && error instanceof ApiError && error.status === 401) sessionExpired();
      throw error;
    }
  })();
  refreshPending = pending;
  void pending.finally(() => { if (refreshPending === pending) refreshPending = null; }).catch(() => {});
  return pending;
}

export async function sessionFetch(path: string, options: RequestInit): Promise<Response> {
  const requestVersion = version;
  const requestEpoch = epoch;
  const headers = new Headers(options.headers);
  const mutation = isMutation(options.method) && !['/api/auth/login', '/api/auth/register'].includes(path);
  const logout = path === '/api/auth/logout';
  async function prepareCsrf() {
    try { headers.set('X-CSRF-Token', await getCsrfToken()); }
    catch (error) {
      assertSessionEpoch(requestEpoch);
      // Logout can use the backend's strictly checked frontend Origin when
      // refresh has expired; do not report success before the server responds.
      if (logout && error instanceof ApiError && error.status === 401) {
        headers.delete('X-CSRF-Token');
        return;
      }
      if (error instanceof ApiError && error.status === 401) sessionExpired();
      throw error;
    }
  }
  if (mutation) await prepareCsrf();
  let csrfRetried = false;
  const send = async () => {
    assertSessionEpoch(requestEpoch);
    let response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: 'include' });
    assertSessionEpoch(requestEpoch);
    if (mutation && !csrfRetried && await responseHasCsrfMismatch(response)) {
      assertSessionEpoch(requestEpoch);
      csrfRetried = true;
      invalidateCsrfToken(headers.get('X-CSRF-Token'));
      await prepareCsrf();
      assertSessionEpoch(requestEpoch);
      response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: 'include' });
      assertSessionEpoch(requestEpoch);
    }
    return response;
  };
  let response = await send();
  if (response.status === 401 && canRefresh(path)) {
    await refreshSession(requestVersion);
    response = await send();
    if (response.status === 401) sessionExpired();
  }
  return checked(response);
}
