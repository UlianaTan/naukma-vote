import type { AdminElectionResults } from '../../services/adminApi';
import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Download, Users } from 'lucide-react';
import { adminApi } from '../../services/adminApi';
import { adminError } from '../../services/adminForm';
import { ConfirmModal } from '../../components/ui/ConfirmModal';

export function ElectionResultsPage() {
  const navigate = useNavigate();
  const { id } = useParams();

  const [resultsData, setResultsData] = useState<AdminElectionResults | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPublishModalOpen, setIsPublishModalOpen] = useState(false);
  const [isPublished, setIsPublished] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);

  // Завантажуємо результати з бекенду
  useEffect(() => {
    let cancelled = false;
    if (id) {
      adminApi.getAdminResults(id)
        .then((data) => {
          if (cancelled) return;
          setError('');
          setResultsData(data);
          setIsPublished(data.results_published || false);
        })
        .catch((err) => {
          if (!cancelled) setError(adminError(err));
        })
        .finally(() => {
          if (!cancelled) setIsLoading(false);
        });
    }
    return () => { cancelled = true; };
  }, [id, reload]);

  // Експорт у CSV через пряме завантаження з бекенду або генерацію
  const handleExportCSV = async () => {
    if (id) {
      try {
        const blob = await adminApi.exportResults(id);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `election-${id}-results.csv`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (err) {
        setError(adminError(err));
      }
    }
  };

  const handlePublishConfirm = async () => {
    if (!id || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      if (isPublished) await adminApi.unpublishResults(id);
      else await adminApi.publishResults(id);
    } catch (error) { setError(adminError(error)); }
    finally {
      // Re-read actual publication state even when a response was lost.
      setReload(value => value + 1); lock.current = false; setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-24">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0B1B3D]"></div>
      </div>
    );
  }

  if (!resultsData) {
    return <div role="alert" className="p-8 text-red-700">{error || "Не вдалося завантажити результати."} <button onClick={() => setReload(value => value + 1)}>Повторити</button></div>;
  }

  const totalVoters = resultsData?.eligible_count ?? 0;
  const votedCount = resultsData?.participants_count ?? 0;
  const turnoutPercentage = resultsData.turnout_percent;
  const candidates = resultsData?.results || [];

  return (
    <div className="flex flex-col w-full">
      {error && <p role="alert" className="mb-4 text-red-700">{error}</p>}
      <button className="mb-4 underline" disabled={busy} onClick={() => setReload(value => value + 1)}>Оновити результати</button>
      <button className="mb-4 underline" onClick={() => navigate(`/admin/audit/${id}`)}>Переглянути аудит</button>
      <div className="mb-6">
        <button 
          onClick={() => navigate('/admin')}
          className="text-slate-500 hover:text-slate-900 transition-colors mb-2 text-sm font-medium block"
        >
          ← Результати голосування
        </button>
        <div className="flex items-center gap-4">
          <h1 className="text-[32px] font-bold text-slate-900 leading-tight">
            {resultsData?.title || "Вибори"}
          </h1>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Завершено
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-8">
        <button
          onClick={() => setIsPublishModalOpen(true)}
          disabled={busy}
          className={`px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
            isPublished 
              ? 'bg-emerald-600 text-white cursor-default'
              : 'bg-[#0B1B3D] text-white hover:bg-slate-800'
          }`}
        >
          {busy ? 'Збереження…' : isPublished ? 'Приховати опубліковані результати' : 'Опублікувати результати студентству'}
        </button>

        <button
          onClick={handleExportCSV}
          className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 rounded-lg text-sm font-semibold hover:bg-slate-50 transition-colors"
        >
          <Download className="w-4 h-4" />
          Експорт в CSV
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-[20px] p-8 shadow-sm mb-6">
        <div className="flex items-center justify-between gap-8">
          <div className="min-w-[120px]">
            <div className="text-5xl font-bold text-slate-900 mb-1">
              {turnoutPercentage}%
            </div>
            <div className="text-xs text-slate-500">
              Загальна явка
            </div>
          </div>

          <div className="flex-1">
            <div className="text-sm font-semibold text-slate-900 mb-3">
              Загальна явка: {turnoutPercentage}% ({votedCount} з {totalVoters} виборців)
            </div>
            <div className="relative w-full bg-slate-100 rounded-full h-3 overflow-hidden">
              <div 
                className="absolute top-0 left-0 h-full bg-[#1D4ED8] rounded-full transition-all duration-1000"
                style={{ width: `${turnoutPercentage}%` }}
              />
            </div>
          </div>

          <div className="text-slate-400">
            <Users className="w-6 h-6" />
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-[20px] p-8 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-1">
          Результати кандидатів
        </h2>
        <p className="text-slate-500 text-sm mb-6">
          Частка голосів за кожного кандидата
        </p>

        <div className="space-y-6">
          {candidates.map((candidate) => (
            <div key={candidate.candidate_id}>
              <div className="flex justify-between items-center mb-2">
                <span className="font-bold text-slate-900 text-base">
                  {candidate.name}
                </span>
                <span className="font-bold text-slate-900 text-lg">
                  {candidate.percent || 0}% ({candidate.votes_count || 0} голосів)
                </span>
              </div>
              <div className="relative w-full bg-slate-100 rounded-full h-3.5 overflow-hidden">
                <div 
                  className="absolute top-0 left-0 h-full bg-[#334155] rounded-full transition-all duration-1000"
                  style={{ width: `${candidate.percent || 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <ConfirmModal
        isOpen={isPublishModalOpen}
        onClose={() => setIsPublishModalOpen(false)}
        onConfirm={handlePublishConfirm}
        title={isPublished ? "Приховати результати?" : "Опублікувати результати студентству?"}
        description={isPublished ? "Студенти більше не бачитимуть результати." : "Результати будуть доступні всім користувачам, які увійшли на сайт."}
        confirmText={isPublished ? "Приховати" : "Опублікувати"}
        cancelText="Скасувати"
        type="primary"
        icon="lock"
      />
    </div>
  );
}