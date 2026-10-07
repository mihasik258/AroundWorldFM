import React, { useState } from 'react';
import {
  Camera,
  ChevronDown,
  ChevronUp,
  LocateFixed,
  Map as MapIcon,
  Move,
  Pause,
  Plane,
  Play,
  RotateCcw,
  RotateCw,
  X,
} from 'lucide-react';
import { useFlight } from '../context/FlightContext';
import { formatClock, formatKm } from '../utils/geo';
import '../styles/flight-hud.css';

const SPEEDS = [1, 5, 20, 60];

export const FlightHud: React.FC = () => {
  const {
    isFlightMode,
    isPlannerOpen,
    activeRoute,
    flightProgress,
    flightSpeed,
    isFlightPlaying,
    followCamera,
    flightTuning,
    currentCoords,
    routeLandmarks,
    seekFlight,
    stepFlightTime,
    setSpeed,
    toggleFlightPlay,
    setFollowCamera,
    openPlanner,
    exitFlight,
  } = useFlight();

  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!isFlightMode || !activeRoute || isPlannerOpen) return null;

  const total = activeRoute.real_duration_minutes;
  const elapsed = (flightProgress / 100) * total;
  const remaining = Math.max(0, total - elapsed);
  const alt = currentCoords?.altitude_m ?? 0;
  const climbShare = activeRoute.cruising_altitude_m > 0 ? alt / activeRoute.cruising_altitude_m : 0;
  const groundSpeed = Math.round(activeRoute.cruising_speed_kmh * (0.35 + 0.65 * climbShare));
  const distLeft = activeRoute.distance_km * (1 - flightProgress / 100);
  const captured = routeLandmarks.filter((rl) => rl.progress <= flightProgress).length;

  const where =
    flightProgress < 4
      ? `Вылет · ${activeRoute.origin.city}`
      : flightProgress > 96
        ? `Заход на посадку · ${activeRoute.destination.city}`
        : flightTuning?.station
          ? `Над: ${flightTuning.station.country}`
          : 'Над облаками';

  const lat = currentCoords?.lat ?? activeRoute.origin.latitude;
  const lon = currentCoords?.lon ?? activeRoute.origin.longitude;
  const coords = `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(2)}°${
    lon >= 0 ? 'E' : 'W'
  }`;

  return (
    <>
      <section className={`fhud arrive${isCollapsed ? ' is-collapsed' : ''}`} aria-label="Полёт">
        <header className="fhud-top">
          <span className="fhud-flight num">{activeRoute.flight_number}</span>
          <span className="fhud-airline">{activeRoute.airline}</span>
          <div className="fhud-actions">
            <button
              className={`fhud-btn${followCamera ? ' is-on' : ''}`}
              onClick={() => setFollowCamera(!followCamera)}
              title={followCamera ? 'Камера следует за самолётом' : 'Свободная камера'}
            >
              {followCamera ? <LocateFixed className="w-4 h-4" /> : <Move className="w-4 h-4" />}
            </button>
            <button className="fhud-btn" onClick={openPlanner} title="Сменить маршрут">
              <MapIcon className="w-4 h-4" />
            </button>
            <button
              className="fhud-btn"
              onClick={() => setIsCollapsed(!isCollapsed)}
              title={isCollapsed ? 'Развернуть' : 'Свернуть'}
            >
              {isCollapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
            <button className="fhud-btn is-exit" onClick={exitFlight} title="Выйти из авиарежима">
              <X className="w-4 h-4" />
            </button>
          </div>
        </header>

        <div className="fhud-route">
          <div className="fhud-end">
            <span className="fhud-code num">{activeRoute.origin.iata_code}</span>
            <span className="fhud-city">{activeRoute.origin.city}</span>
          </div>
          <div className="fhud-track" aria-hidden="true">
            <div className="fhud-track-line" />
            <div className="fhud-track-fill" style={{ width: `${flightProgress}%` }} />
            <Plane className="fhud-track-plane" style={{ left: `${flightProgress}%` }} />
          </div>
          <div className="fhud-end is-dest">
            <span className="fhud-code num">{activeRoute.destination.iata_code}</span>
            <span className="fhud-city">{activeRoute.destination.city}</span>
          </div>
        </div>

        {!isCollapsed && (
          <>
            <dl className="fhud-grid">
              <div>
                <dt>Высота</dt>
                <dd className="num">
                  {Math.round(alt).toLocaleString('ru-RU')}
                  <small>м</small>
                </dd>
              </div>
              <div>
                <dt>Скорость</dt>
                <dd className="num">
                  {groundSpeed}
                  <small>км/ч</small>
                </dd>
              </div>
              <div>
                <dt>До посадки</dt>
                <dd className="num">{formatKm(distLeft)}</dd>
              </div>
              <div>
                <dt>Снимки</dt>
                <dd className="num">
                  {captured}
                  <small>/ {routeLandmarks.length}</small>
                </dd>
              </div>
            </dl>

            <div className="fhud-now">
              <div className="fhud-where">
                <span>{where}</span>
                <span className="num fhud-coords">{coords}</span>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="ftl arrive arrive-2" aria-label="Время полёта">
        <div className="ftl-keys">
          <button className="fhud-btn" onClick={() => stepFlightTime(-15)} title="Назад на 15 минут">
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            className="ftl-play"
            onClick={toggleFlightPlay}
            title={isFlightPlaying ? 'Пауза' : 'Продолжить полёт'}
          >
            {isFlightPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
          </button>
          <button className="fhud-btn" onClick={() => stepFlightTime(15)} title="Вперёд на 15 минут">
            <RotateCw className="w-4 h-4" />
          </button>
        </div>

        <span className="ftl-time num">{formatClock(elapsed)}</span>

        <div className="ftl-track" style={{ '--p': `${flightProgress}%` } as React.CSSProperties}>
          <div className="ftl-rail" />
          <div className="ftl-fill" />
          {routeLandmarks.map((rl) => (
            <button
              key={rl.landmark.id}
              className={`ftl-sight${rl.progress <= flightProgress ? ' is-taken' : ''}${
                rl.landmark.kind === 'scenic' ? ' is-scenic' : ''
              }`}
              style={{ left: `${rl.progress}%` }}
              title={rl.landmark.name}
              onClick={() => seekFlight(Math.max(0, rl.progress - 0.6))}
            >
              <span className="ftl-sight-label">
                <Camera className="w-3 h-3" />
                {rl.landmark.name}
              </span>
            </button>
          ))}
          <input
            className="ftl-range"
            type="range"
            min="0"
            max="100"
            step="0.05"
            value={flightProgress}
            onChange={(e) => seekFlight(parseFloat(e.target.value))}
            aria-label="Прогресс полёта"
          />
        </div>

        <span className="ftl-time num is-left">−{formatClock(remaining)}</span>

        <div className="ftl-speed" role="group" aria-label="Скорость времени">
          {SPEEDS.map((s) => (
            <button key={s} className={`num${flightSpeed === s ? ' is-on' : ''}`} onClick={() => setSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
      </section>
    </>
  );
};
