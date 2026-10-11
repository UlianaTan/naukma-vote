import { useState } from "react";
import { Search, Plus, Upload, MoreHorizontal, FileDown, ShieldCheck, X, FileSpreadsheet, UploadCloud } from "lucide-react";

// Тимчасові дані для таблиці
const MOCK_VOTERS = [
  { id: 1, name: "Коваленко Дмитро Олександрович", email: "d.kovalenko@ukma.edu.ua", faculty: "ФІ", year: "3 курс", status: "Активний" },
  { id: 2, name: "Шевченко Анастасія Ігорівна", email: "a.shevchenko@ukma.edu.ua", faculty: "ФІ", year: "3 курс", status: "Активний" },
  { id: 3, name: "Мельник Ярослав Володимирович", email: "y.melnyk@ukma.edu.ua", faculty: "ФПрН", year: "2 курс", status: "Активний" },
  { id: 4, name: "Бойко Софія Андріївна", email: "s.boiko@ukma.edu.ua", faculty: "ФГН", year: "1 курс", status: "Активний" },
];

export default function VotersManagementPage() {
  const [searchTerm, setSearchTerm] = useState("");
  // Стани для відкриття/закриття модальних вікон
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);

  return (
    <div className="w-full max-w-6xl mx-auto flex flex-col h-full relative">
      
      {/* Заголовок та головні дії */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">База виборців</h1>
          <p className="text-sm text-slate-500">Керування списками студентів, які мають право голосу</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={() => setIsCsvModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            Імпорт CSV
          </button>
          <button 
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-[#0B1B3D] hover:bg-[#0B1B3D]/90 rounded-lg transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Додати виборця
          </button>
        </div>
      </div>

      {/* Панель фільтрів та пошуку */}
      <div className="bg-white p-4 rounded-t-2xl border border-slate-200 border-b-0 flex flex-col sm:flex-row gap-4 justify-between items-center">
        <div className="relative w-full sm:w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Пошук за ПІБ або поштою..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent transition-colors"
          />
        </div>
        
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <button className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 bg-slate-50 border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors w-full sm:w-auto justify-center">
            <FileDown className="w-4 h-4" />
            Експорт
          </button>
        </div>
      </div>

      {/* Таблиця */}
      <div className="bg-white border border-slate-200 rounded-b-2xl overflow-hidden shadow-sm flex-1">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase font-semibold text-slate-500">
              <tr>
                <th className="px-6 py-4">Студент</th>
                <th className="px-6 py-4">Пошта</th>
                <th className="px-6 py-4">Факультет</th>
                <th className="px-6 py-4">Статус</th>
                <th className="px-6 py-4 text-right">Дії</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {MOCK_VOTERS.map((voter) => (
                <tr key={voter.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-900">{voter.name}</div>
                  </td>
                  <td className="px-6 py-4">{voter.email}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 bg-slate-100 text-slate-700 text-xs font-semibold rounded-md">
                        {voter.faculty}
                      </span>
                      <span className="text-slate-400 text-xs">{voter.year}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-100">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {voter.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors">
                      <MoreHorizontal className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Пагінація */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <span className="text-sm text-slate-500">
            Показано <span className="font-medium text-slate-900">4</span> з <span className="font-medium text-slate-900">4</span> студентів
          </span>
          <div className="flex gap-1">
            <button className="px-3 py-1 text-sm font-medium text-slate-400 bg-white border border-slate-200 rounded-md cursor-not-allowed">
              Попередня
            </button>
            <button className="px-3 py-1 text-sm font-medium text-slate-400 bg-white border border-slate-200 rounded-md cursor-not-allowed">
              Наступна
            </button>
          </div>
        </div>
      </div>

      {/* Модальне вікно "Додати виборця" */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-lg font-semibold text-slate-900">Додати виборця</h2>
              <button onClick={() => setIsAddModalOpen(false)} className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">ПІБ студента</label>
                <input type="text" placeholder="Наприклад: Іванов Іван Іванович" className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent" />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-slate-700">Корпоративна пошта</label>
                <input type="email" placeholder="ivan.ivanov@ukma.edu.ua" className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-700">Факультет</label>
                  <select className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent bg-white">
                    <option value="">Оберіть...</option>
                    <option value="ФІ">ФІ</option>
                    <option value="ФГН">ФГН</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-700">Курс</label>
                  <select className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0B1B3D] focus:border-transparent bg-white">
                    <option value="">Оберіть...</option>
                    <option value="1">1 курс БП</option>
                    <option value="2">2 курс БП</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-3">
              <button onClick={() => setIsAddModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors">Скасувати</button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-[#0B1B3D] hover:bg-[#0B1B3D]/90 rounded-lg transition-colors">Зберегти в базу</button>
            </div>
          </div>
        </div>
      )}

      {/* Модальне вікно "Імпорт CSV" */}
      {isCsvModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-lg font-semibold text-slate-900">Імпорт списку виборців</h2>
              <button 
                onClick={() => setIsCsvModalOpen(false)}
                className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              <p className="text-sm text-slate-500 mb-4">
                Завантажте CSV-файл зі списком студентів. Переконайтеся, що файл містить колонки: <span className="font-medium text-slate-700">ПІБ, Пошта, Факультет, Курс</span>.
              </p>
              
              {/* Зона завантаження */}
              <div className="border-2 border-dashed border-slate-200 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:bg-slate-50 hover:border-[#0B1B3D]/50 transition-colors cursor-pointer group">
                <div className="w-12 h-12 bg-slate-100 group-hover:bg-[#0B1B3D]/10 rounded-full flex items-center justify-center mb-4 transition-colors">
                  <UploadCloud className="w-6 h-6 text-slate-500 group-hover:text-[#0B1B3D]" />
                </div>
                <h3 className="text-sm font-medium text-slate-900 mb-1">
                  Натисніть для вибору або перетягніть файл сюди
                </h3>
                <p className="text-xs text-slate-500">
                  Формат CSV. Максимальний розмір 5 MB.
                </p>
                <input type="file" accept=".csv" className="hidden" />
              </div>

              {/* Приклад формату */}
              <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-100">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Приклад формату</span>
                </div>
                <code className="text-xs text-slate-500 block overflow-x-auto whitespace-pre">
                  ПІБ,Пошта,Факультет,Курс<br/>
                  Шевченко А.І.,a.shevchenko@ukma.edu.ua,ФІ,3
                </code>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-3">
              <button 
                onClick={() => setIsCsvModalOpen(false)}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Скасувати
              </button>
              <button className="px-4 py-2 text-sm font-medium text-white bg-[#0B1B3D] hover:bg-[#0B1B3D]/90 rounded-lg transition-colors">
                Завантажити
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}