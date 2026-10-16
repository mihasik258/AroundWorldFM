import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiRequest, refreshAccessToken, setAccessToken } from '../api/client';
import { AuthProviders, User } from '../types';
import { loadTelegramWebApp } from '../services/telegram';
import { clearLaunchParams } from '../services/launchParams';

interface TokenPayload {
  access_token: string;
}

export interface Notice {
  text: string;
  tone: 'success' | 'error';
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  providers: AuthProviders | null;
  notice: Notice | null;
  dismissNotice: () => void;
  login: (loginText: string, passwordText: string) => Promise<void>;
  register: (email: string, username: string, passwordText: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const DISABLED_PROVIDERS: AuthProviders = {
  telegram: { enabled: false, bot_username: null },
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [providers, setProviders] = useState<AuthProviders | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const clearAuth = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  const fetchCurrentUser = useCallback(async () => {
    try {
      setUser(await apiRequest<User>('/users/me'));
    } catch {
      clearAuth();
    }
  }, [clearAuth]);

  const acceptToken = useCallback(
    async (data: TokenPayload) => {
      setAccessToken(data.access_token);
      await fetchCurrentUser();
    },
    [fetchCurrentUser],
  );

  useEffect(() => {
    let cancelled = false;

    (async () => {
      apiRequest<AuthProviders>('/auth/providers')
        .then((p) => !cancelled && setProviders(p))
        .catch(() => !cancelled && setProviders(DISABLED_PROVIDERS));

      const fresh = await refreshAccessToken();
      if (fresh) {
        await fetchCurrentUser();
      } else {
        const webApp = await loadTelegramWebApp();
        if (webApp) {
          try {
            const data = await apiRequest<TokenPayload>('/auth/telegram', {
              method: 'POST',
              body: JSON.stringify({ init_data: webApp.initData }),
            });
            await acceptToken(data);
          } catch {
            clearAuth();
          }
        }
      }

      if (!cancelled) setIsLoading(false);
    })();

    window.addEventListener('auth-expired', clearAuth);
    return () => {
      cancelled = true;
      window.removeEventListener('auth-expired', clearAuth);
    };
  }, [acceptToken, clearAuth, fetchCurrentUser]);

  useEffect(() => {
    if (!isLoading) clearLaunchParams();
  }, [isLoading]);

  const login = useCallback(
    async (loginText: string, passwordText: string) => {
      const data = await apiRequest<TokenPayload>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ login: loginText, password: passwordText }),
      });
      await acceptToken(data);
    },
    [acceptToken],
  );

  const register = useCallback(
    async (email: string, username: string, passwordText: string) => {
      await apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, username, password: passwordText }),
      });
      await login(username, passwordText);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } catch {
      setNotice({ text: 'Сессия завершена локально', tone: 'error' });
    }
    clearAuth();
  }, [clearAuth]);

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isAuthenticated: !!user,
      isAdmin: user?.role === 'admin',
      isLoading,
      providers,
      notice,
      dismissNotice: () => setNotice(null),
      login,
      register,
      logout,
      refreshUser: fetchCurrentUser,
    }),
    [user, isLoading, providers, notice, login, register, logout, fetchCurrentUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
