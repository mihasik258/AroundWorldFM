import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiRequest, refreshAccessToken, setAccessToken } from '../api/client';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  login: (loginText: string, passwordText: string) => Promise<void>;
  register: (email: string, username: string, passwordText: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const clearAuth = () => {
    setAccessToken(null);
    setUser(null);
    setToken(null);
  };

  const fetchCurrentUser = async () => {
    try {
      const userData = await apiRequest<User>('/users/me');
      setUser(userData);
    } catch (err) {
      clearAuth();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // The access token is kept in memory and is gone after a page reload.
    // The refresh cookie survives, so restore the session silently.
    (async () => {
      const fresh = await refreshAccessToken();
      if (fresh) {
        setToken(fresh);
        await fetchCurrentUser();
      } else {
        setIsLoading(false);
      }
    })();

    window.addEventListener('auth-expired', clearAuth);
    return () => window.removeEventListener('auth-expired', clearAuth);
  }, []);

  const login = async (loginText: string, passwordText: string) => {
    const data = await apiRequest<{ access_token: string; user_id: number; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login: loginText, password: passwordText }),
    });

    // The refresh token arrives as an httpOnly cookie and never reaches JS
    setAccessToken(data.access_token);
    setToken(data.access_token);
    await fetchCurrentUser();
  };

  const register = async (email: string, username: string, passwordText: string) => {
    await apiRequest('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, username, password: passwordText }),
    });
    // Auto login after registration
    await login(username, passwordText);
  };

  const logout = async () => {
    // Revoke the session on the server and delete the refresh cookie; without
    // this the cookie would silently log the user back in on the next reload.
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
    } catch {
      // Still clear local state even if the server is unreachable
    }
    clearAuth();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isAdmin: user?.role === 'admin',
        isLoading,
        login,
        register,
        logout,
        refreshUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
