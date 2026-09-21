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
import { usePlayer } from './context/PlayerContext';

export const App: React.FC = () => {
  const { currentStation, skipNext, currentVibe, excludedLanguages } = usePlayer();

  // Stations of the current vibe, drawn as pins on the globe. Vibe membership
  // is decided server-side (it matches on tags, not the mostly-empty `vibes`
  // column), so the globe has to ask for the set rather than filter locally.
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
      .catch((err) => console.error('Failed to load stations for globe', err));
  }, [currentVibe, excludedLanguages]);

  // Tune the first station of the saved vibe once the catalogue is in
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

      {/* The planet, edge to edge, with the band rail resting over its left
          margin on wide screens. */}
      <main className="stage">
        <Globe stations={stations} />
        <VibeBar />
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
