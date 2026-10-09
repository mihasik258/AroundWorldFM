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

        <button
          type="button"
          role="switch"
          aria-checked={isSwitchOn}
          onClick={handleToggleFlight}
          className={`ghost${isSwitchOn ? ' is-on' : ''}`}
          title={isSwitchOn ? 'Выключить авиарежим' : 'Включить авиарежим'}
        >
          <Plane className="w-4 h-4" />
          <span className="hidden sm:inline">Авиа</span>
        </button>

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
