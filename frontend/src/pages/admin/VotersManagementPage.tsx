import { useEffect, useState, useRef } from 'react';
import { adminApi } from '../../services/adminApi';
import { adminError, parseVoterEmails } from '../../services/adminForm';
import type { AdminElection } from '../../services/adminApi';

export default function VotersManagementPage() {
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [voters, setVoters] = useState<{ id: string; email: string }[]>([]);
  const [emails, setEmails] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let cancelled = false;
    adminApi.getElections().then(data => { if (!cancelled) setElections(data); })
      .catch(error => { if (!cancelled) setMessage(adminError(error)); });
    return () => { cancelled = true; };
  }, [reload]);
  useEffect(() => {
    let cancelled = false;
    if (selectedId) {
      adminApi.getVoters(selectedId).then(data => {
        if (!cancelled) setVoters(data);
      }).catch(error => { if (!cancelled) setMessage(adminError(error)); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [selectedId, reload]);
  const selected = elections.find(e => e.id === selectedId);
  const editable = selected?.status === 'draft';
  async function addVoters() {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try {
      const result = await adminApi.addVotersBatch(selectedId, parseVoterEmails(emails));
      setVoters(await adminApi.getVoters(selectedId));
      setMessage(`Додано: ${result.added}. Уже у списку: ${result.already_present}. Некоректних: ${result.invalid.length}. ` + result.invalid.map(item => `${item.value}: ${item.reason}`).join('; '));
      setEmails(result.invalid.map(item => item.value).join('\n'));
    } catch (error) { setMessage(adminError(error) + ' Повторне додавання не дублює адреси.'); }
    finally { lock.current = false; setBusy(false); }
  }
  async function removeVoter(id: string) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try {
      await adminApi.removeVoter(selectedId, id);
      setVoters(await adminApi.getVoters(selectedId));
    } catch (error) { setMessage(adminError(error)); }
    finally { lock.current = false; setBusy(false); }
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
    <button disabled={busy} onClick={() => { setLoading(Boolean(selectedId)); setReload(value => value + 1); }}>Оновити списки</button>
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
