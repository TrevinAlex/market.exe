import { api } from '../api/client';
import type { HeatmapResponse } from '../api/types';
import { useAsync } from './useAsync';

export function useHeatmap(index: string | null = null, limit = 200) {
  return useAsync<HeatmapResponse>(`${index ?? 'top'}:${limit}`, (signal) => api.heatmap(index, limit, signal));
}
