import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { usePlayer } from '../context/PlayerContext';
import { Shield, Smartphone, LogOut, User as UserIcon, Languages, Plane } from 'lucide-react';
import { useFlight } from '../context/FlightContext';

interface NavbarProps {
  onOpenAuth: () => void;
  onOpenSessions: () => void;
  onOpenAdmin: () => void;
  onOpenLanguages: () => void;
}

const useUtcClock = () => {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 30000);
    return () => clearInterval(id);
  }, []);
  const hh = time.getUTCHours().toString().padStart(2, '0');
  const mm = time.getUTCMinutes().toString().padStart(2, '0');
  return `${hh}:${mm} UTC`;
};

export const Navbar: React.FC<NavbarProps> = ({
  onOpenAuth,
  onOpenSessions,
  onOpenAdmin,
  onOpenLanguages,
}) => {
  const { user, isAuthenticated, isAdmin, logout } = useAuth();
  const { isPlaying, excludedLanguages } = usePlayer();
  const { isFlightMode, isPlannerOpen, openPlanner, closePlanner, exitFlight } = useFlight();
  const utc = useUtcClock();

  const handleToggleFlight = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isFlightMode) {
      exitFlight();
    } else if (isPlannerOpen) {
      closePlanner();
    } else {
      openPlanner();
    }
  };
  const isSwitchOn = isFlightMode || isPlannerOpen;

  return (
    <header className="rail arrive">
      <div className="wordmark">
        <span className={isPlaying ? 'pulsing-indicator' : 'band-tick'} />
        <span>AROUND FM</span>
      </div>

      <div className="rail-right">
        <span className="rail-clock num">{utc}</span>

        <div className="flex items-center px-2.5 py-1 rounded-full bg-[#0a1322]/90 border border-slate-800 shadow-inner">
          <button
            type="button"
            role="switch"
            aria-checked={isSwitchOn}
            onClick={handleToggleFlight}
            className="flex items-center gap-2 group cursor-pointer focus:outline-none"
            title={isSwitchOn ? 'Тумблер: выключить авиарежим' : 'Тумблер: включить авиарежим'}
          >
            <Plane
              className={`w-3.5 h-3.5 transition-all duration-300 ${
                isSwitchOn
                  ? 'text-cyan-400 rotate-45 scale-110 drop-shadow-[0_0_6px_rgba(34,211,238,0.8)]'
                  : 'text-slate-500 rotate-0 group-hover:text-slate-400'
              }`}
            />

            <div
              className={`relative inline-flex items-center h-5 w-9 shrink-0 rounded-full border transition-all duration-300 ${
                isSwitchOn
                  ? 'bg-cyan-950/90 border-cyan-400/80 shadow-[0_0_10px_rgba(6,182,212,0.4)]'
                  : 'bg-slate-900 border-slate-700/80 group-hover:border-slate-600'
              }`}
            >
              <span
                className={`pointer-events-none inline-flex items-center justify-center h-3.5 w-3.5 rounded-full transition-transform duration-200 ease-out shadow-sm ${
                  isSwitchOn
                    ? 'translate-x-[18px] bg-gradient-to-b from-cyan-200 via-cyan-400 to-cyan-600 border border-cyan-200 shadow-[0_0_6px_#38bdf8]'
                    : 'translate-x-0.5 bg-gradient-to-b from-slate-200 to-slate-400 border border-slate-400'
                }`}
              >
                <span
                  className={`w-1 h-1 rounded-full ${
                    isSwitchOn ? 'bg-white shadow-[0_0_3px_#fff]' : 'bg-slate-600'
                  }`}
                />
              </span>
            </div>

            <span
              className={`text-[11px] font-mono font-bold tracking-wider uppercase transition-colors select-none ${
                isSwitchOn ? 'text-cyan-300' : 'text-slate-400 group-hover:text-slate-300'
              }`}
            >
              Авиа
            </span>
          </button>
        </div>

        <button className="ghost" onClick={onOpenLanguages} title="Исключить языки">
          <Languages className="w-4 h-4" />
          <span className="hidden sm:inline">Языки</span>
          {excludedLanguages.length > 0 && (
            <span className="ghost-count">{excludedLanguages.length}</span>
          )}
        </button>

        {isAuthenticated && user ? (
          <>
            {isAdmin && (
              <button className="ghost" onClick={onOpenAdmin} title="Панель администратора">
                <Shield className="w-4 h-4" />
              </button>
            )}

            <button className="ghost" onClick={onOpenSessions} title="Активные сессии">
              <Smartphone className="w-4 h-4" />
            </button>

            <button className="ghost" onClick={logout} title={`Выйти — ${user.username}`}>
              <LogOut className="w-4 h-4" />
            </button>
          </>
        ) : (
          <button className="ghost" onClick={onOpenAuth}>
            <UserIcon className="w-4 h-4" />
            <span className="hidden sm:inline">Войти</span>
          </button>
        )}
      </div>
    </header>
  );
};
