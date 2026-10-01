import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { apiRequest } from '../api/client';
import { RadioStation } from '../types';
import { useAuth } from './AuthContext';

const ROTATION_SECONDS = 300;

interface PlayerContextType {
  currentStation: RadioStation | null;
  isPlaying: boolean;
  isLoading: boolean;
  error: string | null;
  volume: number;
  playStation: (station: RadioStation) => void;
  togglePlay: () => void;
  playRandom: (genres?: string, languages?: string) => Promise<void>;
  setVolume: (vol: number) => void;
  favorites: RadioStation[];
  isFavorite: (stationId: number) => boolean;
  toggleFavorite: (station: RadioStation) => Promise<void>;

  currentVibe: string;
  setVibe: (vibe: string) => void;
  excludedLanguages: string[];
  setExcludedLanguages: (langs: string[]) => void;
  toggleLanguageExclusion: (lang: string) => void;
  rotationSecondsLeft: number;
  skipNext: (vibeOverride?: string) => Promise<void>;
  isAutoRotateEnabled: boolean;
  setIsAutoRotateEnabled: (enabled: boolean) => void;
}

const PlayerContext = createContext<PlayerContextType | undefined>(undefined);

export const PlayerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [currentStation, setCurrentStation] = useState<RadioStation | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolumeState] = useState<number>(0.8);
  const [favorites, setFavorites] = useState<RadioStation[]>([]);

  const [currentVibe, setCurrentVibeState] = useState<string>(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlVibe = params.get('vibe');
      if (urlVibe) return urlVibe;
    } catch {}
    return localStorage.getItem('aroundfm_vibe') || 'focus';
  });

  const [excludedLanguages, setExcludedLanguagesState] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('aroundfm_excluded_languages');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [rotationSecondsLeft, setRotationSecondsLeft] = useState<number>(ROTATION_SECONDS);
  const [isAutoRotateEnabled, setIsAutoRotateEnabled] = useState<boolean>(true);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const currentStationRef = useRef<RadioStation | null>(null);
  const recentIdsRef = useRef<number[]>([]);
  const skipNextRef = useRef<() => void>(() => {});
  const isSkippingRef = useRef<boolean>(false);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = 'none';
    audio.volume = volume;

    let stallTimeout: any = null;

    audio.addEventListener('playing', () => {
      if (stallTimeout) clearTimeout(stallTimeout);
      setIsPlaying(true);
      setIsLoading(false);
      setError(null);
    });

    audio.addEventListener('waiting', () => {
      setIsLoading(true);
      if (stallTimeout) clearTimeout(stallTimeout);
      stallTimeout = setTimeout(() => {
        const st = currentStationRef.current;
        if (st && audio.readyState < 2) {
          console.warn(`Stream stalled: ${st.name}`);
          skipNextRef.current();
        }
      }, 7000);
    });

    audio.addEventListener('error', () => {
      if (stallTimeout) clearTimeout(stallTimeout);

      if (audio.error && audio.error.code === 1) {
        return;
      }

      const st = currentStationRef.current;
      if (st && !audio.src.includes(`/api/v1/stations/${st.id}/stream`)) {
        console.warn(`Direct stream failed: ${st.name}`);
        setIsLoading(true);
        audio.src = `/api/v1/stations/${st.id}/stream`;
        audio.play().catch((e) => {
          if (e.name === 'AbortError' || e.name === 'NotAllowedError') return;
          console.warn(`Proxy stream failed: ${st.name}`);
          skipNextRef.current();
        });
        return;
      }

      console.warn(`Stream failed: ${st?.name}`);
      skipNextRef.current();
    });

    audioRef.current = audio;

    return () => {
      if (stallTimeout) clearTimeout(stallTimeout);
      audio.pause();
      audio.src = '';
    };
  }, []);

  const fetchFavorites = async () => {
    if (!isAuthenticated) {
      setFavorites([]);
      return;
    }
    try {
      const data = await apiRequest<RadioStation[]>('/stations/favorites/my');
      setFavorites(data);
    } catch (e) {
      console.error('Failed to load favorites', e);
    }
  };

  useEffect(() => {
    fetchFavorites();
  }, [isAuthenticated]);

  const playStation = useCallback((station: RadioStation) => {
    if (!audioRef.current) return;
    setError(null);
    setIsLoading(true);
    setCurrentStation(station);
    currentStationRef.current = station;

    recentIdsRef.current = [station.id, ...recentIdsRef.current.filter((id) => id !== station.id)].slice(0, 15);

    const audio = audioRef.current;
    audio.pause();
    setRotationSecondsLeft(ROTATION_SECONDS);

    audio.src = station.stream_url;
    audio.play().catch((err) => {
      if (err.name === 'AbortError') return;
      if (err.name === 'NotAllowedError') {
        setIsLoading(false);
        setIsPlaying(false);
        return;
      }
      console.warn('Direct play failed', err);
      audio.src = `/api/v1/stations/${station.id}/stream`;
      audio.play().catch((e) => {
        if (e.name === 'AbortError' || e.name === 'NotAllowedError') {
          setIsLoading(false);
          setIsPlaying(false);
          return;
        }
        setIsLoading(false);
        setIsPlaying(false);
        setError('Поток недоступен');
      });
    });
  }, []);

  const skipNext = useCallback(async (vibeOverride?: string) => {
    if (isSkippingRef.current) return;
    isSkippingRef.current = true;
    setIsLoading(true);
    setError(null);

    const vibe = vibeOverride || currentVibe;
    const params = new URLSearchParams();
    params.set('vibe', vibe);

    if (excludedLanguages.length > 0) {
      params.set('exclude_languages', excludedLanguages.join(','));
    }
    if (recentIdsRef.current.length > 0) {
      params.set('exclude_ids', recentIdsRef.current.join(','));
    }

    try {
      const station = await apiRequest<RadioStation>(`/stations/vibe/next?${params.toString()}`);
      playStation(station);
    } catch (err: any) {
      console.error('Failed to load station', err);
      setError(err.message || 'Нет станций');
      setIsLoading(false);
    } finally {
      isSkippingRef.current = false;
    }
  }, [currentVibe, excludedLanguages, playStation]);

  skipNextRef.current = skipNext;

  const setVibe = (vibe: string) => {
    setCurrentVibeState(vibe);
    localStorage.setItem('aroundfm_vibe', vibe);
    skipNext(vibe);
  };

  const setExcludedLanguages = (langs: string[]) => {
    setExcludedLanguagesState(langs);
    localStorage.setItem('aroundfm_excluded_languages', JSON.stringify(langs));
    if (currentStation?.language && langs.map((l) => l.toLowerCase()).includes(currentStation.language.toLowerCase())) {
      skipNext();
    }
  };

  const toggleLanguageExclusion = (lang: string) => {
    const clean = lang.toLowerCase();
    const updated = excludedLanguages.includes(clean)
      ? excludedLanguages.filter((l) => l !== clean)
      : [...excludedLanguages, clean];
    setExcludedLanguages(updated);
  };

  useEffect(() => {
    if (!isPlaying || !isAutoRotateEnabled) return;

    const interval = setInterval(() => {
      setRotationSecondsLeft((prev) => {
        if (prev <= 1) {
          skipNext();
          return ROTATION_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isPlaying, isAutoRotateEnabled, skipNext]);

  const togglePlay = () => {
    if (!audioRef.current) return;

    if (!currentStation) {
      skipNext();
      return;
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      audioRef.current.play().then(() => {
        setIsPlaying(true);
        setIsLoading(false);
      }).catch(() => {
        setIsLoading(false);
        setIsPlaying(false);
      });
    }
  };

  const playRandom = async (genres?: string, languages?: string) => {
    try {
      setIsLoading(true);
      const params = new URLSearchParams();
      if (genres && genres !== 'any') params.set('genres', genres);
      if (languages) params.set('languages', languages);

      const qs = params.toString() ? `?${params.toString()}` : '';
      const station = await apiRequest<RadioStation>(`/stations/random${qs}`);
      playStation(station);
    } catch (err: any) {
      setError(err.message || 'Нет станций');
      setIsLoading(false);
    }
  };

  const setVolume = (vol: number) => {
    setVolumeState(vol);
    if (audioRef.current) {
      audioRef.current.volume = vol;
    }
  };

  const isFavorite = (stationId: number) => {
    return favorites.some((f) => f.id === stationId);
  };

  const toggleFavorite = async (station: RadioStation) => {
    if (!isAuthenticated) return;

    const exists = isFavorite(station.id);
    try {
      if (exists) {
        await apiRequest(`/stations/favorites/${station.id}`, { method: 'DELETE' });
        setFavorites((prev) => prev.filter((f) => f.id !== station.id));
      } else {
        await apiRequest(`/stations/favorites/${station.id}`, { method: 'POST' });
        setFavorites((prev) => [station, ...prev]);
      }
    } catch (e) {
      console.error('Failed to toggle favorite', e);
    }
  };

  return (
    <PlayerContext.Provider
      value={{
        currentStation,
        isPlaying,
        isLoading,
        error,
        volume,
        playStation,
        togglePlay,
        playRandom,
        setVolume,
        favorites,
        isFavorite,
        toggleFavorite,
        currentVibe,
        setVibe,
        excludedLanguages,
        setExcludedLanguages,
        toggleLanguageExclusion,
        rotationSecondsLeft,
        skipNext,
        isAutoRotateEnabled,
        setIsAutoRotateEnabled,
      }}
    >
      {children}
    </PlayerContext.Provider>
  );
};

export const usePlayer = () => {
  const context = useContext(PlayerContext);
  if (!context) {
    throw new Error('usePlayer must be used within PlayerProvider');
  }
  return context;
};
