import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, baseTicker, errorMessage } from '../api/client';
import { useAuth } from './useAuth';

export interface PinsState {
  /** Pinned tickers in pin order (bare symbols, e.g. "BBCA"). */
  symbols: string[];
  isPinned: (symbol: string) => boolean;
  /** Pin if not pinned, else unpin. Optimistic; rolls back on error. */
  toggle: (symbol: string) => Promise<void>;
  /** False when logged out or pins can't be loaded (e.g. not configured). */
  available: boolean;
  maxPins: number;
  error: string | null;
  clearError: () => void;
}

const PinsContext = createContext<PinsState | null>(null);

/** Loads the logged-in user's pins; must sit inside <AuthProvider>. */
export function PinsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [symbols, setSymbols] = useState<string[]>([]);
  const [available, setAvailable] = useState(false);
  const [maxPins, setMaxPins] = useState(20);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSymbols([]);
    setAvailable(false);
    setError(null);
    if (!user) return;
    const ctrl = new AbortController();
    api
      .pins(false, ctrl.signal)
      .then((r) => {
        setSymbols(r.pins.map((p) => p.symbol));
        setMaxPins(r.max_pins);
        setAvailable(true);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(errorMessage(e));
      });
    return () => ctrl.abort();
  }, [user]);

  const toggle = useCallback(
    async (symbol: string) => {
      const sym = baseTicker(symbol);
      const was = symbols.includes(sym);
      setError(null);
      setSymbols((s) => (was ? s.filter((x) => x !== sym) : [...s, sym]));
      try {
        await (was ? api.unpin(sym) : api.pin(sym));
      } catch (e) {
        setSymbols((s) => (was ? [...s, sym] : s.filter((x) => x !== sym)));
        setError(errorMessage(e));
      }
    },
    [symbols],
  );

  const value = useMemo<PinsState>(
    () => ({
      symbols,
      isPinned: (s) => symbols.includes(baseTicker(s)),
      toggle,
      available,
      maxPins,
      error,
      clearError: () => setError(null),
    }),
    [symbols, toggle, available, maxPins, error],
  );
  return createElement(PinsContext.Provider, { value }, children);
}

export function usePins(): PinsState {
  const ctx = useContext(PinsContext);
  if (!ctx) throw new Error('usePins must be used inside <PinsProvider>');
  return ctx;
}
