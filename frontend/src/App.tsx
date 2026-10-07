import React, { useEffect, useState } from 'react';
import { apiRequest } from './api/client';
import { RadioStation } from './types';
import { Navbar } from './components/Navbar';
import { Globe } from './components/Globe';
import { Player } from './components/Player';
import { VibeBar } from './components/VibeBar';
import { LanguageFilterModal } from './components/LanguageFilterModal';
import { AuthModal } from './components/AuthModal';
import { SessionsModal } from './components/SessionsModal';
import { AdminModal } from './components/AdminModal';
import { FlightPlanner } from './components/FlightPlanner';
import { usePlayer } from './context/PlayerContext';
import { useFlight } from './context/FlightContext';

export const App: React.FC = () => {
  const { currentStation, skipNext, currentVibe, excludedLanguages } = usePlayer();
  const { isFlightMode, isPlannerOpen } = useFlight();

  const [stations, setStations] = useState<RadioStation[]>([]);

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [sessionsModalOpen, setSessionsModalOpen] = useState(false);
  const [adminModalOpen, setAdminModalOpen] = useState(false);
  const [langModalOpen, setLangModalOpen] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ vibe: currentVibe });
    if (excludedLanguages.length > 0) {
      params.set('exclude_languages', excludedLanguages.join(','));
    }
    apiRequest<RadioStation[]>(`/stations/vibe/stations?${params.toString()}`)
      .then((data) => setStations(data))
      .catch((err) => console.error('Failed to load stations', err));
  }, [currentVibe, excludedLanguages]);

  useEffect(() => {
    if (!currentStation && stations.length > 0) {
      skipNext();
    }
  }, [stations.length]);

  return (
    <div className="shell">
      <Navbar
        onOpenAuth={() => setAuthModalOpen(true)}
        onOpenSessions={() => setSessionsModalOpen(true)}
        onOpenAdmin={() => setAdminModalOpen(true)}
        onOpenLanguages={() => setLangModalOpen(true)}
      />

      <main className="stage">
        <Globe stations={stations} />
        {!isFlightMode && !isPlannerOpen && <VibeBar />}
        <FlightPlanner />
      </main>

      <Player onOpenAuth={() => setAuthModalOpen(true)} />

      <LanguageFilterModal isOpen={langModalOpen} onClose={() => setLangModalOpen(false)} />
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <SessionsModal isOpen={sessionsModalOpen} onClose={() => setSessionsModalOpen(false)} />
      <AdminModal
        isOpen={adminModalOpen}
        onClose={() => setAdminModalOpen(false)}
        onStationAdded={() => {}}
      />
    </div>
  );
};
