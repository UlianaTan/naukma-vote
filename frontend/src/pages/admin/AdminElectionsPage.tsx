import { Link } from 'react-router-dom';
export default function AdminElectionsPage() {
  // Тимчасові тестові дані для відображення
  const mockElections = [
    { id: 1, title: "Вибори Голови Студради НаУКМА", status: "Активні", date: "2026-10-15", voters: 1250 },
    { id: 2, title: "Делегати Вченої ради ФІ", status: "Заплановані", date: "2026-11-01", voters: 450 },
    { id: 3, title: "Вибори Голови СК ФІ", status: "Завершені", date: "2026-09-10", voters: 520 },
  ];
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Шапка таблиці */}
      <div className="flex justify-between items-center p-6 border-b border-gray-200">
        <h1 className="text-2xl font-bold text-gray-900">Управління виборами</h1>
        <Link to="/admin/create" className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium">
            + Створити вибори
        </Link>
      </div>
      {/* Сама таблиця */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 text-gray-600 text-sm border-b border-gray-200">
              <th className="p-4 font-semibold">Назва</th>
              <th className="p-4 font-semibold">Статус</th>
              <th className="p-4 font-semibold">Дата</th>
              <th className="p-4 font-semibold">К-ть виборців</th>
              <th className="p-4 font-semibold">Дії</th>
            </tr>
          </thead>
          <tbody className="text-gray-800 text-sm">
            {mockElections.map((election) => (
              <tr key={election.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="p-4 font-medium">{election.title}</td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium 
                    ${election.status === 'Активні' ? 'bg-green-100 text-green-700' : 
                      election.status === 'Заплановані' ? 'bg-yellow-100 text-yellow-700' : 
                      'bg-gray-100 text-gray-700'}`}>
                    {election.status}
                  </span>
                </td>
                <td className="p-4">{election.date}</td>
                <td className="p-4">{election.voters}</td>
                <td className="p-4">
                  <button className="text-blue-600 hover:underline mr-3">Редагувати</button>
                  <button className="text-red-600 hover:underline">Видалити</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}