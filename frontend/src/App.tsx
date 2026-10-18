import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast'; // 1. Імпортуємо Toaster
import { AuthProvider, useAuth } from './features/voter/hooks/useAuth';
import { LoginPage } from './features/voter/pages/LoginPage';
import { ElectionsListPage } from './features/voter/pages/ElectionsListPage';
import { VotingPage } from './features/voter/pages/VotingPage';
import { ResultPage } from './features/voter/pages/ResultPage';
import AdminLayout from './components/layout/AdminLayout';
import { AdminElectionsPage } from './pages/admin/AdminElectionsPage';
import { CreateElectionPage } from './pages/admin/CreateElectionPage';
import VotersManagementPage from './pages/admin/VotersManagementPage';
import { ElectionMonitoringPage } from './pages/admin/ElectionMonitoringPage';
import { ElectionResultsPage } from './pages/admin/ElectionResultsPage';
import { AuditLogPage } from './pages/admin/AuditLogPage';
import toast from 'react-hot-toast';

function ProtectedVoterRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* 2. Додаємо компонент Toaster сюди, всередину BrowserRouter */}
        <Toaster 
          position="top-right" 
          toastOptions={{
            duration: 4000,
            style: {
              background: '#0B1B3D',
              color: '#fff',
            },
          }} 
        />
        
        <Routes>
          {/* Студентські маршрути */}
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/"
            element={
              <ProtectedVoterRoute>
                <ElectionsListPage />
              </ProtectedVoterRoute>
            }
          />
          <Route
            path="/vote/:id"
            element={
              <ProtectedVoterRoute>
                <VotingPage />
              </ProtectedVoterRoute>
            }
          />
          <Route
            path="/vote/:id/done"
            element={
              <ProtectedVoterRoute>
                <ResultPage />
              </ProtectedVoterRoute>
            }
          />

          {/* Єдина секція для всіх адміністративних маршрутів під AdminLayout */}
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminElectionsPage />} />
            <Route path="create" element={<CreateElectionPage />} />
            <Route path="edit/:id" element={<CreateElectionPage />} />
            <Route path="voters" element={<VotersManagementPage />} />
            <Route path="monitor/:id" element={<ElectionMonitoringPage />} />
            <Route path="results/:id" element={<ElectionResultsPage />} />
            <Route path="audit/:id" element={<AuditLogPage />} />
          </Route>

          {/* Усі інші невідомі шляхи направляємо на головну */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;