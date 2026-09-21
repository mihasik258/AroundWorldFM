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

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${BASE_URL}${endpoint}`;
  let response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle Token Refresh on 401
  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          localStorage.setItem('access_token', data.access_token);
          if (data.refresh_token) {
            localStorage.setItem('refresh_token', data.refresh_token);
          }

          // Retry original request with fresh token
          headers['Authorization'] = `Bearer ${data.access_token}`;
          response = await fetch(url, { ...options, headers });
        } else {
          // Token refresh failed -> clear auth
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.dispatchEvent(new Event('auth-expired'));
        }
      } catch (e) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.dispatchEvent(new Event('auth-expired'));
      }
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
