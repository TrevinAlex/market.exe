import type { SubScoreKey, SubScores } from '../api/types';
import { LOW_SIGNAL_THRESHOLD } from '../theme/tokens';

export function normalizedOf(
  key: SubScoreKey,
  subScores: SubScores,
  normalized: Record<string, number> | undefined,
): number {
  const n = normalized?.[key];
  return typeof n === 'number' ? n : subScores[key] / 20;
}

export function isNoData(key: SubScoreKey, value: number, confidence: number): boolean {
  return key === 'momentum' && value === 10 && confidence < LOW_SIGNAL_THRESHOLD;
}
