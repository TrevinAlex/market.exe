import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, api, setAuthToken } from '../api/client';
import type { AuthResponse, User } from '../api/types';

const STORAGE_KEY = 'market.exe.auth';

interface StoredAuth {
  token: string;
  expiresAt: number;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  checking: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function readStored(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as StoredAuth;
    return typeof s.token === 'string' && s.expiresAt > Date.now() ? s : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredAuth | null>(() => {
    const s = readStored();
    setAuthToken(s?.token ?? null);
    return s;
  });
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(stored != null);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setAuthToken(null);
    setStored(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (!stored || user) return;
    const ctrl = new AbortController();
    setChecking(true);
    api
      .me(stored.token, ctrl.signal)
      .then(setUser)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) logout();
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setChecking(false);
      });
    return () => ctrl.abort();
  }, [stored?.token]);

  const accept = useCallback((r: AuthResponse) => {
    const s = { token: r.access_token, expiresAt: Date.now() + r.expires_in * 1000 };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    setAuthToken(s.token);
    setUser(r.user);
    setStored(s);
  }, []);

  const login = useCallback(async (u: string, p: string) => accept(await api.login(u, p)), [accept]);
  const register = useCallback(async (u: string, p: string) => accept(await api.register(u, p)), [accept]);

  const value = useMemo<AuthState>(
    () => ({ user, token: stored?.token ?? null, checking, login, register, logout }),
    [user, stored, checking, login, register, logout],
  );
  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
