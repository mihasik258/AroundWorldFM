const BASE_URL = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: any, status: number, data: any) {
    const formatted = typeof message === 'string' ? message : JSON.stringify(message);
    super(formatted);
    this.status = status;
    this.data = data;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

// The access token lives only in memory: unlike localStorage, a variable does
// not outlive the page and is not sitting in storage for a script to harvest.
// The refresh token is an httpOnly cookie that JavaScript cannot read at all;
// the browser attaches it to /auth/refresh by itself.
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

// Tokens from the old scheme stayed in localStorage; drop them on first load.
localStorage.removeItem('access_token');
localStorage.removeItem('refresh_token');

// Every refresh rotates the refresh cookie, and presenting the same cookie
// twice outside a short window counts as theft. Several requests failing with
// 401 at once must therefore share one refresh instead of racing.
let refreshInFlight: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        accessToken = res.ok ? (await res.json()).access_token : null;
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

const NO_RETRY_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/logout'];

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const url = `${BASE_URL}${endpoint}`;
  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin',
  });

  // Access token expired or its session was revoked: try one silent refresh
  if (response.status === 401 && !NO_RETRY_ENDPOINTS.some((e) => endpoint.startsWith(e))) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      headers['Authorization'] = `Bearer ${fresh}`;
      response = await fetch(url, { ...options, headers, credentials: 'same-origin' });
    } else {
      window.dispatchEvent(new Event('auth-expired'));
    }
  }

  const isJson = response.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    let errorMsg = response.statusText;
    if (isJson && data?.detail) {
      if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail
          .map((item: any) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
              const loc = Array.isArray(item.loc)
                ? item.loc.filter((part: any) => part !== 'body' && part !== 'query').join('.')
                : '';
              let msg = item.msg || item.message || '';
              if (msg.includes('String should match pattern')) {
                msg = 'Разрешены только латинские буквы, цифры, знаки _ и -';
              } else if (msg.includes('String should have at least 8 characters')) {
                msg = 'Минимум 8 символов';
              } else if (msg.includes('String should have at least 3 characters')) {
                msg = 'Минимум 3 символа';
              } else if (msg.includes('valid email')) {
                msg = 'Некорректный адрес email';
              }
              return loc ? `${loc}: ${msg}` : msg;
            }
            return String(item);
          })
          .filter(Boolean)
          .join('; ');
      } else if (typeof data.detail === 'object') {
        errorMsg = JSON.stringify(data.detail);
      }
    }
    throw new ApiError(errorMsg, response.status, data);
  }

  return data as T;
}
