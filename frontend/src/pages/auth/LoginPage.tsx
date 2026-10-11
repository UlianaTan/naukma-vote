import { Shield } from "lucide-react";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    console.log("Редирект на Google OAuth...");
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
        <div className="w-16 h-16 bg-[#0B1B3D] rounded-2xl flex items-center justify-center mx-auto mb-6 text-white">
          <Shield className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2">NaUKMA Vote</h1>
        <p className="text-slate-500 mb-8">
          Авторизація доступна лише для корпоративних акаунтів @ukma.edu.ua
        </p>
        
        <button 
          onClick={handleGoogleLogin}
          className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white border-2 border-slate-200 text-slate-700 font-medium rounded-xl hover:bg-slate-50 hover:border-[#0B1B3D] transition-all"
        >
          <img src="https://www.svgrepo.com/show/475656/google-color.svg" alt="Google" className="w-5 h-5" />
          Увійти через Google
        </button>
      </div>
    </div>
  );
}