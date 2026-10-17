import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiRequest, errorMessage, getAccessToken, refreshAccessToken, setAccessToken } from './client';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('apiRequest', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
    setAccessToken(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends bearer token and same-origin credentials', async () => {
    setAccessToken('tok');
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }));
    await expect(apiRequest('/users/me')).resolves.toEqual({ ok: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/users/me');
    expect(init.headers.Authorization).toBe('Bearer tok');
    expect(init.credentials).toBe('same-origin');
  });

  it('refreshes once on 401 and retries', async () => {
    setAccessToken('stale');
    fetchMock
      .mockResolvedValueOnce(json(401, { detail: 'expired' }))
      .mockResolvedValueOnce(json(200, { access_token: 'fresh' }))
      .mockResolvedValueOnce(json(200, { id: 1 }));
    await expect(apiRequest('/users/me')).resolves.toEqual({ id: 1 });
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/refresh');
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer fresh');
    expect(getAccessToken()).toBe('fresh');
  });

  it('emits auth-expired when refresh fails', async () => {
    const listener = vi.fn();
    window.addEventListener('auth-expired', listener);
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'x' })).mockResolvedValueOnce(json(401, {}));
    await expect(apiRequest('/users/me')).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener('auth-expired', listener);
  });

  it('does not retry login endpoints', async () => {
    fetchMock.mockResolvedValueOnce(json(401, { detail: 'Неверный логин или пароль' }));
    await expect(apiRequest('/auth/login', { method: 'POST' })).rejects.toThrow('Неверный логин или пароль');
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('shares a single in-flight refresh', async () => {
    let resolve: (r: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => (resolve = r)));
    const a = refreshAccessToken();
    const b = refreshAccessToken();
    resolve(json(200, { access_token: 'one' }));
    await expect(Promise.all([a, b])).resolves.toEqual(['one', 'one']);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('exposes status and payload on errors', async () => {
    fetchMock.mockResolvedValueOnce(json(409, { detail: 'Конфликт' }));
    const err = (await apiRequest('/x').catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe('Конфликт');
  });
});

describe('errorMessage', () => {
  it('formats validation arrays', () => {
    const data = {
      detail: [
        { loc: ['body', 'password'], msg: 'String should have at least 8 characters' },
        { loc: ['body', 'email'], msg: 'value is not a valid email address' },
      ],
    };
    expect(errorMessage(data, 'x')).toBe('password: Минимум 8 символов; email: Некорректный email');
  });

  it('falls back for unknown shapes', () => {
    expect(errorMessage('oops', 'fallback')).toBe('fallback');
    expect(errorMessage({ detail: { a: 1 } }, 'fallback')).toBe('fallback');
  });
});
