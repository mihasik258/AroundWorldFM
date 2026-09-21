import React, { useEffect, useState } from 'react';
import { apiRequest } from '../api/client';
import { SystemStats } from '../types';
import { X, Shield, Activity, PlusCircle, Radio, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStationAdded: () => void;
}

export const AdminModal: React.FC<AdminModalProps> = ({
  isOpen,
  onClose,
  onStationAdded,
}) => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [checkingStreams, setCheckingStreams] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // New station state
  const [name, setName] = useState('');
  const [streamUrl, setStreamUrl] = useState('');
  const [country, setCountry] = useState('');
  const [language, setLanguage] = useState('');
  const [tags, setTags] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [addLoading, setAddLoading] = useState(false);

  const fetchStats = async () => {
    setLoadingStats(true);
    try {
      const data = await apiRequest<SystemStats>('/admin/stats');
      setStats(data);
    } catch (err: any) {
      setMessage({ text: err.message || 'Ошибка загрузки статистики', type: 'error' });
    } finally {
      setLoadingStats(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStats();
    }
  }, [isOpen]);

  const handleTriggerHealthCheck = async () => {
    setCheckingStreams(true);
    setMessage(null);
    try {
      const res = await apiRequest('/admin/trigger-stream-check', { method: 'POST' });
      setMessage({ text: res.message || 'Проверка стримов завершена', type: 'success' });
      fetchStats();
    } catch (err: any) {
      setMessage({ text: err.message || 'Ошибка аудита потоков', type: 'error' });
    } finally {
      setCheckingStreams(false);
    }
  };

  const handleCreateStation = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddLoading(true);
    setMessage(null);

    try {
      await apiRequest('/admin/stations', {
        method: 'POST',
        body: JSON.stringify({
          name,
          stream_url: streamUrl,
          country,
          language: language || null,
          tags: tags.toLowerCase(),
          latitude: latitude ? parseFloat(latitude) : null,
          longitude: longitude ? parseFloat(longitude) : null,
        }),
      });

      setMessage({ text: `Станция '${name}' успешно добавлена!`, type: 'success' });
      setName('');
      setStreamUrl('');
      setCountry('');
      setLanguage('');
      setTags('');
      setLatitude('');
      setLongitude('');
      fetchStats();
      onStationAdded();
    } catch (err: any) {
      setMessage({ text: err.message || 'Не удалось создать станцию', type: 'error' });
    } finally {
      setAddLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="glass-panel rounded-3xl p-6 sm:p-8 w-full max-w-xl relative shadow-2xl border border-slate-700/80 max-h-[90vh] flex flex-col">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-5 top-5 text-slate-400 hover:text-white p-1 rounded-lg bg-slate-800/60"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Панель администратора (RBAC)</h2>
            <p className="text-xs text-slate-400">Системные показатели и управление радиостанциями</p>
          </div>
        </div>

        {/* Status Message */}
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

        <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-6">
          {/* Stats Grid */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Технико-экономические показатели (ТЭП)
              </h3>
              <button
                onClick={handleTriggerHealthCheck}
                disabled={checkingStreams}
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-medium"
              >
                {checkingStreams ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Activity className="w-3.5 h-3.5" />}
                <span>Проверить потоки</span>
              </button>
            </div>

            {loadingStats || !stats ? (
              <div className="h-20 glass-card rounded-2xl flex items-center justify-center text-xs text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin mr-2" /> Загрузка показателей...
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                <div className="p-3 rounded-xl glass-card">
                  <div className="text-lg font-black text-white">{stats.total_stations}</div>
                  <div className="text-[10px] text-slate-400 font-medium mt-0.5">Всего станций</div>
                </div>
                <div className="p-3 rounded-xl glass-card">
                  <div className="text-lg font-black text-emerald-400">{stats.active_stations}</div>
                  <div className="text-[10px] text-slate-400 font-medium mt-0.5">Активные потоки</div>
                </div>
                <div className="p-3 rounded-xl glass-card">
                  <div className="text-lg font-black text-indigo-400">
                    {stats.stream_availability_percentage}%
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium mt-0.5">Доступность (ТЭП 1)</div>
                </div>
                <div className="p-3 rounded-xl glass-card">
                  <div className="text-lg font-black text-amber-400">{stats.active_sessions}</div>
                  <div className="text-[10px] text-slate-400 font-medium mt-0.5">Сессий онлайн</div>
                </div>
              </div>
            )}
          </div>

          {/* Add Station Form */}
          <div className="pt-4 border-t border-slate-800">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-1.5">
              <PlusCircle className="w-4 h-4 text-indigo-400" />
              <span>Добавить радиостанцию</span>
            </h3>

            <form onSubmit={handleCreateStation} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Название станции *</label>
                <input
                  type="text"
                  required
                  placeholder="Radio Paradise"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">URL потока (HTTPS) *</label>
                <input
                  type="url"
                  required
                  placeholder="https://stream.example.com/audio.mp3"
                  value={streamUrl}
                  onChange={(e) => setStreamUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Страна *</label>
                <input
                  type="text"
                  required
                  placeholder="France"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Язык вещания</label>
                <input
                  type="text"
                  placeholder="french"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Широта (Latitude)</label>
                <input
                  type="number"
                  step="any"
                  placeholder="48.8566"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Долгота (Longitude)</label>
                <input
                  type="number"
                  step="any"
                  placeholder="2.3522"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="text-[11px] font-semibold text-slate-400 mb-1 block">Теги/Жанры (через запятую)</label>
                <input
                  type="text"
                  placeholder="jazz, chillout, eclectic"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="sm:col-span-2 mt-2">
                <button
                  type="submit"
                  disabled={addLoading}
                  className="btn-primary !w-full justify-center !py-2.5 text-xs"
                >
                  {addLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radio className="w-4 h-4" />}
                  <span>Добавить станцию в систему</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
