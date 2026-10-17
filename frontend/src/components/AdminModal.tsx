import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { apiRequest } from '../api/client';
import { SystemStats } from '../types';
import { KNOWN_LANGUAGES, languageLabel } from '../utils/languages';
import '../styles/sheet.css';

interface AdminModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStationAdded: () => void;
}

type Feedback = { text: string; tone: 'success' | 'error' } | null;

const EMPTY_FORM = {
  name: '',
  streamUrl: '',
  country: '',
  language: '',
  tags: '',
  latitude: '',
  longitude: '',
};

const errorText = (err: unknown, fallback: string) => (err instanceof Error && err.message) || fallback;

export const AdminModal: React.FC<AdminModalProps> = ({ isOpen, onClose, onStationAdded }) => {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const fetchStats = useCallback(async () => {
    try {
      setStats(await apiRequest<SystemStats>('/admin/stats'));
    } catch (err) {
      setFeedback({ text: errorText(err, 'Статистика не загрузилась'), tone: 'error' });
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setFeedback(null);
    fetchStats();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose, fetchStats]);

  if (!isOpen) return null;

  const field = (key: keyof typeof EMPTY_FORM) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value }),
  });

  const checkStreams = async () => {
    setChecking(true);
    setFeedback(null);
    try {
      await apiRequest('/admin/trigger-stream-check', { method: 'POST' });
      setFeedback({ text: 'Проверка потоков запущена, статистика обновится через несколько минут', tone: 'success' });
    } catch (err) {
      setFeedback({ text: errorText(err, 'Проверка не запустилась'), tone: 'error' });
    } finally {
      setChecking(false);
    }
  };

  const createStation = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);
    try {
      await apiRequest('/admin/stations', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name.trim(),
          stream_url: form.streamUrl.trim(),
          country: form.country.trim(),
          language: form.language.trim() || null,
          tags: form.tags,
          latitude: form.latitude ? Number(form.latitude) : null,
          longitude: form.longitude ? Number(form.longitude) : null,
        }),
      });
      setFeedback({ text: `Станция «${form.name.trim()}» добавлена`, tone: 'success' });
      setForm(EMPTY_FORM);
      fetchStats();
      onStationAdded();
    } catch (err) {
      setFeedback({ text: errorText(err, 'Станция не добавлена'), tone: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet is-wide" role="dialog" aria-modal="true" aria-labelledby="admin-title">
        <button className="key sheet-close" onClick={onClose} aria-label="Закрыть">
          <X className="w-4 h-4" />
        </button>

        <h2 id="admin-title" className="sheet-title">
          Администрирование
        </h2>

        {stats ? (
          <>
            <dl className="meters">
              <div className="meter">
                <dt>Станций</dt>
                <dd className="num">{stats.total_stations}</dd>
              </div>
              <div className="meter">
                <dt>В эфире</dt>
                <dd className="num">{stats.active_stations}</dd>
              </div>
              <div className="meter">
                <dt>Пользователей</dt>
                <dd className="num">{stats.total_users}</dd>
              </div>
              <div className="meter">
                <dt>Сессий</dt>
                <dd className="num">{stats.active_sessions}</dd>
              </div>
            </dl>

            <div className="availability">
              <div className="availability-head">
                <span>
                  Доступность потоков <span className="num">{stats.stream_availability_percentage}%</span>
                </span>
                <button className="link-btn" onClick={checkStreams} disabled={checking}>
                  {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Проверить потоки'}
                </button>
              </div>
              <div className="availability-track">
                <div
                  className="availability-fill"
                  style={{ width: `${Math.min(100, stats.stream_availability_percentage)}%` }}
                />
              </div>
            </div>
          </>
        ) : (
          <p className="sheet-sub" style={{ marginTop: 18 }}>
            <Loader2 className="w-4 h-4 animate-spin" />
          </p>
        )}

        {feedback && (
          <p className={`message${feedback.tone === 'error' ? ' is-error' : ''}`} role="status" style={{ marginTop: 16 }}>
            {feedback.text}
          </p>
        )}

        <section className="sheet-section">
          <h3 className="sheet-section-title">Новая станция</h3>
          <form className="form-grid" onSubmit={createStation}>
            <label className="field is-wide">
              <span className="field-label">Название</span>
              <input className="input" required maxLength={255} {...field('name')} />
            </label>
            <label className="field is-wide">
              <span className="field-label">Адрес потока</span>
              <input className="input" type="url" required placeholder="https://" {...field('streamUrl')} />
            </label>
            <label className="field">
              <span className="field-label">Страна</span>
              <input className="input" required maxLength={100} {...field('country')} />
            </label>
            <label className="field">
              <span className="field-label">Язык</span>
              <input className="input" list="admin-languages" maxLength={100} {...field('language')} />
              <datalist id="admin-languages">
                {KNOWN_LANGUAGES.map((code) => (
                  <option key={code} value={code}>
                    {languageLabel(code)}
                  </option>
                ))}
              </datalist>
            </label>
            <label className="field">
              <span className="field-label">Широта</span>
              <input className="input num" type="number" step="any" min={-90} max={90} {...field('latitude')} />
            </label>
            <label className="field">
              <span className="field-label">Долгота</span>
              <input className="input num" type="number" step="any" min={-180} max={180} {...field('longitude')} />
            </label>
            <label className="field is-wide">
              <span className="field-label">Жанры через запятую</span>
              <input className="input" placeholder="jazz, chillout" {...field('tags')} />
            </label>
            <div className="actions is-wide">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Добавить станцию'}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
};
