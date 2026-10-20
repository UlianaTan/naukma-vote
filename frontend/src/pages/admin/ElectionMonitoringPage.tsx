import type { AdminElection, ElectionTurnout } from '../../services/adminApi';
import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Users, ShieldCheck } from 'lucide-react';
import { adminApi } from '../../services/adminApi';
import { adminError, adminStatus } from '../../services/adminForm';
import { ConfirmModal } from '../../components/ui/ConfirmModal'; 

export function ElectionMonitoringPage() {
  const navigate = useNavigate();
  const { id } = useParams();

  const [election, setElection] = useState<AdminElection | null>(null);
  const [turnout, setTurnout] = useState<ElectionTurnout | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCloseModalOpen, setIsCloseModalOpen] = useState(false);

  const [error, setError] = useState('');
  const [updated, setUpdated] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const closing = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      if (!id) return;
      try {
        const [details, counts] = await Promise.all([adminApi.getElectionDetail(id), adminApi.getTurnout(id)]);
        if (cancelled) return;
        setElection(details); setTurnout(counts); setError('');
        setUpdated(new Date().toLocaleTimeString('uk-UA'));
      } catch (error) { if (!cancelled) setError(adminError(error) + ' Показані дані можуть бути застарілими.'); }
      finally {
        if (!cancelled) { setIsLoading(false); timer = setTimeout(load, 15000); }
      }
    }
    void load();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [id, refresh]);

  const handleCloseElection = async () => {
    if (!id || closing.current) return;
    closing.current = true; setBusy(true);
    try { await adminApi.closeElection(id); navigate(`/admin/results/${id}`); }
    catch (error) { setError(adminError(error)); setRefresh(value => value + 1); }
    finally { closing.current = false; setBusy(false); }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-24">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#0B1B3D]"></div>
      </div>
    );
  }

  if (!election || !turnout) {
    return <div role="alert" className="p-8 text-red-700">{error || "Не вдалося завантажити дані."} <button onClick={() => setRefresh(value => value + 1)}>Повторити</button></div>;
  }

  const totalVoters = turnout?.eligible_count ?? 0;
  const votedCount = turnout?.participants_count ?? 0;
  const turnoutPercentage = turnout.turnout_percent;

  return (
    <div className="flex flex-col w-full">
      {error && <p role="alert" className="mb-4 text-red-700">{error}</p>}
      <div className="mb-4 flex gap-4"><button disabled={busy} onClick={() => setRefresh(value => value + 1)}>Оновити дані</button>
      {updated && <span>Оновлено о {updated}. Автоматичне оновлення кожні 15 секунд.</span>}</div>
      {election.status === 'closed' && <button className="mb-4 underline" onClick={() => navigate(`/admin/results/${id}`)}>Перейти до результатів</button>}
      {election.status === 'draft' && <button className="mb-4 underline" onClick={() => navigate(`/admin/edit/${id}`)}>Налаштувати й запустити чернетку</button>}
      <div className="mb-8">
        <button 
          onClick={() => navigate('/admin')}
          className="text-slate-500 hover:text-slate-900 transition-colors mb-2 text-sm font-medium block"
        >
          ← Моніторинг голосування
        </button>
        <div className="flex items-center gap-4">
          <h1 className="text-[32px] font-bold text-slate-900 leading-tight">
            {election?.title || "Вибори"}
          </h1>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E6F4EA] text-[#137333] text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#137333]"></span> {adminStatus(election)}
          </span>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-[20px] p-8 shadow-sm mb-6">
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-lg font-bold text-slate-900">Явка виборців</h2>
          <Users className="w-6 h-6 text-slate-400" />
        </div>

        <div className="mb-4">
          <div className="text-5xl font-bold text-slate-900 mb-2">
            {turnoutPercentage}%
          </div>
          <p className="text-slate-500 text-sm">
            Поточна явка виборців: {votedCount} з {totalVoters} проголосували ({turnoutPercentage}%)
          </p>
        </div>

        <div className="relative w-full bg-slate-100 rounded-full h-3 overflow-hidden mb-2">
          <div 
            className="absolute top-0 left-0 h-full bg-[#1D4ED8] transition-all duration-1000 ease-out rounded-full"
            style={{ width: `${turnoutPercentage}%` }}
          />
        </div>
        
        <div className="flex justify-between text-xs text-slate-500 font-medium">
          <span>0%</span>
          <span>100%</span>
        </div>
      </div>

      <div className="bg-[#F0F7FF] border border-[#BFDBFE] rounded-2xl p-5 flex items-center gap-3.5 text-[#1E3A8A] text-sm font-medium mb-6">
        <ShieldCheck className="w-5 h-5 text-[#1D4ED8] flex-shrink-0" />
        <span>Бюлетені зберігаються окремо від записів про участь. Після активації змінювати параметри голосування не можна.</span>
      </div>

      {election.status === 'active' && <div className="bg-white border border-red-200 rounded-[20px] p-6 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-slate-900 mb-1">
            Дострокове завершення
          </h3>
          <p className="text-slate-500 text-sm">
            Закрийте голосування раніше запланованої дати лише за потреби.
          </p>
        </div>
        
        <button 
          disabled={busy}
          onClick={() => setIsCloseModalOpen(true)}
          className="px-5 py-2.5 bg-[#DC2626] text-white rounded-lg text-sm font-semibold hover:bg-red-700 transition-colors flex-shrink-0 shadow-sm"
        >
          Достроково закрити голосування
        </button>
      </div>}

      <ConfirmModal 
        isOpen={isCloseModalOpen}
        onClose={() => setIsCloseModalOpen(false)}
        onConfirm={handleCloseElection}
        title="Достроково закрити голосування?"
        description="Ви впевнені, що хочете зупинити вибори прямо зараз? Усі студенти, які ще не проголосували, втратять цю можливість."
        confirmText="Так, закрити"
        cancelText="Скасувати"
        type="danger"
        icon="warning"
      />
    </div>
  );
}