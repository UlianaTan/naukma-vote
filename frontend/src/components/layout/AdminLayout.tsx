import { useNavigate } from "react-router-dom";
import { useAuth } from "../../features/voter/hooks/useAuth";
import { Outlet, Link } from "react-router-dom";
import { Shield, Bell, LogOut, Info } from "lucide-react";

export default function AdminLayout() {
  const navigate = useNavigate();

  const { user, logout, error } = useAuth();

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] font-sans text-slate-900">
      
      {/* Верхня панель (Header) */}
      <header className="bg-white border-b border-slate-200 px-4 sm:px-8 py-4 flex flex-col sm:flex-row justify-between items-center gap-4 z-50">
        {/* Логотип */}
        <div 
          className="flex items-center gap-3 cursor-pointer w-full sm:w-auto justify-start"
          onClick={() => navigate("/admin")}
        >
          <div className="w-10 h-10 bg-[#0B1B3D] rounded-xl flex items-center justify-center text-white shrink-0">
            <Shield className="w-5 h-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-slate-900 leading-tight text-lg">NaUKMA Vote</span>
            <span className="text-xs text-slate-500 leading-tight">Вибори НаУКМА</span>
          </div>
        </div>

        {/* Профіль та дії */}
        <div className="flex items-center justify-between sm:justify-end gap-4 w-full sm:w-auto border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100">
          <button className="hidden sm:block text-slate-400 hover:text-slate-600 transition-colors">
            <Bell className="w-5 h-5" />
          </button>

          <div className="flex flex-col text-left sm:text-right">
            <span className="text-sm font-bold text-slate-900 leading-tight">{user?.email}</span>
            <span className="text-xs text-slate-500 leading-tight truncate max-w-[160px] sm:max-w-none">Мої голосування</span>
          </div>

          <button 
            onClick={() => void logout()}
            className="flex items-center gap-2 px-3 sm:px-4 py-2 border border-slate-200 rounded-lg text-slate-700 hover:bg-slate-50 text-sm font-semibold transition-colors shrink-0"
          >
            <LogOut className="w-4 h-4" />
            Вийти
          </button>
        </div>
      </header>

      {/* Основна робоча область */}
      <main className="flex-1 w-full max-w-5xl mx-auto py-6 sm:py-10 px-4 relative z-10">
        <nav className="mb-6 flex gap-4 text-sm underline"><Link to="/admin">Мої голосування</Link><Link to="/">Взяти участь у голосуванні</Link></nav>
        {error && <p role="alert">{error}</p>}
        <Outlet />
      </main>

      {/* Футер */}
      <footer className="border-t border-slate-200 bg-white py-6 px-4 sm:px-8 mt-auto flex justify-start">
        <div className="flex items-center gap-2 text-slate-500 text-xs sm:text-sm">
          <Info className="w-4 h-4 shrink-0" />
          <span>Виникли проблеми? Зверніться до служби підтримки НаУКМА.</span>
        </div>
      </footer>
    </div>
  );
}