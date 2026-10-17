import React, { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { usePlayer } from '../context/PlayerContext';
import { apiRequest } from '../api/client';
import { languageLabel } from '../utils/languages';
import '../styles/sheet.css';

interface LanguageOption {
  code: string;
  count: number;
}

interface LanguageFilterModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LanguageFilterModal: React.FC<LanguageFilterModalProps> = ({ isOpen, onClose }) => {
  const { excludedLanguages, toggleLanguageExclusion, setExcludedLanguages } = usePlayer();
  const [languages, setLanguages] = useState<LanguageOption[]>([]);
  const [search, setSearch] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setFailed(false);
    apiRequest<LanguageOption[]>('/stations/vibe/languages')
      .then(setLanguages)
      .catch(() => setFailed(true));
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return languages;
    return languages.filter(
      (l) => languageLabel(l.code).toLowerCase().includes(q) || l.code.includes(q),
    );
  }, [languages, search]);

  if (!isOpen) return null;

  const muted = excludedLanguages.length;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet is-wide langs" role="dialog" aria-modal="true" aria-labelledby="langs-title">
        <button className="key sheet-close" onClick={onClose} aria-label="Закрыть">
          <X className="w-4 h-4" />
        </button>

        <h2 id="langs-title" className="sheet-title">
          Языки в эфире
        </h2>

        <input
          className="input langs-search"
          type="search"
          placeholder="Найти язык"
          aria-label="Найти язык"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        {failed ? (
          <p className="message is-error langs-empty">Список языков не загрузился. Закройте окно и откройте снова.</p>
        ) : visible.length === 0 && languages.length > 0 ? (
          <p className="langs-empty">Такого языка в каталоге нет</p>
        ) : (
          <ul className="langs-list no-scrollbar">
            {visible.map((lang) => {
              const isOn = !excludedLanguages.includes(lang.code);
              return (
                <li key={lang.code}>
                  <button
                    type="button"
                    className={`lang${isOn ? ' is-on' : ''}`}
                    aria-pressed={isOn}
                    onClick={() => toggleLanguageExclusion(lang.code)}
                  >
                    <span className="band-tick" />
                    <span className="lang-name">{languageLabel(lang.code)}</span>
                    <span className="lang-count num">{lang.count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="langs-foot">
          {muted > 0 ? (
            <button type="button" className="link-btn" onClick={() => setExcludedLanguages([])}>
              Включить все
            </button>
          ) : (
            <span className="langs-status">Звучат все языки</span>
          )}
          <button type="button" className="btn-primary" onClick={onClose}>
            Готово
          </button>
        </div>
      </div>
    </div>
  );
};
