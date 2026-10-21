import { useEffect, useState } from 'react';
import { adminApi } from '../../services/adminApi';
import type { AuditEntry } from '../../services/adminApi';
import { useNavigate, useParams } from 'react-router-dom';
import { Shield, Clock, FileText } from 'lucide-react';

export function AuditLogPage() {
  const navigate = useNavigate();
  const { id } = useParams();

  const [page, setPage] = useState<{ id?: string; logs: AuditEntry[]; error: boolean; hasMore: boolean }>({ logs: [], error: false, hasMore: false });
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    let cancelled = false;
    if (id) {
      adminApi.getAuditLog(id, offset).then(logs => {
        if (!cancelled) setPage({ id, logs, error: false, hasMore: logs.length === 100 });
      }).catch(() => {
        if (!cancelled) setPage({ id, logs: [], error: true, hasMore: false });
      });
    }
    return () => { cancelled = true; };
  }, [id, offset]);
  const auditLogs = page.logs;
  const labels: Record<string, string> = {
    'candidate.updated': 'Редагування кандидата',
    'election.created': 'Створення голосування',
    'election.activated': 'Запуск голосування',
    'election.closed': 'Закриття голосування',
    'results.published': 'Публікація результатів',
    'results.unpublished': 'Приховування результатів',
    'results.exported': 'Експорт результатів',
  };

  return (
    <div className="flex flex-col w-full">
      {/* Кнопка назад */}
      <button 
        onClick={() => navigate(`/admin/results/${id}`)}
        className="text-slate-500 hover:text-slate-900 transition-colors mb-6 flex items-center gap-2 text-sm font-medium w-fit"
      >
        ← Назад до результатів
      </button>

      {/* Заголовок */}
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-[32px] font-bold text-slate-900 mb-2 leading-tight">
            Журнал аудиту дій
          </h1>
          <p className="text-slate-500">
            Історія важливих подій та операцій організатора (з міркувань приватності вибір студентів не фіксується)
          </p>
        </div>
      </div>

      {/* Список подій */}
      <div className="bg-white border border-slate-200 rounded-[20px] overflow-hidden shadow-sm">
        <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex items-center gap-3">
          <Shield className="w-5 h-5 text-[#0B1B3D]" />
          <h2 className="font-bold text-slate-900 text-base">Системний журнал подій</h2>
        </div>

        <div className="divide-y divide-slate-100">
          {!id || page.error ? <p role="alert" className="p-6 text-red-700">Не вдалося завантажити журнал аудиту.</p>
            : page.id !== id ? <p className="p-6">Завантаження…</p>
            : auditLogs.length === 0 ? <p className="p-6">Подій поки немає.</p> : null}
          {auditLogs.map((log) => (
            <div key={log.id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50 transition-colors">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600 flex-shrink-0 mt-0.5">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base mb-1">
                    {labels[log.action] ?? log.action}
                  </h3>
                  <p className="text-slate-600 text-sm mb-2">
                    {JSON.stringify(log.details)}
                  </p>
                  <span className="text-xs text-slate-400 font-medium">
                    Адміністратор: {log.actor_user_id ?? 'Система'}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg w-fit">
                <Clock className="w-4 h-4 text-slate-400" />
                {new Date(log.created_at).toLocaleString('uk-UA')}
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-4 p-6">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Попередні</button>
          <button disabled={!page.hasMore} onClick={() => setOffset(offset + 100)}>Наступні</button>
        </div>
      </div>
    </div>
  );
}