import { api } from '../api/client';
import type { HeatmapResponse } from '../api/types';
import { useAsync } from './useAsync';

export function useHeatmap(index = 'LQ45') {
  return useAsync<HeatmapResponse>(index, (signal) => api.heatmap(index, signal));
}
