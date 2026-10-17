import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from './api/client';
import { RadioStation, StationPoint } from './types';
import { Navbar } from './components/Navbar';
import { Globe } from './components/Globe';
import { Player } from './components/Player';
import { VibeBar } from './components/VibeBar';
import { LanguageFilterModal } from './components/LanguageFilterModal';
import { AuthModal } from './components/AuthModal';
import { AccountModal } from './components/AccountModal';
import { Toast } from './components/Toast';
import { useAuth } from './context/AuthContext';
import { launchParams } from './services/launchParams';
import { AdminModal } from './components/AdminModal';
import { FlightPlanner } from './components/FlightPlanner';
import { FlightHud } from './components/FlightHud';
import { FlightSnapshots } from './components/FlightPhotos';
import { usePlayer } from './context/PlayerContext';
import { useFlight } from './context/FlightContext';

export const App: React.FC = () => {
  const { currentStation, skipNext, playStation, currentVibe, excludedLanguages } = usePlayer();
  const { notice, dismissNotice } = useAuth();
  const [toast, setToast] = useState<{ text: string; tone: 'success' | 'error' } | null>(null);
  const { isFlightMode, isPlannerOpen } = useFlight();

  const [stations, setStations] = useState<StationPoint[]>([]);

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [langModalOpen, setLangModalOpen] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ vibe: currentVibe });
    if (excludedLanguages.length > 0) {
      params.set('exclude_languages', excludedLanguages.join(','));
    }
    apiRequest<{ stations: [number, number, number][] }>(`/stations/vibe/map?${params.toString()}`)
      .then((data) =>
        setStations(data.stations.map(([id, latitude, longitude]) => ({ id, latitude, longitude }))),
      )
      .catch((err) => console.error('Failed to load stations', err));
  }, [currentVibe, excludedLanguages]);

  useEffect(() => {
    if (launchParams.stationId === null) return;
    apiRequest<RadioStation>(`/stations/${launchParams.stationId}`)
      .then(playStation)
      .catch(() => setToast({ text: 'Станция не найдена', tone: 'error' }));
  }, [playStation]);

  const autoStarted = useRef(false);
  useEffect(() => {
    if (autoStarted.current || currentStation || stations.length === 0) return;
    if (launchParams.stationId !== null) return;
    autoStarted.current = true;
    skipNext();
  }, [currentStation, stations.length, skipNext]);

  const closeAccount = useCallback(() => setAccountModalOpen(false), []);
  const visibleToast = toast ?? notice;
  const closeToast = useCallback(() => {
    setToast(null);
    dismissNotice();
  }, [dismissNotice]);

  return (
    <div className="shell">
      <Navbar
        onOpenAuth={() => setAuthModalOpen(true)}
        onOpenAccount={() => setAccountModalOpen(true)}
        onOpenAdmin={() => setAdminModalOpen(true)}
        onOpenLanguages={() => setLangModalOpen(true)}
      />

      <main className="stage">
        <Globe stations={stations} />
        {!isFlightMode && !isPlannerOpen && <VibeBar />}
        <FlightPlanner />
        <FlightHud />
        <FlightSnapshots />
      </main>

      <Player onOpenAuth={() => setAuthModalOpen(true)} />

      <LanguageFilterModal isOpen={langModalOpen} onClose={() => setLangModalOpen(false)} />
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <AccountModal isOpen={accountModalOpen} onClose={closeAccount} />
      {visibleToast && <Toast text={visibleToast.text} tone={visibleToast.tone} onClose={closeToast} />}
      <AdminModal
        isOpen={adminModalOpen}
        onClose={() => setAdminModalOpen(false)}
        onStationAdded={() => {}}
      />
    </div>
  );
};
