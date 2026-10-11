import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/auth/LoginPage';
import VoterLayout from './components/layout/VoterLayout';
import AdminLayout from './components/layout/AdminLayout';
import AdminElectionsPage from './pages/admin/AdminElectionsPage';
import CreateElectionPage from './pages/admin/CreateElectionPage';
import VotersManagementPage from './pages/admin/VotersManagementPage';

const Placeholder = ({ title }: { title: string }) => (
  <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
);

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route path="/" element={<VoterLayout />}>
           <Route index element={<Placeholder title="Дашборд виборця" />} />
        </Route>

        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminElectionsPage />} />
          <Route path="create" element={<CreateElectionPage />} />
          <Route path="voters" element={<VotersManagementPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;