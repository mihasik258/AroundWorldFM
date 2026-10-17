import React, { useCallback, useEffect, useState } from 'react';
import { KeyRound, Loader2, Monitor, X } from 'lucide-react';
import { apiRequest } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AuthProviderId, UserSession } from '../types';
import { openTelegramLink } from '../services/telegram';
import { TelegramIcon } from './BrandIcons';
import '../styles/sheet.css';

interface AccountModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'profile' | 'sessions';
type Feedback = { text: string; tone: 'success' | 'error' } | null;

const PROVIDER_LABELS: Record<AuthProviderId, string> = {
  password: 'Пароль',
  telegram: 'Telegram',
};

const errorText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback);

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export const AccountModal: React.FC<AccountModalProps> = ({ isOpen, onClose }) => {
  const { user, providers, refreshUser, logout } = useAuth();
  const [tab, setTab] = useState<Tab>('profile');
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmName, setConfirmName] = useState('');
  const [deleting, setDeleting] = useState(false);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await apiRequest<UserSession[]>('/auth/sessions'));
    } catch (err) {
      setFeedback({ text: errorText(err, 'Ошибка загрузки'), tone: 'error' });
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setFeedback(null);
    refreshUser();
    loadSessions();
    const onFocus = () => refreshUser();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('focus', onFocus);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('keydown', onKey);
    };
  }, [isOpen, onClose, refreshUser, loadSessions]);

  if (!isOpen || !user) return null;

  const identity = (provider: AuthProviderId) => user.identities.find((i) => i.provider === provider);
  const hasPassword = !!identity('password');

  const run = async (key: string, action: () => Promise<string | void>) => {
    setBusy(key);
    setFeedback(null);
    try {
      const text = await action();
      if (text) setFeedback({ text, tone: 'success' });
    } catch (err) {
      setFeedback({ text: errorText(err, 'Ошибка'), tone: 'error' });
    } finally {
      setBusy(null);
    }
  };

  const unlink = (provider: AuthProviderId) =>
    run(`unlink-${provider}`, async () => {
      await apiRequest(`/users/me/identities/${provider}`, { method: 'DELETE' });
      await refreshUser();
      return `${PROVIDER_LABELS[provider]} отвязан`;
    });

  const linkTelegram = () =>
    run('link-telegram', async () => {
      const { url } = await apiRequest<{ url: string }>('/users/me/identities/telegram/link', {
        method: 'POST',
      });
      openTelegramLink(url);
      return 'Подтвердите привязку в Telegram и вернитесь сюда';
    });

  const savePassword = (e: React.FormEvent) => {
    e.preventDefault();
    run('password', async () => {
      await apiRequest('/users/me/change-password', {
        method: 'POST',
        body: JSON.stringify({ old_password: hasPassword ? oldPassword : null, new_password: newPassword }),
      });
      setOldPassword('');
      setNewPassword('');
      await logout();
      onClose();
    });
  };

  const revokeSession = (session: UserSession) =>
    run(`session-${session.id}`, async () => {
      if (session.is_current) {
        await logout();
        onClose();
        return;
      }
      await apiRequest(`/auth/sessions/${session.id}`, { method: 'DELETE' });
      setSessions((prev) => prev.filter((s) => s.id !== session.id));
      return 'Сессия завершена';
    });

  const revokeOthers = () =>
    run('revoke-all', async () => {
      const res = await apiRequest<{ message: string }>('/auth/sessions/revoke-all', { method: 'POST' });
      await loadSessions();
      return res.message;
    });

  const deleteAccount = () =>
    run('delete', async () => {
      await apiRequest('/users/me', { method: 'DELETE', body: JSON.stringify({ confirm_username: confirmName }) });
      await logout();
      onClose();
    });

  const telegramEnabled = !!providers?.telegram.enabled && !!providers.telegram.bot_username;

  const telegramRow = () => {
    const linked = identity('telegram');
    if (!linked && !telegramEnabled) return null;
    return (
      <li className="row">
        <TelegramIcon className="w-4 h-4 row-icon" />
        <span className="row-main">
          <span className="row-title">Telegram</span>
          <span className="row-sub">{linked ? linked.display_name ?? 'Подключён' : 'Не подключён'}</span>
        </span>
        {linked ? (
          <button className="link-btn is-danger" disabled={!!busy} onClick={() => unlink('telegram')}>
            Отвязать
          </button>
        ) : (
          <button className="link-btn" disabled={!!busy} onClick={linkTelegram}>
            {busy === 'link-telegram' ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Подключить'}
          </button>
        )}
      </li>
    );
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet is-wide" role="dialog" aria-modal="true" aria-labelledby="account-title">
        <button className="key sheet-close" onClick={onClose} aria-label="Закрыть">
          <X className="w-4 h-4" />
        </button>

        <span className="sheet-kicker">{user.role === 'admin' ? 'Администратор' : 'Аккаунт'}</span>
        <h2 id="account-title" className="sheet-title">
          {user.username}
        </h2>
        {user.email && <p className="sheet-sub">{user.email}</p>}

        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'profile'} className={`tab${tab === 'profile' ? ' is-on' : ''}`} onClick={() => setTab('profile')}>
            Способы входа
          </button>
          <button role="tab" aria-selected={tab === 'sessions'} className={`tab${tab === 'sessions' ? ' is-on' : ''}`} onClick={() => setTab('sessions')}>
            Сессии <span className="num">{sessions.length}</span>
          </button>
        </div>

        {feedback && (
          <p className={`message${feedback.tone === 'error' ? ' is-error' : ''}`} role="status" style={{ marginTop: 14 }}>
            {feedback.text}
          </p>
        )}

        {tab === 'profile' ? (
          <>
            <ul className="rows" style={{ marginTop: 8 }}>
              <li className="row">
                <KeyRound className="w-4 h-4 row-icon" />
                <span className="row-main">
                  <span className="row-title">Пароль</span>
                  <span className="row-sub">{hasPassword ? 'Задан' : 'Не задан'}</span>
                </span>
              </li>
              {telegramRow()}
            </ul>

            <section className="sheet-section">
              <h3 className="sheet-section-title">{hasPassword ? 'Сменить пароль' : 'Задать пароль'}</h3>
              <form className="form" style={{ marginTop: 0 }} onSubmit={savePassword}>
                {hasPassword && (
                  <label className="field">
                    <span className="field-label">Текущий пароль</span>
                    <input className="input" type="password" autoComplete="current-password" required value={oldPassword} onChange={(e) => setOldPassword(e.target.value)} />
                  </label>
                )}
                <label className="field">
                  <span className="field-label">Новый пароль</span>
                  <input className="input" type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
                  <span className="field-hint">После сохранения все устройства выйдут из аккаунта</span>
                </label>
                <div className="actions">
                  <button className="btn-primary" type="submit" disabled={!!busy || newPassword.length < 8}>
                    {busy === 'password' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Сохранить'}
                  </button>
                </div>
              </form>
            </section>

            <section className="sheet-section">
              {deleting ? (
                <div className="form" style={{ marginTop: 0 }}>
                  <label className="field">
                    <span className="field-label">
                      Введите <span className="num">{user.username}</span>, чтобы удалить аккаунт навсегда
                    </span>
                    <input className="input" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} />
                  </label>
                  <div className="actions">
                    <button className="btn-secondary" disabled={confirmName !== user.username || !!busy} onClick={deleteAccount}>
                      Удалить аккаунт
                    </button>
                    <button className="link-btn" onClick={() => setDeleting(false)}>
                      Отмена
                    </button>
                  </div>
                </div>
              ) : (
                <button className="link-btn is-danger" onClick={() => setDeleting(true)}>
                  Удалить аккаунт
                </button>
              )}
            </section>
          </>
        ) : (
          <>
            <ul className="rows" style={{ marginTop: 8 }}>
              {sessions.map((session) => (
                <li className="row" key={session.id}>
                  <Monitor className="w-4 h-4 row-icon" />
                  <span className="row-main">
                    <span className="row-title">{session.device_name ?? 'Устройство'}</span>
                    <span className="row-sub">
                      {session.ip_address ?? '—'} · {formatDate(session.last_used_at)}
                    </span>
                  </span>
                  {session.is_current && <span className="row-tag">это устройство</span>}
                  <button className="link-btn is-danger" disabled={!!busy} onClick={() => revokeSession(session)}>
                    {session.is_current ? 'Выйти' : 'Завершить'}
                  </button>
                </li>
              ))}
            </ul>
            {sessions.length > 1 && (
              <div className="actions" style={{ marginTop: 14 }}>
                <button className="btn-secondary" disabled={!!busy} onClick={revokeOthers}>
                  Завершить остальные
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
