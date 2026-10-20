import assert from 'node:assert/strict';
import { test } from 'node:test';
import { localDateTime, parseVoterEmails, adminStatus, syncCandidates } from '../src/services/adminForm.ts';

test('one-column CSV/TXT preserves invalid values for server reporting and deduplicates normalized emails', () => {
  assert.deepEqual(parseVoterEmails('\uFEFFemail\r\n"Alice@ukma.edu.ua";alice@ukma.edu.ua\nbad-address\nbob@ukma.edu.ua'),
    ['alice@ukma.edu.ua', 'bad-address', 'bob@ukma.edu.ua']);
});

test('local date fields preserve summer and winter instants in Europe/Kyiv', () => {
  const original = process.env.TZ;
  process.env.TZ = 'Europe/Kyiv';
  try {
    for (const iso of ['2027-01-10T13:00:00.000Z', '2027-07-10T12:00:00.000Z']) {
      assert.equal(localDateTime(iso).slice(-5), '15:00');
      assert.equal(new Date(localDateTime(iso)).toISOString(), iso);
      assert.equal(localDateTime(iso.slice(0, -1)), localDateTime(iso));
    }
  } finally { if (original === undefined) delete process.env.TZ; else process.env.TZ = original; }
});

test('monitor distinguishes scheduled, running, expired, closed and draft elections', () => {
  const election = { status: 'active', starts_at: '2027-01-01T10:00:00Z', ends_at: '2027-01-01T11:00:00Z' };
  assert.equal(adminStatus(election, Date.parse('2027-01-01T09:00:00Z')), 'Очікує початку');
  assert.equal(adminStatus(election, Date.parse(election.starts_at)), 'Триває');
  assert.match(adminStatus(election, Date.parse(election.ends_at)), /очікується закриття/);
  assert.equal(adminStatus({ ...election, status: 'closed' }), 'Завершено');
  assert.equal(adminStatus({ ...election, status: 'draft' }), 'Чернетка');
});

test('candidate retry reconciles a lost response without duplicates and retains unchanged IDs', async () => {
  const election = { status: 'draft', candidates: [{ id: 'keep', name: 'Анна' }, { id: 'remove', name: 'Богдан' }] };
  let fail = true;
  const api = {
    getElectionDetail: async () => structuredClone(election),
    removeCandidate: async (_id, id) => { election.candidates = election.candidates.filter(c => c.id !== id); },
    addCandidate: async (_id, { name }) => {
      election.candidates.push({ id: name, name });
      if (fail) { fail = false; throw new TypeError('Lost response after commit'); }
    },
  };
  await assert.rejects(syncCandidates(api, 'draft', ['Анна', 'Олена', 'Петро']));
  await syncCandidates(api, 'draft', ['Анна', 'Олена', 'Петро']);
  assert.deepEqual(election.candidates, [{ id: 'keep', name: 'Анна' }, { id: 'Олена', name: 'Олена' }, { id: 'Петро', name: 'Петро' }]);
});

test('candidate sync refuses a status change before any mutations', async () => {
  await assert.rejects(syncCandidates({ getElectionDetail: async () => ({ status: 'active' }),
    removeCandidate: () => assert.fail(), addCandidate: () => assert.fail() }, 'id', ['Анна']), /no longer a draft/);
});
