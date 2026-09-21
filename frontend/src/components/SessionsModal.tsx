import React, { useEffect, useState } from 'react';
import { apiRequest } from '../api/client';
import { UserSession } from '../types';
import { X, Smartphone, Trash2, ShieldCheck, KeyRound, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

interface SessionsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SessionsModal: React.FC<SessionsModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'sessions' | 'password'>('sessions');
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Password change form
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [pwdLoading, setPwdLoading] = useState(false);

  const loadSessions = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await apiRequest<UserSession[]>('/auth/sessions');
      setSessions(data);
    } catch (err: any) {
      setMessage({ text: err.message || 'Ошибка загрузки сессий', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen]);

  const handleRevoke = async (sessionId: number) => {
    setActionLoading(true);
    try {
      await apiRequest(`/auth/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setMessage({ text: 'Сессия успешно завершена', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.message || 'Не удалось отозвать сессию', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevokeAll = async () => {
    if (!confirm('Вы уверены, что хотите завершить сеансы на всех устройствах?')) return;
    setActionLoading(true);
    try {
      await apiRequest('/auth/sessions/revoke-all', { method: 'POST' });
      setMessage({ text: 'Все сессии успешно отозваны', type: 'success' });
      loadSessions();
    } catch (err: any) {
      setMessage({ text: err.message || 'Ошибка отзыва всех сессий', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdLoading(true);
    setMessage(null);

    try {
      const res = await apiRequest('/users/me/change-password', {
        method: 'POST',
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      setMessage({ text: res.message || 'Пароль успешно изменен', type: 'success' });
      setOldPassword('');
      setNewPassword('');
    } catch (err: any) {
      setMessage({ text: err.message || 'Ошибка смены пароля', type: 'error' });
    } finally {
      setPwdLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="glass-panel rounded-3xl p-6 sm:p-8 w-full max-w-lg relative shadow-2xl border border-slate-700/80 max-h-[90vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 text-slate-400 hover:text-white p-1 rounded-lg bg-slate-800/60"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Безопасность аккаунта</h2>
            <p className="text-xs text-slate-400">Управление устройствами и паролем</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
          <button
            onClick={() => { setActiveTab('sessions'); setMessage(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'sessions'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Smartphone className="w-3.5 h-3.5" />
            <span>Активные сеансы ({sessions.length})</span>
          </button>

          <button
            onClick={() => { setActiveTab('password'); setMessage(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-2 ${
              activeTab === 'password'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <KeyRound className="w-3.5 h-3.5" />
            <span>Смена пароля</span>
          </button>
        </div>

        {/* Status Message Alert */}
        {message && (
          <div
            className={`mb-4 p-3 rounded-xl text-xs flex items-center gap-2 ${
              message.type === 'success'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
        )}

        {/* Tab 1: Sessions List */}
        {activeTab === 'sessions' && (
          <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-3">
            {loading ? (
              <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-xs">Загрузка сессий...</span>
              </div>
            ) : sessions.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">Нет активных сессий</div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className="p-3.5 rounded-xl glass-card flex items-center justify-between gap-3 border border-slate-800"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span className="text-xs font-semibold text-white truncate">
                        {s.user_agent ? s.user_agent.split(' ')[0] : 'Неизвестное устройство'}
                      </span>
                      {s.ip_address && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                          {s.ip_address}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate max-w-xs">
                      {s.user_agent || 'Браузерная сессия'}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">
                      Активен: {new Date(s.last_used_at).toLocaleString()}
                    </div>
                  </div>

                  <button
                    onClick={() => handleRevoke(s.id)}
                    disabled={actionLoading}
                    className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Завершить сессию"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}

            {sessions.length > 1 && (
              <div className="mt-4 pt-3 border-t border-slate-800">
                <button
                  onClick={handleRevokeAll}
                  disabled={actionLoading}
                  className="btn-secondary !w-full justify-center !py-2.5 text-xs text-rose-300 border-rose-500/30 hover:bg-rose-500/10"
                >
                  Выйти со всех остальных устройств
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Password Change */}
        {activeTab === 'password' && (
          <form onSubmit={handlePasswordChange} className="flex flex-col gap-3.5 py-2">
            <div>
              <label className="text-xs font-semibold text-slate-300 mb-1 block">Текущий пароль</label>
              <input
                type="password"
                required
                placeholder="••••••••"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 mb-1 block">Новый пароль (мин. 8 символов)</label>
              <input
                type="password"
                required
                minLength={8}
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={pwdLoading}
              className="btn-primary !w-full justify-center !py-3 mt-3 text-sm"
            >
              {pwdLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Сменить пароль'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
