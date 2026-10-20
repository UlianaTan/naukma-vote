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
