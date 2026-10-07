import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './features/voter/hooks/useAuth';
import { LoginPage } from './features/voter/pages/LoginPage';
import { ElectionsListPage } from './features/voter/pages/ElectionsListPage';
import { VotingPage } from './features/voter/pages/VotingPage';
import { ResultPage } from './features/voter/pages/ResultPage';
import AdminLayout from './components/layout/AdminLayout';
import AdminElectionsPage from './pages/admin/AdminElectionsPage';
import CreateElectionPage from './pages/admin/CreateElectionPage';

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
        <Routes>
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

          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<AdminElectionsPage />} />
            <Route path="create" element={<CreateElectionPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
