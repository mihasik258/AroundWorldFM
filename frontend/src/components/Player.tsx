import React, { useEffect, useState, useMemo } from 'react';
import { usePlayer } from '../context/PlayerContext';
import { useAuth } from '../context/AuthContext';
import { apiRequest } from '../api/client';
import {
  Play,
  Pause,
  SkipForward,
  Heart,
  Volume2,
  VolumeX,
  Loader2,
} from 'lucide-react';

interface PlayerProps {
  onOpenAuth: () => void;
}

const ROTATION_SECONDS = 300;

export const Player: React.FC<PlayerProps> = ({ onOpenAuth }) => {
  const {
    currentStation,
    isPlaying,
    isLoading,
    error,
    volume,
    togglePlay,
    setVolume,
    isFavorite,
    toggleFavorite,
    rotationSecondsLeft,
    skipNext,
  } = usePlayer();

  const { isAuthenticated } = useAuth();

  const [weather, setWeather] = useState<{ temp: number; condition: string } | null>(null);

  const [nowPlaying, setNowPlaying] = useState<{
    has_track: boolean;
    raw_title: string | null;
    artist: string | null;
    title: string | null;
    spotify_url: string | null;
  } | null>(null);

  // Local time where the station transmits, from its longitude
  const localTimeInfo = useMemo(() => {
    if (!currentStation || currentStation.longitude == null) return null;

    const offsetHours = Math.round(currentStation.longitude / 15);
    const now = new Date();
    const utcTime = now.getTime() + now.getTimezoneOffset() * 60000;
    const cityDate = new Date(utcTime + offsetHours * 3600000);

    const hours = cityDate.getHours();
    const minutes = cityDate.getMinutes().toString().padStart(2, '0');

    let period = 'вечер';
    if (hours < 6 || hours >= 21) period = 'ночь';
    else if (hours < 12) period = 'утро';
    else if (hours < 18) period = 'день';

    return { time: `${hours.toString().padStart(2, '0')}:${minutes}`, period };
  }, [currentStation]);

  const coords = useMemo(() => {
    const lat = currentStation?.latitude;
    const lon = currentStation?.longitude;
    if (lat == null || lon == null) return null;
    return `${Math.abs(lat).toFixed(1)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(1)}°${lon >= 0 ? 'E' : 'W'}`;
  }, [currentStation?.latitude, currentStation?.longitude]);

  useEffect(() => {
    if (!currentStation?.latitude || !currentStation?.longitude) {
      setWeather(null);
      return;
    }

    const lat = currentStation.latitude.toFixed(2);
    const lon = currentStation.longitude.toFixed(2);

    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code`)
      .then((res) => res.json())
      .then((data) => {
        if (data?.current) {
          const code = data.current.weather_code;
          let condition = 'ясно';
          if (code >= 1 && code <= 3) condition = 'облачно';
          else if (code >= 51 && code <= 67) condition = 'дождь';
          else if (code >= 71 && code <= 77) condition = 'снег';
          else if (code >= 95) condition = 'гроза';

          setWeather({ temp: Math.round(data.current.temperature_2m), condition });
        }
      })
      .catch(() => setWeather(null));
  }, [currentStation?.id, currentStation?.latitude, currentStation?.longitude]);

  useEffect(() => {
    if (!currentStation?.id) {
      setNowPlaying(null);
      return;
    }

    let isMounted = true;
    const fetchNowPlaying = () => {
      apiRequest<any>(`/stations/${currentStation.id}/now-playing`)
        .then((data: any) => {
          if (isMounted) setNowPlaying(data);
        })
        .catch(() => {});
    };

    fetchNowPlaying();
    const interval = setInterval(fetchNowPlaying, 18000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [currentStation?.id]);

  const handleFavoriteClick = () => {
    if (!isAuthenticated) {
      onOpenAuth();
      return;
    }
    if (currentStation) toggleFavorite(currentStation);
  };

  const isFav = currentStation ? isFavorite(currentStation.id) : false;

  const minutes = Math.floor(rotationSecondsLeft / 60);
  const seconds = rotationSecondsLeft % 60;
  const timerStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  const timerPercent = (rotationSecondsLeft / ROTATION_SECONDS) * 100;

  if (!currentStation) {
    return (
      <section className="console arrive arrive-2">
        <div className="rotation-track" />
        <div className="empty">
          <p className="empty-text">
            Выберите настроение — станция найдётся сама и сменится через пять минут.
          </p>
          <button className="start" onClick={() => skipNext()}>
            Включить
          </button>
        </div>
      </section>
    );
  }

  const statusLabel = isLoading ? 'Настройка' : isPlaying ? 'В эфире' : 'Пауза';

  return (
    <section className="console arrive arrive-2">
      {/* The divider between planet and panel is the five-minute timer. */}
      <div className="rotation-track">
        <div className="rotation-fill" style={{ width: `${timerPercent}%` }} />
      </div>

      <div className="console-head">
        <span className={`status${isPlaying ? ' is-live' : ''}`}>
          <span className="status-dot" />
          {statusLabel}
        </span>

        <span className="next-in">
          следующая<span className="num">{timerStr}</span>
        </span>
      </div>

      <h1 className="station-name">{currentStation.name}</h1>

      <div className="meta">
        <span className="meta-item">{currentStation.country}</span>

        {coords && (
          <>
            <span className="meta-rule hidden sm:block" />
            <span className="meta-item num hidden sm:inline-flex">{coords}</span>
          </>
        )}

        {localTimeInfo && (
          <>
            <span className="meta-rule" />
            <span className="meta-item">
              <span className="num">{localTimeInfo.time}</span>
              {localTimeInfo.period}
            </span>
          </>
        )}

        {weather && (
          <>
            <span className="meta-rule" />
            <span className="meta-item">
              <span className="num">{weather.temp > 0 ? `+${weather.temp}` : weather.temp}°</span>
              {weather.condition}
            </span>
          </>
        )}

        {currentStation.language && (
          <>
            <span className="meta-rule" />
            <span className="meta-item">{currentStation.language}</span>
          </>
        )}
      </div>

      {nowPlaying?.has_track && nowPlaying.title && (
        <div className="track">
          <span className="track-title">
            {nowPlaying.artist ? `${nowPlaying.artist} — ${nowPlaying.title}` : nowPlaying.title}
          </span>
          {nowPlaying.spotify_url && (
            <a
              className="track-link"
              href={nowPlaying.spotify_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Найти в Spotify
            </a>
          )}
        </div>
      )}

      {error && (
        <div className="alert">
          <span>{error}</span>
          <button onClick={() => skipNext()}>Взять другую станцию</button>
        </div>
      )}

      <div className="transport">
        <div className="transport-left">
          <button
            className="key key-play"
            onClick={togglePlay}
            disabled={isLoading}
            title={isPlaying ? 'Пауза' : 'Слушать'}
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : isPlaying ? (
              <Pause className="w-5 h-5" />
            ) : (
              <Play className="w-5 h-5 ml-0.5" />
            )}
          </button>

          <button className="key" onClick={() => skipNext()} title="Следующая станция">
            <SkipForward className="w-5 h-5" />
          </button>

          <button
            className={`key${isFav ? ' is-on' : ''}`}
            onClick={handleFavoriteClick}
            title={isAuthenticated ? (isFav ? 'В избранном' : 'В избранное') : 'Войдите, чтобы сохранять'}
          >
            <Heart className="w-5 h-5" fill={isFav ? 'currentColor' : 'none'} />
          </button>
        </div>

        <div className="volume">
          <button
            className="key"
            style={{ width: 28, height: 28 }}
            onClick={() => setVolume(volume === 0 ? 0.8 : 0)}
            title={volume === 0 ? 'Включить звук' : 'Выключить звук'}
          >
            {volume === 0 ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <input
            className="vol"
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            aria-label="Громкость"
          />
        </div>
      </div>
    </section>
  );
};
