import type { SubScoreKey, SubScores } from '../api/types';
import { LOW_SIGNAL_THRESHOLD } from '../theme/tokens';

/** Backend-provided 0–1 value; falls back to score/20 only if the key is absent. */
export function normalizedOf(
  key: SubScoreKey,
  subScores: SubScores,
  normalized: Record<string, number> | undefined,
): number {
  const n = normalized?.[key];
  return typeof n === 'number' ? n : subScores[key] / 20;
}

/**
 * Known backend quirk: a missing momentum input yields exactly 10 (neutral)
 * with zero confidence for that dimension, so 10 + low overall confidence = no data.
 */
export function isNoData(key: SubScoreKey, value: number, confidence: number): boolean {
  return key === 'momentum' && value === 10 && confidence < LOW_SIGNAL_THRESHOLD;
}
