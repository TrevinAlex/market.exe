import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import type { SimulateOptions, SimulationResponse } from '../api/types';

export function useSimulate(symbol: string | null, opts: SimulateOptions = { runs: 500, days: 30 }) {
  const [data, setData] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);
  const { runs, days } = opts;

  useEffect(() => {
    ctrlRef.current?.abort();
    setData(null);
    setError(null);
    setLoading(false);
  }, [symbol]);

  useEffect(() => () => ctrlRef.current?.abort(), []);

  const run = useCallback(() => {
    if (!symbol) return;
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    setLoading(true);
    setError(null);
    api
      .simulate(symbol, { runs, days }, ctrl.signal)
      .then((d) => !ctrl.signal.aborted && setData(d))
      .catch((e) => !ctrl.signal.aborted && setError(e))
      .finally(() => !ctrl.signal.aborted && setLoading(false));
  }, [symbol, runs, days]);

  return { data, error, loading, run };
}
