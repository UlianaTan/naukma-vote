import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./features/voter/hooks/useAuth";
import { ElectionsListPage } from "./features/voter/pages/ElectionsListPage";
import { LoginPage } from "./features/voter/pages/LoginPage";

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
          <Route path="/admin" element={<div>Тут буде адмін-панель</div>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;