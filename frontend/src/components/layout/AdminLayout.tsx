import { Outlet, Link } from 'react-router-dom';

export default function AdminLayout() {
  return (
    <div className="flex min-h-screen bg-gray-100">
      {/* Бокова панель навігації */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-800">KMA Vote Admin</h2>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <Link 
            to="/admin" 
            className="block px-4 py-2 text-gray-700 bg-gray-100 rounded-md font-medium"
          >
            Список виборів
          </Link>
          <Link 
            to="/admin/voters" 
            className="block px-4 py-2 text-gray-600 hover:bg-gray-50 rounded-md"
          >
            База виборців
          </Link>
        </nav>
      </aside>

      {/* Основний контент (сюди підставляється AdminElectionsPage) */}
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}