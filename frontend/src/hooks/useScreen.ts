import { api } from '../api/client';
import type { ScreenResponse } from '../api/types';
import { useAsync } from './useAsync';

export function useScreen(index = 'LQ45', limit = 20) {
  return useAsync<ScreenResponse>(`${index}:${limit}`, (signal) => api.screen(index, limit, signal));
}
