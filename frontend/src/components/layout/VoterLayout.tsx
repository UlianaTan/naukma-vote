import { Outlet, Link } from "react-router-dom";
import { Shield, LogOut, Info } from "lucide-react";
import { useAuth } from "../../features/voter/hooks/useAuth";

export function VoteBrand() {
  return <Link to="/" className="flex shrink-0 items-center gap-3" aria-label="NaUKMA Vote — головна">
    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white"><Shield size={21} /></span>
    <span><span className="block font-bold leading-tight">NaUKMA Vote</span><span className="block text-xs text-slate-500">Вибори НаУКМА</span></span>
  </Link>;
}
export function VoteFooter() {
  return <footer className="border-t border-slate-200 bg-white px-5 py-5 sm:px-8"><p className="flex items-start gap-2 text-xs text-slate-500 sm:text-sm"><Info size={16} className="shrink-0" />Виникли проблеми? Зверніться до служби підтримки НаУКМА.</p></footer>;
}
export default function VoterLayout() {
  const { user, logout, error } = useAuth();
  return <div className="vote-background flex min-h-screen flex-col">
    <header className="border-b border-slate-200 bg-white px-4 py-4 sm:px-8">
      <div className="flex flex-wrap items-center justify-between gap-4"><VoteBrand />
        <div className="flex min-w-0 items-center gap-3 sm:gap-5"><span className="max-w-[180px] break-all text-xs font-medium text-slate-600 sm:max-w-none sm:text-sm">{user?.email}</span><button onClick={() => void logout()} className="vote-button-secondary" aria-label="Вийти"><LogOut size={16} /><span className="hidden sm:inline">Вийти</span></button></div>
      </div>
    </header>
    <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-7 sm:px-8 sm:py-10">
      <nav aria-label="Основна навігація" className="mb-8 flex flex-wrap gap-5 text-sm"><Link to="/" className="font-semibold text-primary">Доступні голосування</Link><Link to="/admin" className="text-slate-500 hover:text-primary">Мої голосування — створити та керувати</Link></nav>
      {error && <p role="alert" className="mb-5 rounded-lg bg-red-50 p-4 text-red-700">{error}</p>}
      <Outlet />
    </main><VoteFooter />
  </div>;
}
