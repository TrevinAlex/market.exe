import type {
  HeatmapResponse,
  Score,
  ScreenResponse,
  SimulateOptions,
  SimulationResponse,
} from './types';

/** Base path. In dev, Vite proxies /api to http://127.0.0.1:8000. */
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

const TICKER_RE = /^[A-Za-z]{4}$/;
const INDEX_RE = /^[A-Za-z0-9]{2,20}$/;

/** Error carrying the HTTP status and a user-facing message. */
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

/** Validate + normalise a ticker. Returns the uppercased symbol or null. */
export function normalizeTicker(input: string): string | null {
  const t = input.trim();
  return TICKER_RE.test(t) ? t.toUpperCase() : null;
}

/** Strip the ".JK" exchange suffix the screener sometimes returns. */
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

/** Turn a non-OK response into a user-facing ApiError. */
export async function toApiError(res: Response): Promise<ApiError> {
  let detail: string | null = null;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body) {
      const d = (body as { detail: unknown }).detail;
      // FastAPI validation errors (422) return an array of objects.
      detail = typeof d === 'string' ? d : JSON.stringify(d);
    }
  } catch {
    /* body was not JSON */
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init.headers ?? {}) },
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

  heatmap(index = 'LQ45', signal?: AbortSignal): Promise<HeatmapResponse> {
    const qs = new URLSearchParams({ index: assertIndex(index) });
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
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return 'Unknown error';
}
