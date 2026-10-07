import type {
  AuthResponse,
  HeatmapResponse,
  HistoryKind,
  HistoryResponse,
  PinsResponse,
  User,
  Score,
  ScreenResponse,
  SimulateOptions,
  SimulationResponse,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

const TICKER_RE = /^[A-Za-z]{4}$/;
const INDEX_RE = /^[A-Za-z0-9]{2,20}$/;

export class ApiError extends Error {
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

export function normalizeTicker(input: string): string | null {
  const t = input.trim();
  return TICKER_RE.test(t) ? t.toUpperCase() : null;
}

export function baseTicker(symbol: string): string {
  return symbol.replace(/\.JK$/i, '').toUpperCase();
}

function parseRetryAfter(header: string | null): number | null {
  if (!header) return null;
  const secs = Number(header);
  if (Number.isFinite(secs)) return Math.max(0, Math.ceil(secs));
  const date = Date.parse(header);
  if (!Number.isNaN(date)) return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  return null;
}

export async function toApiError(res: Response): Promise<ApiError> {
  let detail: string | null = null;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body) {
      const d = (body as { detail: unknown }).detail;
      detail = typeof d === 'string' ? d : JSON.stringify(d);
    }
  } catch {
  }

  if (res.status === 429) {
    const retry = parseRetryAfter(res.headers.get('Retry-After'));
    return new ApiError(
      retry != null ? `Rate limited, retry in ${retry}s` : 'Rate limited, retry shortly',
      429,
      retry,
    );
  }
  if (res.status === 400) return new ApiError('Invalid ticker', 400);
  return new ApiError(detail ?? `Request failed (HTTP ${res.status})`, res.status);
}

let authToken: string | null = null;
export function setAuthToken(token: string | null): void {
  authToken = token;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError('Backend unreachable. Is the API running on :8000?', 0);
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

function assertIndex(index: string): string {
  if (!INDEX_RE.test(index)) throw new ApiError('Invalid index', 400);
  return index;
}

function assertTicker(symbol: string): string {
  const t = normalizeTicker(baseTicker(symbol));
  if (!t) throw new ApiError('Invalid ticker', 400);
  return t;
}

export const api = {
  screen(index = 'LQ45', limit = 20, signal?: AbortSignal): Promise<ScreenResponse> {
    const qs = new URLSearchParams({ index: assertIndex(index), limit: String(limit) });
    return request<ScreenResponse>(`/api/screen?${qs}`, { signal });
  },

  heatmap(index: string | null = null, limit = 200, signal?: AbortSignal): Promise<HeatmapResponse> {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (index) qs.set('index', assertIndex(index));
    return request<HeatmapResponse>(`/api/heatmap?${qs}`, { signal });
  },

  company(symbol: string, signal?: AbortSignal): Promise<Score> {
    return request<Score>(`/api/company/${encodeURIComponent(assertTicker(symbol))}`, { signal });
  },

  simulate(
    symbol: string,
    { runs = 500, days = 30 }: SimulateOptions = {},
    signal?: AbortSignal,
  ): Promise<SimulationResponse> {
    const qs = new URLSearchParams({ runs: String(runs), days: String(days) });
    return request<SimulationResponse>(
      `/api/simulate/${encodeURIComponent(assertTicker(symbol))}?${qs}`,
      { method: 'POST', signal },
    );
  },

  register(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>('/api/auth/register', jsonPost({ username, password }));
  },

  login(username: string, password: string): Promise<AuthResponse> {
    return request<AuthResponse>('/api/auth/login', jsonPost({ username, password }));
  },

  me(token: string, signal?: AbortSignal): Promise<User> {
    return request<User>('/api/auth/me', { headers: { Authorization: `Bearer ${token}` }, signal });
  },

  history(
    { kind, limit = 50, offset = 0 }: { kind?: HistoryKind; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<HistoryResponse> {
    const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (kind) qs.set('kind', kind);
    return request<HistoryResponse>(`/api/history?${qs}`, { signal });
  },

  deleteHistory(id?: number): Promise<{ deleted: number }> {
    const path = id == null ? '/api/history' : `/api/history/${encodeURIComponent(String(id))}`;
    return request<{ deleted: number }>(path, { method: 'DELETE' });
  },

  pins(withScores = false, signal?: AbortSignal): Promise<PinsResponse> {
    return request<PinsResponse>(`/api/pins${withScores ? '?scores=true' : ''}`, { signal });
  },

  pin(symbol: string): Promise<{ symbol: string; pinned: boolean }> {
    return request(`/api/pins/${encodeURIComponent(assertTicker(symbol))}`, { method: 'PUT' });
  },

  unpin(symbol: string): Promise<{ symbol: string; pinned: boolean }> {
    return request(`/api/pins/${encodeURIComponent(assertTicker(symbol))}`, { method: 'DELETE' });
  },
};

function jsonPost(body: unknown): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

export const USERNAME_RE = /^[A-Za-z0-9_]{3,32}$/;
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return 'Unknown error';
}
