import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { adminApi } from "../../services/adminApi";
import { Folder } from "lucide-react";
import toast from 'react-hot-toast';

import type { AdminElection } from "../../services/adminApi";

export function AdminElectionsPage() {
  const navigate = useNavigate();
  
  const [elections, setElections] = useState<AdminElection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("Усі");

  const tabs = ["Усі", "Чернетки", "Активні", "Завершені"];

  // Завантаження голосувань з реального бекенду при відкритті сторінки
  useEffect(() => {
    const fetchElections = async () => {
      try {
        setIsLoading(true);
        const data = await adminApi.getElections();
        setElections(data);
        setError(null);
      } catch (err) {
        console.error("Помилка завантаження голосувань:", err);
        const errorMessage = "Не вдалося завантажити список голосувань від сервера.";
        setError(errorMessage);
        toast.error(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    fetchElections();
  }, []);

  // Фільтруємо голосування залежно від обраної вкладки
  const filteredElections = (elections || []).filter((election) => {
    if (activeTab === "Усі") return true;
    if (activeTab === "Чернетки") return election.status === "draft";
    if (activeTab === "Активні") return election.status === "active";
    if (activeTab === "Завершені") return election.status === "closed";
    return true;
  });

  // Візуальні беджі для статусів
  const renderStatus = (status: string) => {
    switch (status) {
      case "active":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E6F4EA] text-[#137333] text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#137333]"></span> Активне
          </span>
        );
      case "closed":
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Завершено
          </span>
        );
      case "draft":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-sm font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Чернетка
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col w-full">
      {/* Заголовок сторінки */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
          <h1 className="text-[28px] md:text-[32px] font-bold text-slate-900 mb-1 leading-tight">Мої голосування</h1>
          <p className="text-slate-500 text-sm md:text-base">Панель управління організатора</p>
        </div>
        
        {/* Кнопка "Створити" */}
        {!isLoading && !error && elections?.length > 0 && (
          <button
            onClick={() => navigate("/admin/create")}
            className="w-full md:w-auto bg-[#0B1B3D] text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-800 transition-colors text-center"
          >
            + Створити голосування
          </button>
        )}
      </div>

      {/* Вкладки фільтрації */}
      <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2 w-full">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors whitespace-nowrap ${
              activeTab === tab
                ? "bg-[#0B1B3D] text-white"
                : "text-slate-600 hover:bg-slate-100 bg-white border border-slate-200 md:border-0"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Стан завантаження */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Стан помилки */}
      {!isLoading && error && (
        <div className="bg-red-50 text-red-600 rounded-xl p-4 text-sm border border-red-100">
          {error}
        </div>
      )}

      {/* Порожній стан (Empty State) */}
      {!isLoading && !error && filteredElections.length === 0 && (() => {
        let emptyState = {
          title: 'У вас поки немає створених голосувань',
          desc: 'Створіть перше голосування, додайте кандидатів і запросіть виборців.',
          showButton: true
        };

        if (activeTab === 'Чернетки') {
          emptyState = {
            title: 'У вас немає збережених чернеток',
            desc: 'Усі ваші створені голосування вже активні або завершені.',
            showButton: true
          };
        } else if (activeTab === 'Активні') {
          emptyState = {
            title: 'Зараз немає активних голосувань',
            desc: 'Опублікуйте чернетку, щоб виборці могли віддати свій голос.',
            showButton: false
          };
        } else if (activeTab === 'Завершені') {
          emptyState = {
            title: 'У вас ще немає завершених голосувань',
            desc: 'Тут зʼявляться голосування, термін яких минув.',
            showButton: false
          };
        }

        return (
          <div className="bg-white border border-slate-200 rounded-[20px] py-24 flex flex-col items-center justify-center text-center">
            <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-6">
              <Folder className="w-8 h-8 text-slate-300" strokeWidth={1.5} />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-3">
              {emptyState.title}
            </h2>
            <p className="text-slate-500 mb-8">
              {emptyState.desc}
            </p>
            {emptyState.showButton && (
              <button
                onClick={() => navigate("/admin/create")}
                className="bg-[#0B1B3D] text-white px-6 py-3 rounded-lg text-sm font-semibold hover:bg-slate-800 transition-colors"
              >
                + Створити перше голосування
              </button>
            )}
          </div>
        );
      })()}

      {/* Таблиця зі списком голосувань */}
      {!isLoading && !error && filteredElections.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-[20px] overflow-hidden">
          {/* Заголовок таблиці (тільки на десктопі) */}
          <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-4 border-b border-slate-100 bg-slate-50/50 text-xs font-semibold text-slate-500">
            <div className="col-span-5">Назва голосування</div>
            <div className="col-span-2">Статус</div>
            <div className="col-span-2">Виборці</div>
            <div className="col-span-3 text-right">Дії</div>
          </div>

          {/* Рядки таблиці */}
          <div className="divide-y divide-slate-100">
            {filteredElections.map((election) => (
              <div key={election.id} className="flex flex-col md:grid md:grid-cols-12 gap-4 px-6 py-5 md:items-center hover:bg-slate-50 transition-colors">
                <div className="col-span-5 font-bold text-slate-900 text-base md:text-sm">
                  {election.title}
                </div>
                <div className="col-span-2 flex items-center">
                  {renderStatus(election.status)}
                </div>
                <div className="col-span-2 text-sm text-slate-500">
                  Кількість виборців — у моніторингу
                </div>
                <div className="col-span-3 flex flex-wrap md:flex-nowrap justify-start md:justify-end gap-2 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
                  {election.status === "active" && (
                    <>
                      <button 
                        onClick={() => navigate(`/admin/monitor/${election.id}`)}
                        className="bg-[#0B1B3D] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800"
                      >
                        Моніторинг
                      </button>
                      <button 
                        onClick={() => navigate(`/admin/edit/${election.id}`)}
                        className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50"
                      >
                        Редагувати
                      </button>
                    </>
                  )}
                  {(!election.status || election.status === "draft") && (
                    <>
                      <button 
                        onClick={() => navigate(`/admin/monitor/${election.id}`)}
                        className="bg-[#0B1B3D] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800"
                      >
                        Запустити
                      </button>
                      <button 
                        onClick={() => navigate(`/admin/edit/${election.id}`)}
                        className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50"
                      >
                        Редагувати
                      </button>
                    </>
                  )}
                  {(election.status === "closed") && (
                    <button 
                      onClick={() => navigate(`/admin/results/${election.id}`)}
                      className="bg-white border border-slate-200 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-50"
                    >
                      Результати та аудит
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Підсумок */}
      {!isLoading && !error && filteredElections.length > 0 && (
        <div className="mt-8 text-sm text-slate-500">
          Усього голосувань: {filteredElections.length}
        </div>
      )}
    </div>
  );
}