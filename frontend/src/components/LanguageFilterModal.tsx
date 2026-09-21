import React, { useEffect, useState } from 'react';
import { usePlayer } from '../context/PlayerContext';
import { apiRequest } from '../api/client';
import { X, Search, Check, ShieldAlert, RotateCcw } from 'lucide-react';

interface LanguageOption {
  code: string;
  name: string;
  count: number;
}

interface LanguageFilterModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const FLAG_MAP: Record<string, string> = {
  english: '🇬🇧',
  french: '🇫🇷',
  spanish: '🇪🇸',
  german: '🇩🇪',
  russian: '🇷🇺',
  italian: '🇮🇹',
  instrumental: '🎵',
  dutch: '🇳🇱',
  portuguese: '🇧🇷',
  polish: '🇵🇱',
  korean: '🇰🇷',
  japanese: '🇯🇵',
  hindi: '🇮🇳',
  turkish: '🇹🇷',
  greek: '🇬🇷',
  arabic: '🇪🇬',
};

export const LanguageFilterModal: React.FC<LanguageFilterModalProps> = ({ isOpen, onClose }) => {
  const { excludedLanguages, toggleLanguageExclusion, setExcludedLanguages } = usePlayer();
  const [languages, setLanguages] = useState<LanguageOption[]>([]);
  const [search, setSearch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen) return;
    setIsLoading(true);
    apiRequest<LanguageOption[]>('/stations/vibe/languages')
      .then((data) => setLanguages(data))
      .catch((err) => console.error('Failed to load vibe languages', err))
      .finally(() => setIsLoading(false));
  }, [isOpen]);

  if (!isOpen) return null;

  const filtered = languages.filter((l) =>
    l.name.toLowerCase().includes(search.toLowerCase()) ||
    l.code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-800/40">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Исключить языки из эфира</h3>
              <p className="text-xs text-slate-400">
                Отметьте языки, которые вы <span className="text-rose-400 font-medium">не хотите</span> слышать в потоке
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search & Actions */}
        <div className="p-4 border-b border-white/5 bg-slate-900/50 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по языку..."
              className="w-full bg-slate-800/80 border border-white/10 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-400"
            />
          </div>
          {excludedLanguages.length > 0 && (
            <button
              onClick={() => setExcludedLanguages([])}
              className="flex items-center gap-1.5 px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors border border-white/5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Сбросить ({excludedLanguages.length})</span>
            </button>
          )}
        </div>

        {/* Language Grid */}
        <div className="p-4 overflow-y-auto flex-1 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {isLoading ? (
            <div className="col-span-2 py-8 text-center text-xs text-slate-500">Загрузка языков...</div>
          ) : filtered.length === 0 ? (
            <div className="col-span-2 py-8 text-center text-xs text-slate-500">Языки не найдены</div>
          ) : (
            filtered.map((lang) => {
              const isExcluded = excludedLanguages.includes(lang.code);
              const flag = FLAG_MAP[lang.code] || '🌐';

              return (
                <button
                  key={lang.code}
                  onClick={() => toggleLanguageExclusion(lang.code)}
                  className={`flex items-center justify-between p-3 rounded-xl border text-left transition-all ${
                    isExcluded
                      ? 'bg-rose-500/15 border-rose-500/40 text-rose-200'
                      : 'bg-slate-800/40 border-white/5 hover:bg-slate-800/80 text-slate-300'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">{flag}</span>
                    <div>
                      <div className="text-xs font-medium text-white">{lang.name}</div>
                      <div className="text-[10px] text-slate-400">{lang.count} станций</div>
                    </div>
                  </div>

                  <div
                    className={`w-5 h-5 rounded-md flex items-center justify-center border transition-all ${
                      isExcluded
                        ? 'bg-rose-500 border-rose-400 text-white'
                        : 'border-white/20 bg-slate-800'
                    }`}
                  >
                    {isExcluded && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/10 bg-slate-800/40 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            {excludedLanguages.length === 0 ? (
              <span className="text-emerald-400">Включены все языки планеты</span>
            ) : (
              <span>Исключено: <b className="text-rose-400">{excludedLanguages.length}</b> яз.</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25"
          >
            Готово
          </button>
        </div>
      </div>
    </div>
  );
};
