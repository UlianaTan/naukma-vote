import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<div className="p-4">Тут буде інтерфейс виборця</div>} />
        <Route path="/admin" element={<div className="p-4">Тут буде адмін-панель</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;