import { Outlet } from "react-router-dom";
import { Bell, LogOut, Shield, User } from "lucide-react";

export default function VoterLayout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      
      {/* Верхня панель навігації (Хедер) */}
      <header className="sticky top-0 z-50 w-full bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        
        {/* Ліва частина: Логотип */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#0B1B3D] rounded-xl flex items-center justify-center text-white shrink-0">
            <Shield className="w-5 h-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-slate-900 leading-tight">NaUKMA Vote</span>
            <span className="text-xs text-slate-500 leading-tight">Вибори НаУКМА</span>
          </div>
        </div>

        {/* Права частина: Профіль та дії */}
        <div className="flex items-center gap-4 sm:gap-6">
          
          {/* Кнопка сповіщень */}
          <button className="text-slate-500 hover:text-slate-900 transition-colors p-1 relative">
            <Bell className="w-5 h-5" />
            {/* Червона крапка (індикатор нових сповіщень) */}
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
          </button>

          {/* Інформація про користувача */}
          <div className="flex items-center gap-3 border-l border-slate-200 pl-4 sm:pl-6">
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-sm font-semibold text-slate-900 leading-tight">user</span>
              <span className="text-xs text-slate-500 leading-tight">user@ukma.edu.ua</span>
            </div>
            {/* Аватарка (замінимо на фото потім, поки іконка) */}
            <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center border border-slate-200 overflow-hidden shrink-0">
              <User className="w-5 h-5 text-slate-400" />
            </div>
          </div>

          {/* Кнопка "Вийти" */}
          <button className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors ml-2">
            <LogOut className="w-4 h-4 text-slate-500" />
            <span className="hidden md:inline">Вийти</span>
          </button>
        </div>
        
      </header>

      {/* Основний контент сторінок */}
      <main className="flex-1 w-full max-w-5xl mx-auto p-4 sm:p-6 lg:p-8 relative">
        {/* 
          Фонова сітка. Залишив її тут, щоб вона була на всіх внутрішніх сторінках,
          якщо за дизайном вона потрібна і там.
        */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-[0.15] z-0"
          style={{
            backgroundImage: `linear-gradient(to right, #94a3b8 1px, transparent 1px), linear-gradient(to bottom, #94a3b8 1px, transparent 1px)`,
            backgroundSize: '5rem 5rem'
          }}
        />
        
        {/* Контейнер для дочірніх сторінок (Дашборд, Голосування тощо) */}
        <div className="relative z-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
