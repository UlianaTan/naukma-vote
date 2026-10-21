import type { DraftCandidate } from '../../services/adminForm';
import type { AdminElection } from '../../services/adminApi';
import type { ChangeEvent } from 'react';
import { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { adminApi } from '../../services/adminApi';
import { adminError, localDateTime, parseVoterEmails, uncertainMutation, syncCandidates } from '../../services/adminForm';
import { ConfirmModal } from '../../components/ui/ConfirmModal';

export const CreateElectionPage = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEditMode = Boolean(id);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [electionStatus, setElectionStatus] = useState<AdminElection['status']>('draft');
  const [candidates, setCandidates] = useState<DraftCandidate[]>([{ name: '' }, { name: '' }]);
  const [votersFile, setVotersFile] = useState<File | null>(null);
  const [fileEmails, setFileEmails] = useState<string[]>([]);
  const [fileBusy, setFileBusy] = useState(false);
  const fileVersion = useRef(0);
  const [manualEmails, setManualEmails] = useState('');
  const [votersError, setVotersError] = useState('');
  const [votersFileError, setVotersFileError] = useState('');
  const [savedVoters, setSavedVoters] = useState<{ electionId: string; exists: boolean } | null>(null);
  const [votersLoadError, setVotersLoadError] = useState('');
  const [votersReload, setVotersReload] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [loadError, setLoadError] = useState('');
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [savedId, setSavedId] = useState<string | undefined>(id);
  const snapshot = useRef<AdminElection | null>(null);
  const [createUncertain, setCreateUncertain] = useState(false);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [loadedElectionId, setLoadedElectionId] = useState<string | null>(null);
  const isLoadingData = isEditMode && loadedElectionId !== id;
  const votersCount = fileEmails.length;
  const isDraftEdit = Boolean(savedId) && electionStatus === 'draft';

  useEffect(() => {
    let cancelled = false;
    if (id && (snapshot.current?.id !== id || reload > 0)) {
      adminApi.getElectionDetail(id).then(data => {
        if (cancelled) return;
        snapshot.current = data;
        setSavedId(data.id);
        setTitle(data.title);
        setDescription(data.description || '');
        setStartDate(localDateTime(data.starts_at));
        setEndDate(localDateTime(data.ends_at));
        setElectionStatus(data.status);
        setCandidates(data.candidates.length ? data.candidates.map(c => ({ id: c.id, name: c.name })) : [{ name: '' }, { name: '' }]);
        setLoadError('');
      }).catch(error => { if (!cancelled) setLoadError(adminError(error)); })
        .finally(() => { if (!cancelled) setLoadedElectionId(id); });
    }
    return () => { cancelled = true; };
  }, [id, reload]);

  useEffect(() => {
    let cancelled = false;
    // Recheck after saving/importing, including the navigate from create to edit.
    // Cleanup ignores reads started before the latest mutation.
    if (!savedId || busy) return;
    adminApi.getVoters(savedId).then(voters => {
      if (!cancelled) { setSavedVoters({ electionId: savedId, exists: voters.length > 0 }); setVotersLoadError(''); }
    }).catch(() => {
      if (!cancelled) { setSavedVoters(null); setVotersLoadError('Не вдалося перевірити збережених виборців. Повторіть перевірку.'); }
    });
    return () => { cancelled = true; };
  }, [savedId, busy, votersReload]);

  const handleCandidateChange = (index: number, value: string) => {
    setCandidates(previous => previous.map((row, i) => i === index ? { ...row, name: value } : row));
  };
  const handleAddCandidate = () => setCandidates(previous => [...previous, { name: '' }]);
  const handleRemoveCandidate = (index: number) => setCandidates(previous => previous.filter((_, i) => i !== index));

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const version = ++fileVersion.current;
    const file = event.target.files?.[0];
    setVotersFile(file || null);
    setFileEmails([]);
    setVotersFileError('');
    setVotersError('');
    if (!file) return;
    setFileBusy(true);
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error('Файл завеликий. Максимум 2 МБ.');
      const text = await file.text();
      if (version !== fileVersion.current) return;
      if (text.includes('\0')) throw new Error('Оберіть текстовий CSV або TXT у кодуванні UTF-8.');
      const emails = parseVoterEmails(text);
      if (!emails.length) throw new Error('Файл не містить адрес.');
      setFileEmails(emails);
      setMessage('');
    } catch (error) {
      if (version === fileVersion.current) {
        setVotersFile(null);
        setVotersFileError(error instanceof Error ? error.message : 'Не вдалося прочитати файл.');
      }
    } finally { if (version === fileVersion.current) setFileBusy(false); }
  };

  const validateForm = (activate: boolean) => {
    const next: Record<string, string> = {};
    if (title.trim().length < 3 || title.trim().length > 255) next.title = 'Назва має містити від 3 до 255 символів.';
    if (description.trim().length > 2000) next.description = 'Опис — не більше 2000 символів.';
    const start = new Date(startDate).getTime();
    const end = new Date(endDate).getTime();
    const unchangedStart = snapshot.current && localDateTime(snapshot.current.starts_at) === startDate;
    if (!Number.isFinite(start)) next.startDate = 'Вкажіть дату початку.';
    else if (!unchangedStart && start <= Date.now()) next.startDate = 'Оберіть час початку в майбутньому.';
    if (!Number.isFinite(end) || end <= Date.now() || end <= start) next.endDate = 'Завершення має бути в майбутньому й пізніше початку.';
    const names = candidates.map(c => c.name.trim()).filter(Boolean);
    if (activate && names.length < 2) next.candidates = 'Для запуску додайте щонайменше двох кандидатів.';
    if (names.some(name => name.length < 2 || name.length > 255)) next.candidates = 'Ім’я кандидата — від 2 до 255 символів.';
    if (new Set(names.map(name => name.toLocaleLowerCase())).size !== names.length) next.candidates = 'Імена кандидатів не мають повторюватися.';
    setErrors(next);
    return Object.keys(next).length === 0;
  };
  const handlePublishClick = () => { if (validateForm(true)) setIsPublishModalOpen(true); };

  const handleFinalSubmit = async (targetStatus: 'draft' | 'active') => {
    if (busyRef.current || fileBusy || createUncertain || electionStatus !== 'draft' || !validateForm(targetStatus === 'active')) return;
    busyRef.current = true;
    setBusy(true);
    setMessage('');
    setVotersError('');
    // A rejected file must be replaced or removed before a launch attempt.
    if (targetStatus === 'active' && votersFileError) {
      busyRef.current = false; setBusy(false); return;
    }
    let stage = 'Збереження даних';
    let electionId = savedId;
    try {
      const desired = candidates.map(row => ({ ...row, name: row.name.trim() })).filter(row => row.name);
      const names = desired.map(row => row.name);
      if (!electionId) {
        try {
          const created = await adminApi.createElection({ title: title.trim(), description: description.trim(),
            starts_at: new Date(startDate).toISOString(), ends_at: new Date(endDate).toISOString(),
            candidates: names.map(name => ({ name })) });
          electionId = created.id;
          setSavedId(created.id);
          snapshot.current = created;
          setCandidates(created.candidates.map(row => ({ id: row.id, name: row.name })));
          // Preserve the draft address even if later operations fail or the page is refreshed.
          setLoadedElectionId(created.id);
          navigate(`/admin/edit/${created.id}`, { replace: true });
        } catch (error) {
          if (uncertainMutation(error)) setCreateUncertain(true);
          throw error;
        }
      } else {
        const current = await adminApi.getElectionDetail(electionId);
        setElectionStatus(current.status);
        if (current.status !== 'draft') {
          setMessage('Статус змінився. Редагування вже недоступне. Перейдіть до моніторингу або результатів.');
          return;
        }
        const dates = {
          ...(localDateTime(current.starts_at) !== startDate ? { starts_at: new Date(startDate).toISOString() } : {}),
          ...(localDateTime(current.ends_at) !== endDate ? { ends_at: new Date(endDate).toISOString() } : {}),
        };
        await adminApi.updateElection(electionId, { title: title.trim(), description: description.trim(), ...dates });
        stage = 'Збереження кандидатів';
        snapshot.current = await syncCandidates(adminApi, electionId, desired);
        setCandidates(snapshot.current.candidates.map(row => ({ id: row.id, name: row.name })));
      }
      stage = 'Додавання виборців';
      const emails = parseVoterEmails([...fileEmails, manualEmails].join('\n'));
      if (emails.length) {
        // Backend rejects oversized batches; use small idempotent batches instead.
        let added = 0, existing = 0;
        const invalid: { value: string; reason: string }[] = [];
        for (let offset = 0; offset < emails.length; offset += 500) {
          const result = await adminApi.addVotersBatch(electionId, emails.slice(offset, offset + 500));
          added += result.added; existing += result.already_present; invalid.push(...result.invalid);
        }
        setFileEmails([]); setVotersFile(null);
        setManualEmails(invalid.map(item => item.value).join('\n'));
        if (fileInputRef.current) fileInputRef.current.value = '';
        const summary = `Додано виборців: ${added}. Уже у списку: ${existing}. Некоректних: ${invalid.length}.`;
        setMessage(summary + (invalid.length ? ' Виправте адреси у полі: ' + invalid.map(item => `${item.value}: ${item.reason}`).join('; ') : ' Чернетку збережено. Можна перевірити список виборців або запустити голосування.'));
        if (added > 0 || existing > 0) setSavedVoters({ electionId, exists: true });
        if (invalid.length) {
          setVotersError('Перевірте адреси виборців. Дозволені лише адреси @ukma.edu.ua. ' +
            invalid.map(item => `${item.value}: ${item.reason}`).join('; '));
          return;
        }
        if (targetStatus === 'draft') return;
      }
      if (targetStatus === 'active') {
        stage = 'Запуск голосування';
        let voters;
        try { voters = await adminApi.getVoters(electionId); }
        catch {
          setVotersError('Не вдалося перевірити список виборців. Повторіть спробу запуску.');
          return;
        }
        setSavedVoters({ electionId, exists: voters.length > 0 });
        if (!voters.length) {
          setVotersError('Для запуску додайте щонайменше одного виборця — завантажте файл або введіть email-адресу.');
          setMessage('Чернетку збережено.');
          return;
        }
        try { await adminApi.activateElection(electionId); }
        catch (error) {
          const current = await adminApi.getElectionDetail(electionId);
          setElectionStatus(current.status);
          if (current.status !== 'active') throw error;
        }
        navigate(`/admin/monitor/${electionId}`);
      } else setMessage('Чернетку збережено. Можна продовжити редагування або запустити голосування.');
    } catch (error) {
      if (stage === 'Додавання виборців') setVotersError(adminError(error));
      if (stage === 'Запуск голосування' && adminError(error).includes('Список виборців порожній')) {
        setSavedVoters(electionId ? { electionId, exists: false } : null);
        setVotersError('Для запуску додайте щонайменше одного виборця.');
      }
      setMessage(`${stage}: ${adminError(error)} ${electionId ? 'Чернетка вже існує. Повторне збереження продовжить роботу з нею.' : ''}`);
    } finally { busyRef.current = false; setBusy(false); }
  };

  const handleDeleteConfirm = async () => {
    const electionId = savedId;
    if (!electionId || busyRef.current) return;
    busyRef.current = true; setBusy(true);
    try { await adminApi.deleteElection(electionId); navigate('/admin'); }
    catch (error) { setMessage(adminError(error)); }
    finally { busyRef.current = false; setBusy(false); }
  };

  if (isLoadingData) return <p role="status">Завантаження чернетки…</p>;
  if (loadError) return <div role="alert">{loadError} <button onClick={() => setReload(value => value + 1)}>Повторити завантаження</button></div>;
  if (electionStatus !== 'draft') return <div className="space-y-4">
    <p>Голосування вже активоване або завершене. Редагування заборонено.</p>
    <button onClick={() => navigate(`/admin/${electionStatus === 'closed' ? 'results' : 'monitor'}/${savedId}`)}>Перейти до голосування</button>
  </div>;
  return (
    <div className="w-full flex justify-center pb-12">
      <div className="w-full max-w-4xl">
        
        <button 
          onClick={() => navigate('/admin')}
          className="text-slate-500 hover:text-slate-900 transition-colors mb-6 flex items-center gap-2 text-sm font-medium"
        >
          ← Назад до панелі організатора
        </button>

        <div className="bg-white rounded-2xl border border-slate-200 p-8 lg:p-10 shadow-sm">
          
          <div className="mb-8 border-b border-slate-100 pb-6">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">
              {!savedId
                ? 'Створення нового голосування' 
                : isDraftEdit 
                  ? 'Редагування чернетки' 
                  : 'Редагування голосування'}
            </h1>
            <p className="text-slate-500 text-sm">
              Вкажіть основні дані, додайте кандидатів і список виборців.
            </p>
          </div>

          {message && <p role="status" className="mb-4 whitespace-pre-wrap text-slate-800">{message}</p>}
          {createUncertain && <div role="alert" className="mb-4 text-red-700">Сервер міг створити чернетку, але відповідь не отримано. Повторне створення заблоковано. <button className="underline" onClick={() => navigate('/admin')}>Перевірити мої голосування</button></div>}
          {savedId && <button className="mb-4 underline" disabled={busy || fileBusy} onClick={() => navigate('/admin/voters')}>Перевірити список виборців</button>}
          <fieldset disabled={busy || fileBusy || createUncertain} className="space-y-8 disabled:opacity-60">
            
            <div>
              <label className="block text-sm font-bold text-slate-900 mb-2">Назва голосування</label>
              <input 
                type="text" 
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Введіть назву голосування"
                className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#0B1B3D]/20 focus:border-[#0B1B3D]"
              />
            </div>

            {errors.title && <p role="alert" className="text-red-700">{errors.title}</p>}
            {errors.description && <p role="alert" className="text-red-700">{errors.description}</p>}
            <p className="text-sm text-slate-500">Дати й час вказуйте за місцевим часом вашого пристрою.</p>
            <div>
              <label className="block text-sm font-bold text-slate-900 mb-2">Опис та правила</label>
              <textarea 
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Опишіть мету голосування та правила участі"
                className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#0B1B3D]/20 resize-none"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="start-date" className="block text-sm font-bold text-slate-900 mb-2">Дата початку</label>
                <input 
                  id="start-date"
                  type="datetime-local" 
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  aria-invalid={Boolean(errors.startDate)}
                  aria-describedby={errors.startDate ? 'start-date-error' : undefined}
                  className={`w-full border rounded-lg px-4 py-3 text-sm text-slate-700 focus:outline-none ${
                    errors.startDate ? 'border-red-500' : 'border-slate-300'
                  }`}
                />
                {errors.startDate && <p id="start-date-error" role="alert" className="text-xs text-red-600 mt-1.5 font-medium">{errors.startDate}</p>}
              </div>
              <div>
                <label htmlFor="end-date" className="block text-sm font-bold text-slate-900 mb-2">Дата завершення</label>
                <input 
                  id="end-date"
                  type="datetime-local" 
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  aria-invalid={Boolean(errors.endDate)}
                  aria-describedby={errors.endDate ? 'end-date-error' : undefined}
                  className={`w-full border rounded-lg px-4 py-3 text-sm text-slate-700 focus:outline-none ${
                    errors.endDate ? 'border-red-500' : 'border-slate-300'
                  }`}
                />
                {errors.endDate && <p id="end-date-error" role="alert" className="text-xs text-red-600 mt-1.5 font-medium">{errors.endDate}</p>}
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-900 mb-4">Кандидати</label>
              <div className="space-y-3">
                {candidates.map((candidate, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <input 
                      type="text" 
                      value={candidate.name}
                      onChange={(e) => handleCandidateChange(index, e.target.value)}
                      placeholder="Ім'я та прізвище кандидата"
                      className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none"
                    />
                    <button 
                      type="button"
                      onClick={() => handleRemoveCandidate(index)}
                      className="p-3 text-slate-400 hover:text-red-500 border border-slate-200 rounded-lg"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
              {errors.candidates && <p className="text-xs text-red-600 mt-2 font-medium">{errors.candidates}</p>}
              <button 
                type="button"
                onClick={handleAddCandidate}
                className="mt-4 px-4 py-2.5 border border-slate-200 text-slate-800 rounded-lg text-sm font-semibold hover:bg-slate-50"
              >
                + Додати кандидата
              </button>
            </div>

            <div>
              <h2 id="voters-heading" className="block text-sm font-bold text-slate-900 mb-2">Виборці</h2>
              <p id="voters-help" className="mb-4 text-sm text-slate-500">Для запуску потрібен щонайменше один виборець. Дозволені адреси @ukma.edu.ua. Чернетку можна зберегти без виборців.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className={`border border-dashed ${votersError || votersFileError ? 'border-red-500' : 'border-slate-300'} bg-slate-50/70 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-100`}
                >
                  <input type="file" accept=".csv,.txt,text/csv,text/plain" className="hidden" ref={fileInputRef} onChange={handleFileChange}
                    aria-label="Файл виборців CSV або TXT"
                    aria-invalid={Boolean(votersFileError || votersError)}
                    aria-describedby={votersFileError ? 'voters-file-error' : votersError ? 'voters-error' : 'voters-help'} />
                  {votersFile ? (
                    <p className="text-sm text-emerald-700 font-medium">Обрано: {votersFile.name} ({votersCount} виборців)</p>
                  ) : (
                    <p className="text-sm text-slate-700">CSV/TXT: одна колонка email. <span className="font-bold underline">оберіть файл</span></p>
                  )}
                </div>

                <div>
                  <label htmlFor="voter-emails" className="block text-sm font-bold text-slate-900 mb-2">Або додайте email-адреси</label>
                  <textarea
                    id="voter-emails"
                    rows={5}
                    value={manualEmails}
                    onChange={(e) => { setManualEmails(e.target.value); setVotersError(''); }}
                    placeholder="student@ukma.edu.ua&#10;Одна адреса в кожному рядку"
                    aria-invalid={Boolean(votersError)}
                    aria-describedby={votersError ? 'voters-help voters-error' : 'voters-help'}
                    className={`w-full border ${votersError ? 'border-red-500' : 'border-slate-300'} rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none resize-none`}
                  />
                </div>
              </div>
              {votersFileError && <p id="voters-file-error" role="alert" className="mt-2 text-xs font-medium text-red-600">{votersFileError} Оберіть інший файл.</p>}
              {votersError && <p id="voters-error" role="alert" className="mt-2 break-words text-xs font-medium text-red-600">{votersError}</p>}
              {votersLoadError && <p role="alert" className="mt-3 text-sm text-red-700">{votersLoadError} <button type="button" className="underline" onClick={() => setVotersReload(value => value + 1)}>Повторити перевірку виборців</button></p>}
              {savedVoters?.electionId === savedId && savedVoters?.exists && <p role="status" className="mt-4 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-950">Вказаних виборців уже збережено в базі. Порожні поля не означають, що список порожній. Переглянути або змінити список можна через «Перевірити список виборців».</p>}
            </div>
            
            <div className="flex items-center justify-between pt-6 mt-8 border-t border-slate-100">
              <div>
                {savedId && (
                  <button
                    type="button"
                    onClick={() => setIsDeleteModalOpen(true)}
                    className="text-red-600 hover:text-red-700 font-semibold text-sm"
                  >
                    {isDraftEdit ? 'Видалити чернетку' : 'Видалити голосування'}
                  </button>
                )}
              </div>

              <div className="flex gap-3">
                <button 
                  type="button"
                  onClick={() => handleFinalSubmit('draft')}
                  className="px-5 py-2.5 border border-slate-200 text-slate-800 rounded-lg font-semibold hover:bg-slate-50 text-sm"
                >
                  Зберегти чернетку
                </button>
                <button 
                  type="button"
                  onClick={handlePublishClick}
                  className="px-5 py-2.5 bg-[#0B1B3D] text-white rounded-lg font-semibold hover:bg-slate-800 text-sm shadow-sm"
                >
                  Запустити голосування
                </button>
              </div>
            </div>

          </fieldset>
        </div>
      </div>

      <ConfirmModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        onConfirm={() => handleFinalSubmit('active')}
        title="Запустити голосування?"
        description="Параметри та список виборців будуть заблоковані від редагування."
        confirmText="Розпочати"
        cancelText="Скасувати"
        type="primary"
        icon="lock"
      />

      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        onConfirm={handleDeleteConfirm}
        title={isDraftEdit ? "Видалити чернетку?" : "Видалити голосування?"}
        description="Голосування буде вилучено безповоротно."
        confirmText="Видалити"
        cancelText="Скасувати"
        type="danger"
        icon="trash"
      />
    </div>
  );
};
