import { useState } from 'react';

export default function CreateElectionPage() {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    startDate: '',
    endDate: '',
  });
  
  const [candidates, setCandidates] = useState(['', '']); // Мінімум 2 кандидати
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  // Обробка текстових полів форми
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Обробка списку кандидатів
  const handleCandidateChange = (index: number, value: string) => {
    const newCandidates = [...candidates];
    newCandidates[index] = value;
    setCandidates(newCandidates);
  };

  const addCandidateField = () => setCandidates([...candidates, '']);
  
  const removeCandidateField = (index: number) => {
    if (candidates.length > 2) {
      setCandidates(candidates.filter((_, i) => i !== index));
    }
  };

  // Валідація та відправка
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setStatus('idle');

    // 1. Валідація
    if (!formData.title || !formData.description || !formData.startDate || !formData.endDate) {
      setErrorMessage('Усі основні поля є обовʼязковими.');
      setStatus('error');
      return;
    }
    if (new Date(formData.startDate) >= new Date(formData.endDate)) {
      setErrorMessage('Дата завершення має бути пізнішою за дату початку.');
      setStatus('error');
      return;
    }
    const validCandidates = candidates.filter(c => c.trim() !== '');
    if (validCandidates.length < 2) {
      setErrorMessage('Потрібно додати хоча б двох кандидатів.');
      setStatus('error');
      return;
    }

    // 2. Імітація запиту на бекенд (Mock)
    setStatus('submitting');
    try {
      await new Promise(resolve => setTimeout(resolve, 1500)); // Імітація затримки мережі
      
      // Тут в майбутньому буде реальний POST-запит, наприклад:
      // await api.post('/api/elections', { ...formData, candidates: validCandidates });
      
      setStatus('success');
      // Очищення форми після успішного створення
      setFormData({ title: '', description: '', startDate: '', endDate: '' });
      setCandidates(['', '']);
    } catch (err) {
      setErrorMessage('Помилка сервера. Спробуйте пізніше.');
      setStatus('error');
    }
  };

  return (
    <div className="max-w-2xl bg-white p-8 rounded-lg shadow-sm border border-gray-200">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Створити нові вибори</h1>
      
      {status === 'success' && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 border border-green-200 rounded-md">
          Вибори успішно створено (Mock)!
        </div>
      )}

      {status === 'error' && (
        <div className="mb-6 p-4 bg-red-50 text-red-700 border border-red-200 rounded-md">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Основна інформація */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Назва голосування</label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleInputChange}
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              placeholder="Наприклад: Вибори Голови Студради"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Опис</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleInputChange}
              rows={3}
              className="w-full p-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              placeholder="Короткий опис процедури та правил..."
            />
          </div>
        </div>

        {/* Дати */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Початок</label>
            <input
              type="datetime-local"
              name="startDate"
              value={formData.startDate}
              onChange={handleInputChange}
              className="w-full p-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Завершення</label>
            <input
              type="datetime-local"
              name="endDate"
              value={formData.endDate}
              onChange={handleInputChange}
              className="w-full p-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>

        {/* Кандидати */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Кандидати</label>
          <div className="space-y-2">
            {candidates.map((candidate, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={candidate}
                  onChange={(e) => handleCandidateChange(index, e.target.value)}
                  className="flex-1 p-2 border border-gray-300 rounded-md"
                  placeholder={`Кандидат ${index + 1}`}
                />
                {candidates.length > 2 && (
                  <button
                    type="button"
                    onClick={() => removeCandidateField(index)}
                    className="px-3 py-2 text-red-600 border border-red-200 rounded-md hover:bg-red-50"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addCandidateField}
            className="mt-3 text-sm text-blue-600 font-medium hover:underline"
          >
            + Додати кандидата
          </button>
        </div>

        {/* Сабміт */}
        <div className="pt-4 border-t border-gray-200 flex justify-end">
          <button
            type="submit"
            disabled={status === 'submitting'}
            className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {status === 'submitting' ? 'Збереження...' : 'Створити чернетку'}
          </button>
        </div>
      </form>
    </div>
  );
}