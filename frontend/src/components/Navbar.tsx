import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { usePlayer } from '../context/PlayerContext';
import { Shield, Smartphone, LogOut, User as UserIcon, Languages } from 'lucide-react';

interface NavbarProps {
  onOpenAuth: () => void;
  onOpenSessions: () => void;
  onOpenAdmin: () => void;
  onOpenLanguages: () => void;
}

/** UTC is what actually drives the terminator, so it is the clock on show. */
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
  const utc = useUtcClock();

  return (
    <header className="rail arrive">
      <div className="wordmark">
        <span className={isPlaying ? 'pulsing-indicator' : 'band-tick'} />
        <span>AROUND FM</span>
      </div>

      <div className="rail-right">
        <span className="rail-clock num">{utc}</span>

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
