import React, { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { TelegramIcon } from './BrandIcons';
import '../styles/sheet.css';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const USERNAME_RE = /^[a-zA-Z0-9_-]+$/;

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { login, register, providers } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const validate = (): string | null => {
    if (!isRegister) return null;
    const name = username.trim();
    if (name.length < 3) return 'Имя пользователя короче 3 символов';
    if (!USERNAME_RE.test(name)) return 'Недопустимые символы в имени пользователя';
    if (password.length < 8) return 'Пароль короче 8 символов';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const invalid = validate();
    setError(invalid);
    if (invalid) return;
    setLoading(true);
    try {
      if (isRegister) {
        await register(email.trim(), username.trim(), password);
      } else {
        await login(username.trim(), password);
      }
      setPassword('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (name: string, pass: string) => {
    setIsRegister(false);
    setUsername(name);
    setPassword(pass);
    setError(null);
  };

  const botUsername = providers?.telegram.enabled ? providers.telegram.bot_username : null;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="auth-title">
        <button className="key sheet-close" onClick={onClose} aria-label="Закрыть">
          <X className="w-4 h-4" />
        </button>

        <span className="sheet-kicker">Аккаунт</span>
        <h2 id="auth-title" className="sheet-title">
          {isRegister ? 'Регистрация' : 'Вход'}
        </h2>
        <p className="sheet-sub">Избранное и сессии синхронизируются между устройствами</p>

        <form className="form" onSubmit={handleSubmit} noValidate>
          {isRegister && (
            <label className="field">
              <span className="field-label">Email</span>
              <input
                className="input"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
          )}
          <label className="field">
            <span className="field-label">{isRegister ? 'Имя пользователя' : 'Логин или email'}</span>
            <input
              className="input"
              type="text"
              required
              autoComplete="username"
              maxLength={isRegister ? 32 : 255}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            {isRegister && <span className="field-hint">3–32 символа: a-z, цифры, - и _</span>}
          </label>
          <label className="field">
            <span className="field-label">Пароль</span>
            <input
              className="input"
              type="password"
              required
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {isRegister && <span className="field-hint">Минимум 8 символов</span>}
          </label>

          {error && (
            <p className="message is-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" disabled={loading} className="btn-primary btn-wide">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : isRegister ? 'Создать аккаунт' : 'Войти'}
          </button>
        </form>

        {botUsername && (
          <>
            <div className="divider">или</div>
            <a
              className="btn-secondary btn-wide"
              href={`https://t.me/${botUsername}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <TelegramIcon className="w-4 h-4" />
              Открыть в Telegram
            </a>
          </>
        )}

        <div className="actions" style={{ marginTop: 18, justifyContent: 'space-between' }}>
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
          >
            {isRegister ? 'Уже есть аккаунт' : 'Создать аккаунт'}
          </button>
          {import.meta.env.DEV && (
            <span className="actions">
              <button type="button" className="link-btn" onClick={() => fillDemo('admin', 'Admin12345!')}>
                admin
              </button>
              <button type="button" className="link-btn" onClick={() => fillDemo('listener', 'User12345!')}>
                listener
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
