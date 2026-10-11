export class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export const api = {
  // Додаємо <T>, щоб api розумів типи (наприклад <User>), і _ перед змінними, щоб лінтер не сварився
  get: async <T,>(_url: string, _config?: any): Promise<T> => ({} as T),
  post: async <T,>(_url: string, _data?: any, _config?: any): Promise<T> => ({} as T),
  patch: async <T,>(_url: string, _data?: any, _config?: any): Promise<T> => ({} as T),
  delete: async <T,>(_url: string, _config?: any): Promise<T> => ({} as T),
};