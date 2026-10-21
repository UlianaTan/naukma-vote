import { useEffect, useState } from 'react';
import { adminApi } from '../../services/adminApi';
import type { AdminElection } from '../../services/adminApi';

export default function VotersManagementPage() {
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [voters, setVoters] = useState<{ id: string; email: string }[]>([]);
  const [emails, setEmails] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    adminApi.getElections().then(data => { if (!cancelled) setElections(data); })
      .catch(() => { if (!cancelled) setMessage('Не вдалося завантажити голосування.'); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    if (selectedId) {
      adminApi.getVoters(selectedId).then(data => {
        if (!cancelled) setVoters(data);
      }).catch(() => { if (!cancelled) setMessage('Не вдалося завантажити виборців.'); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [selectedId]);
  const selected = elections.find(e => e.id === selectedId);
  const editable = selected?.status === 'draft';
  async function addVoters() {
    setBusy(true);
    try {
      const result = await adminApi.addVotersBatch(selectedId, emails.split(/[\n,;]/).map(e => e.trim()).filter(Boolean));
      setVoters(await adminApi.getVoters(selectedId));
      setMessage(`Додано: ${result.added}. Уже у списку: ${result.already_present}. Некоректних: ${result.invalid.length}.`);
      setEmails('');
    } catch { setMessage('Не вдалося додати виборців.'); }
    finally { setBusy(false); }
  }
  async function removeVoter(id: string) {
    setBusy(true);
    try {
      await adminApi.removeVoter(selectedId, id);
      setVoters(await adminApi.getVoters(selectedId));
    } catch { setMessage('Не вдалося видалити виборця.'); }
    finally { setBusy(false); }
  }
  return <div className="space-y-6">
    <h1 className="text-2xl font-bold">Виборці голосування</h1>
    <label className="block">Оберіть голосування
      <select className="block border rounded p-3 w-full" value={selectedId} disabled={busy} onChange={e => {
        setSelectedId(e.target.value); setVoters([]); setLoading(Boolean(e.target.value)); setMessage('');
      }}>
        <option value="">Оберіть зі списку</option>
        {elections.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
      </select>
    </label>
    {message && <p role="status">{message}</p>}
    {selectedId && <>
      {loading ? <p>Завантаження…</p> : voters.length === 0 ? <p>Виборців у списку поки немає.</p> :
        <ul className="divide-y">{voters.map(v => <li key={v.id} className="flex justify-between p-3">
          {v.email}{editable && <button disabled={busy} onClick={() => removeVoter(v.id)}>Видалити</button>}
        </li>)}</ul>}
      {editable && <div className="space-y-3">
        <label className="block">Email виборців (кожен з нового рядка)
          <textarea className="block border rounded p-3 w-full" value={emails} onChange={e => setEmails(e.target.value)} />
        </label>
        <button className="rounded bg-slate-900 text-white p-3" disabled={busy || !emails.trim()} onClick={addVoters}>Додати виборців</button>
      </div>}
    </>}
  </div>;
}
