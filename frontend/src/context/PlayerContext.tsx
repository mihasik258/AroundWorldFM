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
  resetRotationTimer: () => void;
  skipNext: (vibeOverride?: string) => Promise<void>;
  isAutoRotateEnabled: boolean;
  setIsAutoRotateEnabled: (enabled: boolean) => void;
}

const fadeAudio = (
  audio: HTMLAudioElement,
  fromVol: number,
  toVol: number,
  durationMs: number,
  onComplete?: () => void
): (() => void) => {
  const start = Date.now();
  let cancelled = false;

  const initial = Math.max(0, Math.min(1, fromVol));
  const target = Math.max(0, Math.min(1, toVol));
  audio.volume = initial;

  const timer = setInterval(() => {
    if (cancelled) {
      clearInterval(timer);
      return;
    }
    const elapsed = Date.now() - start;
    const progress = Math.min(1, elapsed / Math.max(1, durationMs));
    const eased = 0.5 * (1 - Math.cos(progress * Math.PI));
    const v = initial + (target - initial) * eased;
    audio.volume = Math.max(0, Math.min(1, v));

    if (progress >= 1) {
      clearInterval(timer);
      audio.volume = target;
      if (onComplete) onComplete();
    }
  }, 25);

  return () => {
    cancelled = true;
    clearInterval(timer);
  };
};

const PlayerContext = createContext<PlayerContextType | undefined>(undefined);

export const PlayerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [currentStation, setCurrentStation] = useState<RadioStation | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolumeState] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('aroundfm_volume');
      if (saved) return Number(saved);
    } catch {}
    return 0.45;
  });
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

  const audioARef = useRef<HTMLAudioElement | null>(null);
  const audioBRef = useRef<HTMLAudioElement | null>(null);
  const activeSlotRef = useRef<'A' | 'B'>('A');
  const cancelFadeARef = useRef<(() => void) | null>(null);
  const cancelFadeBRef = useRef<(() => void) | null>(null);
  const transitionTokenRef = useRef<number>(0);

  const currentStationRef = useRef<RadioStation | null>(null);
  const recentIdsRef = useRef<number[]>([]);
  const skipNextRef = useRef<() => void>(() => {});
  const isSkippingRef = useRef<boolean>(false);
  const volumeRef = useRef<number>(volume);

  useEffect(() => {
    volumeRef.current = volume;
  }, [volume]);

  const cancelFade = (slot: 'A' | 'B') => {
    if (slot === 'A' && cancelFadeARef.current) {
      cancelFadeARef.current();
      cancelFadeARef.current = null;
    } else if (slot === 'B' && cancelFadeBRef.current) {
      cancelFadeBRef.current();
      cancelFadeBRef.current = null;
    }
  };

  useEffect(() => {
    const audioA = new Audio();
    const audioB = new Audio();
    audioA.preload = 'none';
    audioB.preload = 'none';
    audioA.volume = volumeRef.current;
    audioB.volume = 0;

    let stallTimeoutA: any = null;
    let stallTimeoutB: any = null;

    const setupStallWatchdog = (
      audio: HTMLAudioElement,
      slot: 'A' | 'B',
      getTimeout: () => any,
      setTimeoutVal: (t: any) => void
    ) => {
      audio.addEventListener('waiting', () => {
        if (activeSlotRef.current !== slot) return;
        setIsLoading(true);
        const cur = getTimeout();
        if (cur) clearTimeout(cur);
        setTimeoutVal(
          setTimeout(() => {
            const st = currentStationRef.current;
            if (st && activeSlotRef.current === slot && audio.readyState < 2) {
              console.warn(`Stream stalled: ${st.name}`);
              setIsLoading(false);
              audio.play().catch(() => {});
            }
          }, 7000)
        );
      });

      audio.addEventListener('playing', () => {
        const cur = getTimeout();
        if (cur) clearTimeout(cur);
      });
    };

    setupStallWatchdog(audioA, 'A', () => stallTimeoutA, (t) => { stallTimeoutA = t; });
    setupStallWatchdog(audioB, 'B', () => stallTimeoutB, (t) => { stallTimeoutB = t; });

    audioARef.current = audioA;
    audioBRef.current = audioB;

    return () => {
      if (stallTimeoutA) clearTimeout(stallTimeoutA);
      if (stallTimeoutB) clearTimeout(stallTimeoutB);
      cancelFade('A');
      cancelFade('B');
      audioA.pause();
      audioA.src = '';
      audioB.pause();
      audioB.src = '';
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
    const audioA = audioARef.current;
    const audioB = audioBRef.current;
    if (!audioA || !audioB) return;

    setError(null);
    setIsLoading(true);
    setCurrentStation(station);
    currentStationRef.current = station;

    recentIdsRef.current = [station.id, ...recentIdsRef.current.filter((id) => id !== station.id)].slice(0, 15);
    setRotationSecondsLeft(ROTATION_SECONDS);

    const token = ++transitionTokenRef.current;

    const curSlot = activeSlotRef.current;
    const nextSlot: 'A' | 'B' = curSlot === 'A' ? 'B' : 'A';
    const outAudio = curSlot === 'A' ? audioA : audioB;
    const inAudio = nextSlot === 'A' ? audioA : audioB;

    cancelFade(curSlot);
    if (!outAudio.paused) {
      outAudio.volume = volumeRef.current;
    }

    cancelFade(nextSlot);
    inAudio.pause();
    inAudio.volume = 0;
    inAudio.src = station.stream_url;

    let hasHandledSuccess = false;

    const executeCrossfade = () => {
      if (transitionTokenRef.current !== token || hasHandledSuccess) return;
      hasHandledSuccess = true;

      setIsPlaying(true);
      setIsLoading(false);
      setError(null);
      activeSlotRef.current = nextSlot;

      cancelFade(curSlot);
      const cancelOut = fadeAudio(outAudio, outAudio.volume, 0, 320, () => {
        outAudio.pause();
        outAudio.src = '';
      });
      if (curSlot === 'A') cancelFadeARef.current = cancelOut;
      else cancelFadeBRef.current = cancelOut;

      cancelFade(nextSlot);
      const targetVol = volumeRef.current;
      const cancelIn = fadeAudio(inAudio, 0, targetVol, 320);
      if (nextSlot === 'A') cancelFadeARef.current = cancelIn;
      else cancelFadeBRef.current = cancelIn;
    };

    const handleFailure = () => {
      if (transitionTokenRef.current !== token) return;
      console.warn(`Stream failed: ${station.name}`);
      setIsLoading(false);
      setError(`Не удалось подключиться к «${station.name}»`);
      cancelFade(nextSlot);
      inAudio.pause();
      inAudio.src = '';
      if (!outAudio.paused) {
        outAudio.volume = volumeRef.current;
        setIsPlaying(true);
      }
    };

    const onError = () => {
      inAudio.removeEventListener('playing', onPlaying);
      inAudio.removeEventListener('error', onError);
      if (transitionTokenRef.current !== token) return;

      if (!inAudio.src.includes(`/api/v1/stations/${station.id}/stream`)) {
        console.warn(`Direct stream failed: ${station.name}`);
        inAudio.src = `/api/v1/stations/${station.id}/stream`;
        inAudio.addEventListener('playing', onPlaying, { once: true });
        inAudio.addEventListener('error', onError, { once: true });
        inAudio.play().catch((e) => {
          if (e.name === 'AbortError' || e.name === 'NotAllowedError') return;
          handleFailure();
        });
        return;
      }
      handleFailure();
    };

    const onPlaying = () => {
      inAudio.removeEventListener('playing', onPlaying);
      inAudio.removeEventListener('error', onError);
      executeCrossfade();
    };

    inAudio.addEventListener('playing', onPlaying, { once: true });
    inAudio.addEventListener('error', onError, { once: true });

    inAudio.play().catch((err) => {
      if (err.name === 'AbortError') return;
      if (err.name === 'NotAllowedError') {
        setIsLoading(false);
        setIsPlaying(false);
        return;
      }
      if (!inAudio.src.includes(`/api/v1/stations/${station.id}/stream`)) onError();
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
    const curSlot = activeSlotRef.current;
    const activeAudio = curSlot === 'A' ? audioARef.current : audioBRef.current;
    if (!activeAudio) return;

    if (!currentStationRef.current) {
      skipNext();
      return;
    }

    if (isPlaying) {
      cancelFade(curSlot);
      const cancel = fadeAudio(activeAudio, activeAudio.volume, 0, 300, () => {
        activeAudio.pause();
        setIsPlaying(false);
      });
      if (curSlot === 'A') cancelFadeARef.current = cancel;
      else cancelFadeBRef.current = cancel;
    } else {
      cancelFade(curSlot);
      setIsLoading(true);
      activeAudio.volume = 0;
      activeAudio
        .play()
        .then(() => {
          setIsPlaying(true);
          setIsLoading(false);
          const cancel = fadeAudio(activeAudio, 0, volumeRef.current, 350);
          if (curSlot === 'A') cancelFadeARef.current = cancel;
          else cancelFadeBRef.current = cancel;
        })
        .catch(() => {
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
    volumeRef.current = vol;
    const curSlot = activeSlotRef.current;
    const activeAudio = curSlot === 'A' ? audioARef.current : audioBRef.current;
    if (activeAudio) {
      activeAudio.volume = Math.max(0, Math.min(1, vol));
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

  const resetRotationTimer = useCallback(() => {
    setRotationSecondsLeft(ROTATION_SECONDS);
  }, []);

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
        resetRotationTimer,
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
