import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AdminLayout from './components/layout/AdminLayout';
import AdminElectionsPage from './pages/admin/AdminElectionsPage';
import CreateElectionPage from './pages/admin/CreateElectionPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Тимчасова заглушка для інтерфейсу виборця */}
        <Route path="/" element={<div className="p-4">Тут буде інтерфейс виборця</div>} />

        {/* Роути адмін-панелі */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminElectionsPage />} />
          <Route path="create" element={<CreateElectionPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
