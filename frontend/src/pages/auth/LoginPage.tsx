import { Eye, Info } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col relative text-slate-900">
      
      {/* Фонова сітка (Grid) */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-[0.15]"
        style={{
          backgroundImage: `linear-gradient(to right, #94a3b8 1px, transparent 1px), linear-gradient(to bottom, #94a3b8 1px, transparent 1px)`,
          backgroundSize: '5rem 5rem'
        }}
      />

      {/* Основна частина */}
      <main className="flex-1 flex items-center justify-center p-4 relative z-10">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100 p-8 sm:p-10">
          
          <div className="text-center mb-8">
            <p className="text-sm font-bold text-[#0B1B3D] tracking-widest uppercase mb-2">
              NaUKMA Vote
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">
              Вхід у систему голосувань
            </h1>
          </div>

          <form className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700" htmlFor="email">
                Корпоративна пошта
              </label>
              <input
                id="email"
                type="email"
                placeholder="your.name@ukma.edu.ua"
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent transition-colors text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700" htmlFor="password">
                Пароль
              </label>
              <div className="relative">
                <input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent transition-colors text-sm pr-10"
                />
                <button 
                  type="button" 
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <Eye className="w-5 h-5" />
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="w-full bg-[#0B1B3D] hover:bg-[#0B1B3D]/90 text-white font-medium py-3 rounded-lg transition-colors mt-4"
            >
              Увійти
            </button>
          </form>

          <p className="text-center text-xs text-slate-500 mt-6 leading-relaxed">
            Авторизація доступна виключно для корпоративних акаунтів<br />НаУКМА
          </p>
        </div>
      </main>

      {/* Футер */}
      <footer className="relative z-10 w-full p-6 bg-white border-t border-slate-200 mt-auto">
        <div className="max-w-7xl mx-auto flex items-center text-sm text-slate-600">
          <Info className="w-4 h-4 mr-2 text-slate-400" />
          <p>Виникли проблеми? Зверніться до служби підтримки НаУКМА.</p>
        </div>
      </footer>
    </div>
  );
}