import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { registerHooks } from 'node:module';
import axios, { AxiosError } from 'axios';

registerHooks({
  resolve(specifier, context, nextResolve) {
    try { return nextResolve(specifier, context); }
    catch (error) {
      if (specifier.startsWith('.') && error.code === 'ERR_MODULE_NOT_FOUND') {
        return nextResolve(specifier + '.ts', context);
      }
      throw error;
    }
  },
});

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });
const { sessionFetch, clearSession, sessionVersion } = await import('../src/lib/session.ts');
const response = (status, data = {}) => new Response(JSON.stringify(data), { status });

function mockServer(handler) {
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    const path = new URL(url).pathname;
    const headers = new Headers(options.headers);
    calls.push({ path, options, headers });
    assert.equal(options.credentials, 'include');
    if (path === '/api/auth/csrf') return response(200, { csrf_token: 'test-csrf' });
    return handler(path, options, headers, calls);
  };
  return calls;
}

test('mutations bootstrap CSRF once and send the header', async () => {
  clearSession();
  const calls = mockServer((_path, _options, headers) => {
    assert.equal(headers.get('X-CSRF-Token'), 'test-csrf');
    return response(200);
  });
  await Promise.all([sessionFetch('/first', { method: 'POST' }), sessionFetch('/second', { method: 'DELETE' })]);
  assert.equal(calls.filter(c => c.path === '/api/auth/csrf').length, 1);
});

test('parallel 401s share one refresh and retry once', async () => {
  clearSession();
  let refreshed = false;
  const calls = mockServer(async (path, _options, headers) => {
    if (path === '/api/auth/refresh') {
      assert.equal(headers.get('X-CSRF-Token'), 'test-csrf');
      await new Promise(resolve => setTimeout(resolve, 10));
      refreshed = true;
      return response(200);
    }
    return response(refreshed ? 200 : 401);
  });
  await Promise.all([sessionFetch('/one', {}), sessionFetch('/two', {})]);
  assert.equal(calls.filter(c => c.path === '/api/auth/refresh').length, 1);
  assert.equal(calls.filter(c => c.path === '/one').length, 2);
  assert.equal(calls.filter(c => c.path === '/two').length, 2);
});

test('403 never triggers refresh; failed refresh cannot loop', async () => {
  clearSession();
  let calls = mockServer(() => response(403));
  await assert.rejects(sessionFetch('/forbidden', {}), { status: 403 });
  assert.equal(calls.length, 1);
  clearSession();
  calls = mockServer(() => response(401));
  await assert.rejects(sessionFetch('/expired', {}), { status: 401 });
  assert.equal(calls.filter(c => c.path === '/api/auth/refresh').length, 1);
  assert.equal(calls.filter(c => c.path === '/expired').length, 1);
});

test('persistent 401 after successful refresh retries only once', async () => {
  clearSession();
  const calls = mockServer(path => response(path === '/api/auth/refresh' ? 200 : 401));
  await assert.rejects(sessionFetch('/missing-user', {}), { status: 401 });
  assert.equal(calls.filter(c => c.path === '/missing-user').length, 2);
  assert.equal(calls.filter(c => c.path === '/api/auth/refresh').length, 1);
});

test('network failure during refresh does not expire the session', async () => {
  clearSession();
  const before = sessionVersion();
  mockServer(path => {
    if (path === '/api/auth/refresh') throw new TypeError('Offline');
    return response(401);
  });
  await assert.rejects(sessionFetch('/network', {}), /Offline/);
  assert.equal(sessionVersion(), before);
});

test('Axios and fetch share a refresh; Axios mutations and CSV retain their behavior', async () => {
  clearSession();
  let refreshed = false;
  const calls = mockServer(async path => {
    if (path === '/api/auth/refresh') {
      await new Promise(resolve => setTimeout(resolve, 10));
      refreshed = true;
      return response(200);
    }
    return response(refreshed ? 200 : 401);
  });
  const originalAdapter = axios.defaults.adapter;
  const requests = [];
  let denied = false;
  axios.defaults.adapter = async config => {
    requests.push(config);
    const result = { data: config.responseType === 'blob' ? new Blob(['csv']) : [],
      status: denied ? 403 : refreshed ? 200 : 401, statusText: '', headers: {}, config };
    if (result.status >= 400) throw new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, null, result);
    return result;
  };
  try {
    const { adminApi } = await import('../src/services/adminApi.ts');
    await Promise.all([sessionFetch('/voter', {}), adminApi.getElections()]);
    assert.equal(calls.filter(c => c.path === '/api/auth/refresh').length, 1);
    await adminApi.activateElection('id');
    assert.equal(requests.at(-1).headers.get('X-CSRF-Token'), 'test-csrf');
    assert.equal(requests.at(-1).withCredentials, true);
    const csv = await adminApi.exportResults('id');
    assert.ok(csv instanceof Blob);
    assert.equal(requests.at(-1).responseType, 'blob');
    denied = true;
    await assert.rejects(adminApi.activateElection('id'), error => error.response.status === 403);
    assert.equal(calls.filter(c => c.path === '/api/auth/refresh').length, 1);
  } finally { axios.defaults.adapter = originalAdapter; }
});

test('CSRF mismatch recovers once; ordinary forbidden responses are not retried', async () => {
  clearSession();
  let token = 'old';
  let csrfCalls = 0;
  let mutations = 0;
  globalThis.fetch = async (url, options = {}) => {
    if (new URL(url).pathname === '/api/auth/csrf') {
      csrfCalls++;
      return response(200, { csrf_token: token });
    }
    mutations++;
    return response(new Headers(options.headers).get('X-CSRF-Token') === token ? 200 : 403,
      { detail: 'Missing or invalid CSRF token' });
  };
  const { getCsrfToken } = await import('../src/lib/session.ts');
  await getCsrfToken();
  token = 'new'; // Another tab completed Google login and replaced cookies.
  await sessionFetch('/mutation', { method: 'POST' });
  assert.equal(csrfCalls, 2);
  assert.equal(mutations, 2);
  globalThis.fetch = async () => { mutations++; return response(403, { detail: 'Not the election owner' }); };
  await assert.rejects(sessionFetch('/mutation', { method: 'POST' }), { status: 403 });
  assert.equal(mutations, 3);
});

test('refresh repairs stale CSRF without expiring a valid session', async () => {
  clearSession();
  const { getCsrfToken } = await import('../src/lib/session.ts');
  let token = 'old'; let csrfCalls = 0; let refreshCalls = 0; let refreshed = false;
  globalThis.fetch = async (url, options = {}) => {
    const path = new URL(url).pathname;
    if (path === '/api/auth/csrf') { csrfCalls++; return response(200, { csrf_token: token }); }
    if (path === '/api/auth/refresh') {
      refreshCalls++;
      if (new Headers(options.headers).get('X-CSRF-Token') !== token)
        return response(403, { detail: 'Missing or invalid CSRF token' });
      refreshed = true; return response(200);
    }
    return response(refreshed ? 200 : 401);
  };
  await getCsrfToken(); token = 'new';
  const before = sessionVersion();
  await sessionFetch('/protected', {});
  assert.equal(csrfCalls, 2); assert.equal(refreshCalls, 2);
  assert.equal(sessionVersion(), before + 1);
});

test('persistent CSRF mismatch is bounded and does not expire the session', async () => {
  clearSession(); let mutations = 0;
  globalThis.fetch = async url => {
    if (new URL(url).pathname === '/api/auth/csrf') return response(200, { csrf_token: 'token' });
    mutations++; return response(403, { detail: 'Missing or invalid CSRF token' });
  };
  const before = sessionVersion();
  await assert.rejects(sessionFetch('/mutation', { method: 'POST' }), { status: 403 });
  assert.equal(mutations, 2); assert.equal(sessionVersion(), before);
});

test('late CSRF from a cleared session cannot replace the new token', async () => {
  clearSession();
  const { getCsrfToken } = await import('../src/lib/session.ts');
  let release;
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    if (calls === 1) return new Promise(resolve => { release = () => resolve(response(200, { csrf_token: 'old' })); });
    return response(200, { csrf_token: 'new' });
  };
  const old = getCsrfToken();
  const rejected = assert.rejects(old, /Сесію змінено/);
  clearSession();
  assert.equal(await getCsrfToken(), 'new');
  release(); await rejected;
  assert.equal(await getCsrfToken(), 'new');
  assert.equal(calls, 2);
});

test('logout reaches backend after CSRF bootstrap reports expired refresh', async () => {
  clearSession(); const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    const path = new URL(url).pathname; calls.push(path);
    if (path === '/api/auth/csrf') return response(401);
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'include');
    assert.equal(path, '/api/auth/logout');
    return response(200, { status: 'ok' });
  };
  await sessionFetch('/api/auth/logout', { method: 'POST' });
  assert.deepEqual(calls, ['/api/auth/csrf', '/api/auth/logout']);
});

test('late 401 from before logout cannot trigger refresh or replay a mutation', async () => {
  clearSession(); let release; let calls = 0;
  globalThis.fetch = async () => { calls++; return new Promise(resolve => { release = () => resolve(response(401)); }); };
  const pending = sessionFetch('/protected', {});
  const rejected = assert.rejects(pending, /Сесію змінено/);
  clearSession(); release(); await rejected;
  assert.equal(calls, 1);
});

test('Axios also repairs only a CSRF mismatch and limits retries', async () => {
  clearSession();
  let token = 'old'; let calls = 0;
  globalThis.fetch = async () => response(200, { csrf_token: token });
  const { getCsrfToken } = await import('../src/lib/session.ts');
  await getCsrfToken(); token = 'new';
  const originalAdapter = axios.defaults.adapter;
  let persistent = false;
  // Use a fresh client so its Axios instance captures this adapter.
  axios.defaults.adapter = async config => {
    calls++;
    const status = persistent || config.headers.get('X-CSRF-Token') !== token ? 403 : 200;
    const result = { status, data: { detail: 'Missing or invalid CSRF token' }, statusText: '', headers: {}, config };
    if (status === 403) throw new AxiosError('Forbidden', 'ERR_BAD_REQUEST', config, null, result);
    return result;
  };
  try {
    const { adminApi } = await import('../src/services/adminApi.ts?csrf-test');
    await adminApi.activateElection('id');
    assert.equal(calls, 2);
    persistent = true;
    await assert.rejects(adminApi.activateElection('id'), e => e.response?.status === 403);
    assert.equal(calls, 4);
  } finally { axios.defaults.adapter = originalAdapter; }
});


test('session lookup distinguishes connection failures from anonymous sessions and can retry', async () => {
  const { loadSession } = await import('../src/lib/loadSession.ts');
  clearSession();
  globalThis.fetch = async () => { throw new TypeError('Offline'); };
  assert.deepEqual(await loadSession(), { kind: 'unavailable' });
  globalThis.fetch = async () => response(503);
  assert.deepEqual(await loadSession(), { kind: 'unavailable' });
  globalThis.fetch = async url => new URL(url).pathname === '/api/auth/me'
    ? response(200, { id: 'user-id', email: 'user@ukma.edu.ua' }) : response(401);
  assert.deepEqual(await loadSession(), { kind: 'authenticated', user: { id: 'user-id', email: 'user@ukma.edu.ua' } });
  clearSession();
  globalThis.fetch = async () => response(401);
  assert.deepEqual(await loadSession(), { kind: 'anonymous' });
});

test('failed logout keeps the local session; successful logout clears it', async () => {
  const { api } = await import('../src/lib/api.ts');
  clearSession(); let fail = true;
  globalThis.fetch = async url => new URL(url).pathname === '/api/auth/csrf'
    ? response(200, { csrf_token: 'token' }) : response(fail ? 503 : 200, { status: 'ok' });
  const before = sessionVersion();
  await assert.rejects(api.post('/api/auth/logout'), { status: 503 });
  assert.equal(sessionVersion(), before);
  fail = false;
  await api.post('/api/auth/logout');
  assert.equal(sessionVersion(), before + 1);
});

test('login and registration do not require a prior session or trigger refresh', async () => {
  clearSession();
  const calls = mockServer(() => response(200));
  await sessionFetch('/api/auth/login', { method: 'POST', body: '{}' });
  await sessionFetch('/api/auth/register', { method: 'POST', body: '{}' });
  assert.deepEqual(calls.map(call => call.path), ['/api/auth/login', '/api/auth/register']);
});


test('invalid password does not refresh or reuse an old logged-in session', async () => {
  clearSession();
  const calls = mockServer(() => response(401));
  await assert.rejects(sessionFetch('/api/auth/login', { method: 'POST', body: '{}' }), { status: 401 });
  await assert.rejects(sessionFetch('/api/auth/register', { method: 'POST', body: '{}' }), { status: 401 });
  assert.deepEqual(calls.map(call => call.path), ['/api/auth/login', '/api/auth/register']);
});

test('first password setup requires the session CSRF token and keeps cookies', async () => {
  clearSession();
  const calls = mockServer((path, options, headers) => {
    assert.equal(path, '/api/auth/password');
    assert.equal(options.method, 'POST');
    assert.equal(headers.get('X-CSRF-Token'), 'test-csrf');
    return response(200, { status: 'ok' });
  });
  await sessionFetch('/api/auth/password', { method: 'POST', body: '{}' });
  assert.deepEqual(calls.map(call => call.path), ['/api/auth/csrf', '/api/auth/password']);
});
