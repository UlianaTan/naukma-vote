import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, Users, Settings, LogOut, Shield } from "lucide-react";

export default function AdminLayout() {
  // Пункти меню для адмінки (сюди входить твоя задача на 5 тиждень)
  const navItems = [
    { path: "/admin", icon: LayoutDashboard, label: "Голосування" },
    { path: "/admin/voters", icon: Users, label: "База виборців" },
    { path: "/admin/settings", icon: Settings, label: "Налаштування" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900">
      
      {/* Бокова панель (Sidebar) */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col fixed inset-y-0 left-0 z-50">
        
        {/* Логотип */}
        <div className="h-[72px] flex items-center px-6 border-b border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-[#0B1B3D] rounded-xl flex items-center justify-center text-white shrink-0">
              <Shield className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-slate-900 leading-tight">NaUKMA Vote</span>
              <span className="text-[10px] text-slate-500 leading-tight uppercase tracking-widest font-semibold">
                Admin Panel
              </span>
            </div>
          </div>
        </div>

        {/* Навігація */}
        <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
          <p className="px-3 text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">
            Меню
          </p>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/admin"} // Щоб головна сторінка не підсвічувалась постійно
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? "bg-slate-100 text-[#0B1B3D]"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Футер сайдбару (Профіль організатора / Вихід) */}
        <div className="p-4 border-t border-slate-200">
          <div className="flex items-center gap-3 px-3 py-3 mb-3 rounded-xl bg-slate-50 border border-slate-100">
            <div className="w-9 h-9 bg-[#0B1B3D]/10 rounded-full flex items-center justify-center text-[#0B1B3D] font-bold text-sm">
              О
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-semibold truncate">Організатор</span>
              <span className="text-xs text-slate-500 truncate">admin@ukma.edu.ua</span>
            </div>
          </div>
          <button className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-red-600 rounded-xl hover:bg-red-50 transition-colors">
            <LogOut className="w-5 h-5" />
            Вийти
          </button>
        </div>
      </aside>

      {/* Основна робоча область (куди будуть рендеритись сторінки адмінки) */}
      <main className="flex-1 ml-64 min-h-screen relative flex flex-col">
        {/* Фонова сітка для стилістики */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-[0.15] z-0"
          style={{
            backgroundImage: `linear-gradient(to right, #94a3b8 1px, transparent 1px), linear-gradient(to bottom, #94a3b8 1px, transparent 1px)`,
            backgroundSize: '5rem 5rem'
          }}
        />
        
        {/* Вміст сторінки */}
        <div className="relative z-10 p-8 flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
