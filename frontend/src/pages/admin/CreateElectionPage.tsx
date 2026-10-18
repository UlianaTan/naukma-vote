import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { adminApi } from '../../services/adminApi';
import { ConfirmModal } from '../../components/ui/ConfirmModal';

export const CreateElectionPage = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEditMode = Boolean(id);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Стан форм
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [electionStatus, setElectionStatus] = useState<'draft' | 'active'>('draft');

  // Кандидати (масив об'єктів або рядків)
  const [candidates, setCandidates] = useState<string[]>(['', '']);

  // Виборці
  const [votersFile, setVotersFile] = useState<File | null>(null);
  const [votersCount, setVotersCount] = useState<number>(0);
  const [manualEmails, setManualEmails] = useState('');

  // Помилки та модалки
  const [errors, setErrors] = useState<{ title?: string; endDate?: string; candidates?: string }>({});
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(false);

  // Підвантаження даних у режимі редагування з бекенду
  useEffect(() => {
    if (isEditMode && id) {
      setIsLoadingData(true);
      adminApi.getElectionDetail(id)
        .then((data) => {
          setTitle(data.title || '');
          setDescription(data.description || '');
          setStartDate(data.starts_at ? data.starts_at.slice(0, 16) : '');
          setEndDate(data.ends_at ? data.ends_at.slice(0, 16) : '');
          setElectionStatus(data.status || 'draft');
          if (data.candidates && data.candidates.length > 0) {
            setCandidates(data.candidates.map((c: any) => c.name));
          }
        })
        .catch((err) => {
          console.error("Не вдалося завантажити деталі голосування:", err);
        })
        .finally(() => {
          setIsLoadingData(false);
        });
    }
  }, [id, isEditMode]);

  const handleCandidateChange = (index: number, value: string) => {
    const newCandidates = [...candidates];
    newCandidates[index] = value;
    setCandidates(newCandidates);

    const validCount = newCandidates.filter(c => c.trim() !== '').length;
    if (validCount >= 2 && errors.candidates) {
      setErrors(prev => ({ ...prev, candidates: undefined }));
    }
  };

  const handleAddCandidate = () => {
    setCandidates([...candidates, '']);
  };

  const handleRemoveCandidate = (index: number) => {
    if (candidates.length > 1) {
      setCandidates(candidates.filter((_, i) => i !== index));
    }
  };

  const processFile = (file: File) => {
    setVotersFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      if (text) {
        const lines = text.split(/\r\n|\n/).filter(line => line.trim().includes('@'));
        setVotersCount(lines.length);
      }
    };
    reader.readAsText(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const validateForm = () => {
    const newErrors: { title?: string; endDate?: string; candidates?: string } = {};

    if (!title.trim()) {
      newErrors.title = "Вкажіть назву голосування";
    }
    if (!endDate) {
      newErrors.endDate = 'Вкажіть дату закінчення';
    }

    const validCandidates = candidates.filter(c => c.trim() !== '');
    if (validCandidates.length < 2) {
      newErrors.candidates = 'Додайте щонайменше 2 кандидатів';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handlePublishClick = () => {
    if (validateForm()) {
      if (isEditMode && electionStatus === 'active') {
        handleFinalSubmit('active');
      } else {
        setIsPublishModalOpen(true);
      }
    }
  };

  // ФІНАЛЬНА ВІДПРАВКА НА БЕКЕНД
  const handleFinalSubmit = async (targetStatus: 'draft' | 'active') => {
    try {
      const payload = {
        title,
        description,
        starts_at: startDate ? new Date(startDate).toISOString() : new Date().toISOString(),
        ends_at: endDate ? new Date(endDate).toISOString() : new Date(Date.now() + 86400000).toISOString(),
        candidates: candidates
          .filter(c => c.trim() !== '')
          .map(name => ({ name }))
      };

      let electionId = id;

      if (isEditMode && id) {
        await adminApi.updateElection(id, payload);
      } else {
        const created = await adminApi.createElection(payload);
        electionId = created.id;
      }

      // Якщо є введені вручну email або файл виборців — додаємо їх до білого списку (whitelist)
      if (electionId) {
        const emailsList: string[] = [];
        
        if (manualEmails.trim()) {
          const parsedManual = manualEmails.split(/\r\n|\n/).map(e => e.trim()).filter(Boolean);
          emailsList.push(...parsedManual);
        }

        if (emailsList.length > 0) {
          await adminApi.addVotersBatch(electionId, emailsList);
        }

        // Якщо потрібно активувати голосування
        if (targetStatus === 'active') {
          await adminApi.activateElection(electionId);
        }
      }

      navigate('/admin');
    } catch (err) {
      console.error("Помилка збереження голосування на сервері:", err);
      alert("Не вдалося зберегти голосування. Перевірте з'єднання з бекендом.");
    }
  };

  const handleDeleteConfirm = async () => {
    if (id) {
      try {
        await adminApi.deleteElection(id);
        navigate('/admin');
      } catch (err) {
        console.error("Помилка видалення:", err);
        alert("Не вдалося видалити чернетку.");
      }
    }
  };

  const isDraftEdit = isEditMode && electionStatus === 'draft';

  if (isLoadingData) {
    return (
      <div className="flex justify-center items-center py-24">
        <div className="animate-spin rounded-full h-12 b-2 border-b-2 border-[#0B1B3D]"></div>
      </div>
    );
  }

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
              {!isEditMode 
                ? 'Створення нового голосування' 
                : isDraftEdit 
                  ? 'Редагування чернетки' 
                  : 'Редагування голосування'}
            </h1>
            <p className="text-slate-500 text-sm">
              Вкажіть основні дані, додайте кандидатів і список виборців.
            </p>
          </div>

          <div className="space-y-8">
            
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
                <label className="block text-sm font-bold text-slate-900 mb-2">Дата початку</label>
                <input 
                  type="datetime-local" 
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-700 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-bold text-slate-900 mb-2">Дата завершення</label>
                <input 
                  type="datetime-local" 
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className={`w-full border rounded-lg px-4 py-3 text-sm text-slate-700 focus:outline-none ${
                    errors.endDate ? 'border-red-500' : 'border-slate-300'
                  }`}
                />
                {errors.endDate && <p className="text-xs text-red-600 mt-1.5 font-medium">{errors.endDate}</p>}
              </div>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-900 mb-4">Кандидати</label>
              <div className="space-y-3">
                {candidates.map((candidate, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <input 
                      type="text" 
                      value={candidate}
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
              <label className="block text-sm font-bold text-slate-900 mb-4">Виборці</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className="border border-dashed border-slate-300 bg-slate-50/70 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-100"
                >
                  <input type="file" accept=".csv" className="hidden" ref={fileInputRef} onChange={handleFileChange} />
                  {votersFile ? (
                    <p className="text-sm text-emerald-700 font-medium">Завантажено: {votersFile.name} ({votersCount} виборців)</p>
                  ) : (
                    <p className="text-sm text-slate-700">Перетягніть CSV-файл або <span className="font-bold underline">оберіть файл</span></p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-bold text-slate-900 mb-2">Або додайте email-адреси</label>
                  <textarea 
                    rows={5}
                    value={manualEmails}
                    onChange={(e) => setManualEmails(e.target.value)}
                    placeholder="student@ukma.edu.ua&#10;Одна адреса в кожному рядку"
                    className="w-full border border-slate-300 rounded-lg px-4 py-3 text-sm text-slate-900 focus:outline-none resize-none"
                  />
                </div>
              </div>
            </div>
            
            <div className="flex items-center justify-between pt-6 mt-8 border-t border-slate-100">
              <div>
                {isEditMode && (
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
                  Опублікувати та розпочати
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        onConfirm={() => handleFinalSubmit('active')}
        title="Опублікувати голосування?"
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