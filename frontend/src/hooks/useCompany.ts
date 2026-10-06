import { api } from '../api/client';
import type { Score } from '../api/types';
import { useAsync } from './useAsync';

export function useCompany(symbol: string | null) {
  return useAsync<Score>(symbol, (signal) => api.company(symbol as string, signal));
}
