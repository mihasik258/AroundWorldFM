import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { X, Lock, Mail, User, AlertCircle, Loader2 } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanUsername = username.trim();
    const cleanEmail = email.trim();

    if (isRegister) {
      if (cleanUsername.length < 3) {
        setError('Имя пользователя должно быть не короче 3 символов');
        return;
      }
      if (!/^[a-zA-Z0-9_-]+$/.test(cleanUsername)) {
        setError('Имя пользователя может содержать только латинские буквы (a-z), цифры, _ и - (без пробелов и кириллицы)');
        return;
      }
      if (password.length < 8) {
        setError('Пароль должен содержать минимум 8 символов');
        return;
      }
    }

    setLoading(true);

    try {
      if (isRegister) {
        await register(cleanEmail, cleanUsername, password);
      } else {
        await login(cleanUsername, password);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Ошибка аутентификации');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (userType: 'admin' | 'listener') => {
    setIsRegister(false);
    if (userType === 'admin') {
      setUsername('admin');
      setPassword('Admin12345!');
    } else {
      setUsername('listener');
      setPassword('User12345!');
    }
    setError(null);
  };

  return (
    <div className="modal-backdrop">
      <div className="glass-panel rounded-3xl p-6 sm:p-8 w-full max-w-md relative shadow-2xl border border-slate-700/80 animate-in fade-in zoom-in-95 duration-200">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 text-slate-400 hover:text-white p-1 rounded-lg bg-slate-800/60"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="text-center mb-6">
          <h2 className="text-2xl font-black text-white tracking-tight">
            {isRegister ? 'Регистрация' : 'Вход в аккаунт'}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {isRegister ? 'Создайте профиль для сохранения любимых радиостанций' : 'Войдите для синхронизации избранного и сессий'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span className="leading-relaxed break-words">{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
          {isRegister && (
            <div>
              <label className="text-xs font-semibold text-slate-300 mb-1 block">Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-300 mb-1 block">
              {isRegister ? 'Имя пользователя (латиница)' : 'Логин или Email'}
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                placeholder={isRegister ? 'ivan_music' : 'admin или listener'}
                value={username}
                minLength={isRegister ? 3 : 1}
                maxLength={32}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            {isRegister && (
              <p className="text-[11px] text-slate-400 mt-1 pl-0.5">
                3–32 символа: латиница (a-z), цифры, дефис и <code className="text-slate-300">_</code>
              </p>
            )}
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 mb-1 block">Пароль</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                minLength={isRegister ? 8 : 1}
                maxLength={128}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>
            {isRegister && (
              <p className="text-[11px] text-slate-400 mt-1 pl-0.5">
                Минимум 8 символов
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary !w-full justify-center !py-3 mt-2 text-sm"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </form>

        {/* Demo Accounts Quick-Fill */}
        <div className="mt-5 pt-4 border-t border-slate-800 text-center">
          <div className="text-[11px] text-slate-400 mb-2">Демо-вход в один клик:</div>
          <div className="flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => fillDemo('admin')}
              className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-medium"
            >
              🛡️ Admin
            </button>
            <button
              type="button"
              onClick={() => fillDemo('listener')}
              className="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-medium"
            >
              🎧 Listener
            </button>
          </div>
        </div>

        {/* Toggle Mode */}
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium underline"
          >
            {isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
          </button>
        </div>
      </div>
    </div>
  );
};
