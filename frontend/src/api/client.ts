const BASE_URL = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

let refreshInFlight: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        accessToken = res.ok ? ((await res.json()) as { access_token: string }).access_token : null;
      } catch {
        accessToken = null;
      } finally {
        refreshInFlight = null;
      }
      return accessToken;
    })();
  }
  return refreshInFlight;
}

const NO_RETRY_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/logout', '/auth/telegram'];

const FRIENDLY_MESSAGES: [string, string][] = [
  ['String should match pattern', 'Недопустимые символы'],
  ['String should have at least 8 characters', 'Минимум 8 символов'],
  ['String should have at least 3 characters', 'Минимум 3 символа'],
  ['valid email', 'Некорректный email'],
];

interface ValidationItem {
  loc?: unknown[];
  msg?: string;
  message?: string;
}

function describeItem(item: unknown): string {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item);
  const { loc, msg, message } = item as ValidationItem;
  const field = Array.isArray(loc) ? loc.filter((p) => p !== 'body' && p !== 'query').join('.') : '';
  let text = msg ?? message ?? '';
  const friendly = FRIENDLY_MESSAGES.find(([needle]) => text.includes(needle));
  if (friendly) text = friendly[1];
  return field ? `${field}: ${text}` : text;
}

export function errorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object' || !('detail' in data)) return fallback;
  const detail = (data as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(describeItem).filter(Boolean).join('; ') || fallback;
  return fallback;
}

export async function apiRequest<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const url = `${BASE_URL}${endpoint}`;
  let response = await fetch(url, { ...options, headers, credentials: 'same-origin' });

  if (response.status === 401 && !NO_RETRY_ENDPOINTS.some((e) => endpoint.startsWith(e))) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      headers.Authorization = `Bearer ${fresh}`;
      response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
    } else {
      window.dispatchEvent(new Event('auth-expired'));
    }
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data: unknown = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(errorMessage(data, response.statusText || 'Ошибка запроса'), response.status, data);
  }
  return data as T;
}
