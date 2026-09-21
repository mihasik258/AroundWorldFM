import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiRequest } from '../api/client';
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
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchCurrentUser = async () => {
    try {
      const userData = await apiRequest<User>('/users/me');
      setUser(userData);
    } catch (err) {
      setUser(null);
      setToken(null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchCurrentUser();
    } else {
      setIsLoading(false);
    }

    const handleExpired = () => {
      setUser(null);
      setToken(null);
    };

    window.addEventListener('auth-expired', handleExpired);
    return () => window.removeEventListener('auth-expired', handleExpired);
  }, [token]);

  const login = async (loginText: string, passwordText: string) => {
    const data = await apiRequest<{ access_token: string; refresh_token: string; user_id: number; role: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login: loginText, password: passwordText }),
    });

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
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
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    setToken(null);
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
