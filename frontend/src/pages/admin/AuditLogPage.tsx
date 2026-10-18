import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Shield, Clock, FileText } from 'lucide-react';

export function AuditLogPage() {
  const navigate = useNavigate();
  const { id } = useParams();

  // Мокові записи журналу дій (у майбутньому підтягуватимемо з бекенду)
  const auditLogs = [
    {
      id: 1,
      action: "Створення чернетки голосування",
      timestamp: "20.10.2026, 10:15",
      admin: "admin@ukma.edu.ua",
      details: "Створено голосування та додано 2 кандидатів."
    },
    {
      id: 2,
      action: "Завантаження списку виборців",
      timestamp: "20.10.2026, 10:20",
      admin: "admin@ukma.edu.ua",
      details: "Імпортовано файл ukma_voters.csv (50 виборців)."
    },
    {
      id: 3,
      action: "Публікація та запуск голосування",
      timestamp: "20.10.2026, 09:00",
      admin: "admin@ukma.edu.ua",
      details: "Параметри заблоковано від редагування, статус змінено на 'active'."
    }
  ];

  return (
    <div className="flex flex-col w-full">
      {/* Кнопка назад */}
      <button 
        onClick={() => navigate(`/admin/results/${id || 1}`)}
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
          {auditLogs.map((log) => (
            <div key={log.id} className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50 transition-colors">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600 flex-shrink-0 mt-0.5">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 text-base mb-1">
                    {log.action}
                  </h3>
                  <p className="text-slate-600 text-sm mb-2">
                    {log.details}
                  </p>
                  <span className="text-xs text-slate-400 font-medium">
                    Адміністратор: {log.admin}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg w-fit">
                <Clock className="w-4 h-4 text-slate-400" />
                {log.timestamp}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}