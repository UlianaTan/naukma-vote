import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { registerHooks } from 'node:module';
registerHooks({ resolve(specifier, context, nextResolve) {
  try { return nextResolve(specifier, context); }
  catch (error) {
    if (specifier.startsWith('.') && error.code === 'ERR_MODULE_NOT_FOUND') return nextResolve(specifier + '.ts', context);
    throw error;
  }
} });
const { voterApi, voterError, VoteUncertainError } = await import('../src/features/voter/services/voterApi.ts');
const { electionState } = await import('../src/features/voter/electionState.ts');
const { clearSession, ApiError } = await import('../src/lib/session.ts');
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; clearSession(); });
const id = '11111111-1111-4111-8111-111111111111';
const candidateId = '22222222-2222-4222-8222-222222222222';
const election = { id, title: 'Вибори', description: null, status: 'active',
  starts_at: '2026-10-21T08:00:00Z', ends_at: '2026-10-21T10:00:00Z',
  has_voted: false, results_published: false, closed_at: null,
  candidates: [{ id: candidateId, election_id: id, name: 'Кандидат', description: null }] };
const json = (status, data) => new Response(JSON.stringify(data), { status });
function server(handler) {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(options.credentials, 'include');
    const path = new URL(url).pathname;
    calls.push({ path, ...options });
    if (path === '/api/auth/csrf') return json(200, { csrf_token: 'csrf' });
    return handler(path, options);
  };
  return calls;
}

test('loads API election list and details without filtering out closed elections', async () => {
  const list = [election, { ...election, status: 'closed', results_published: true }];
  const calls = server(path => json(200, path.endsWith(id) ? election : list));
  assert.deepEqual(await voterApi.list(), list);
  assert.deepEqual(await voterApi.get(id), election);
  assert.deepEqual(calls.map(call => call.path), ['/api/v1/elections', `/api/v1/elections/${id}`]);
});

test('submits the backend payload with CSRF and accepts only server confirmation', async () => {
  const calls = server((_path, options) => {
    assert.deepEqual(JSON.parse(options.body), { candidate_id: candidateId });
    assert.equal(new Headers(options.headers).get('X-CSRF-Token'), 'csrf');
    return json(200, { status: 'success', message: 'Ваш голос успішно зараховано' });
  });
  assert.equal((await voterApi.vote(id, candidateId)).status, 'success');
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
});

test('lost vote response is reconciled by reading participation, never by repeating POST', async () => {
  const calls = server(path => {
    if (path.endsWith('/vote')) throw new TypeError('Connection lost after commit');
    return json(200, { ...election, has_voted: true });
  });
  assert.equal((await voterApi.vote(id, candidateId)).status, 'success');
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
  assert.equal(calls.at(-1).path, `/api/v1/elections/${id}`);
});

test('unconfirmed participation remains uncertain after a network or server failure', async () => {
  for (const committed of [false, null]) {
    const calls = server(path => path.endsWith('/vote')
      ? json(503, {}) : committed === false ? json(200, election) : json(503, {}));
    await assert.rejects(voterApi.vote(id, candidateId), VoteUncertainError);
    assert.equal(calls.filter(call => call.method === 'POST').length, 1);
    clearSession();
  }
});

test('duplicate vote is confirmed by server participation without a second POST', async () => {
  const calls = server(path => path.endsWith('/vote')
    ? json(409, { detail: 'Ви вже проголосували в цьому голосуванні' })
    : json(200, { ...election, has_voted: true }));
  assert.equal((await voterApi.vote(id, candidateId)).status, 'success');
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
});

test('denied and closed votes are not treated as success or retried', async () => {
  for (const status of [400, 403, 422]) {
    const calls = server(() => json(status, { detail: 'Denied' }));
    await assert.rejects(voterApi.vote(id, candidateId), { status });
    assert.equal(calls.filter(call => call.method === 'POST').length, 1);
    assert.equal(calls.filter(call => call.path.endsWith(id)).length, 0);
    clearSession();
  }
});

test('published results load independently of whitelist-restricted details', async () => {
  const results = { election_id: id, title: 'Підсумки', total_votes: 0, outcome: 'no_votes',
    winner_ids: [], closed_at: election.ends_at, results: [] };
  const calls = server(path => path.endsWith('/results') ? json(200, results) : json(403, { detail: 'No whitelist' }));
  assert.deepEqual(await voterApi.results(id), results);
  assert.deepEqual(calls.map(call => call.path), [`/api/v1/elections/${id}/results`]);
});

test('unpublished results retain server refusal and have a clear message', async () => {
  server(() => json(403, { detail: 'Результати ще не опубліковані організатором' }));
  await assert.rejects(voterApi.results(id), error => {
    assert.equal(voterError(error, 'Помилка'), 'Результати ще не опубліковані організатором');
    return true;
  });
  assert.equal(voterError(new ApiError(500, 'private traceback'), 'Помилка'), 'Сервіс тимчасово недоступний. Спробуйте пізніше.');
});

test('time boundaries and closed status govern voting availability', () => {
  assert.equal(electionState(election, Date.parse(election.starts_at) - 1), 'upcoming');
  assert.equal(electionState(election, Date.parse(election.starts_at)), 'active');
  assert.equal(electionState(election, Date.parse(election.ends_at)), 'closed');
  assert.equal(electionState({ ...election, status: 'closed' }, Date.parse(election.starts_at)), 'closed');
});

test('invalid election URLs fail before any request', async () => {
  const calls = server(() => json(200, {}));
  assert.throws(() => voterApi.get('../auth/me'), /Некоректне посилання/);
  assert.equal(calls.length, 0);
});
