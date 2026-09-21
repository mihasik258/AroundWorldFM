import React from 'react';
import { usePlayer } from '../context/PlayerContext';

// A vibe behaves like a band on a receiver, so it is presented as one: a name
// and a lamp, no icon and no colour of its own. The planet carries the colour.
const VIBES = [
  { id: 'focus', label: 'Фокус' },
  { id: 'night_drive', label: 'Драйв' },
  { id: 'coffee', label: 'Утренний чай' },
  { id: 'party', label: 'Вечеринка' },
  { id: 'sunset', label: 'Закат' },
  { id: 'world_odyssey', label: 'Мировое турне' },
];

export const VibeBar: React.FC = () => {
  const { currentVibe, setVibe } = usePlayer();

  return (
    <nav className="bands no-scrollbar arrive arrive-3" aria-label="Настроение">
      {VIBES.map((vibe) => {
        const isActive = currentVibe === vibe.id;
        return (
          <button
            key={vibe.id}
            onClick={() => {
              setVibe(vibe.id);
            }}
            className={`band${isActive ? ' is-on' : ''}`}
            aria-pressed={isActive}
          >
            <span className="band-tick" />
            <span>{vibe.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
