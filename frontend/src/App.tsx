import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import LoginPage from './pages/auth/LoginPage';

import VoterLayout from './components/layout/VoterLayout';

import AdminLayout from './components/layout/AdminLayout';
import VotersManagementPage from './pages/admin/VotersManagementPage';

// Заглушка для порожніх сторінок
const Placeholder = ({ title }: { title: string }) => (
  <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
);

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Сторінка логіну */}
        <Route path="/login" element={<LoginPage />} />

        {/* Роути ВИБОРЦЯ */}
        <Route path="/" element={<VoterLayout />}>
           <Route index element={<Placeholder title="Дашборд виборця (Задача Віки)" />} />
        </Route>

        {/* Роути АДМІНА */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Placeholder title="Список голосувань (Адмін)" />} />
          <Route path="voters" element={<VotersManagementPage />} />
          <Route path="settings" element={<Placeholder title="Налаштування" />} />
        </Route>

        {/* Редирект, якщо адреса неправильна */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;