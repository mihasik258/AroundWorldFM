import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeftRight, Camera, Plane, X } from 'lucide-react';
import { useFlight } from '../context/FlightContext';
import { CITIES, City } from '../data/cities';
import { FlightRoute } from '../types';
import { formatDuration, formatKm, landmarksAlongRoute } from '../utils/geo';
import '../styles/flight-planner.css';

const CityField: React.FC<{
  label: string;
  value: City | null;
  exclude?: City | null;
  onChange: (city: City | null) => void;
}> = ({ label, value, exclude, onChange }) => {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return CITIES.filter(
      (c) =>
        c.code !== exclude?.code &&
        (!q ||
          c.name.toLowerCase().includes(q) ||
          c.nameEn.toLowerCase().includes(q) ||
          c.code.toLowerCase().startsWith(q) ||
          c.country.toLowerCase().includes(q))
    ).slice(0, 8);
  }, [query, exclude]);

  const choose = (c: City) => {
    onChange(c);
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
  };

  return (
    <div className="plan-field">
      <span className="plan-field-label">{label}</span>
      <div className="plan-field-box">
        {value && !open ? (
          <button
            type="button"
            className="plan-field-value"
            onClick={() => {
              setOpen(true);
              setTimeout(() => inputRef.current?.focus(), 0);
            }}
          >
            <span className="num plan-code">{value.code}</span>
            <span className="plan-field-city">{value.name}</span>
            <span className="plan-field-country">{value.country}</span>
          </button>
        ) : (
          <input
            ref={inputRef}
            className="plan-input"
            placeholder="Город или код аэропорта"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && matches[0]) choose(matches[0]);
              if (e.key === 'Escape') setOpen(false);
            }}
          />
        )}
        {open && matches.length > 0 && (
          <ul className="plan-suggest">
            {matches.map((c) => (
              <li key={c.code}>
                <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c)}>
                  <span className="num plan-code">{c.code}</span>
                  <span>{c.name}</span>
                  <span className="plan-field-country">{c.country}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};

const RouteRow: React.FC<{
  route: FlightRoute;
  isActive: boolean;
  isHovered: boolean;
  revealOnHover: boolean;
  onHover: (id: number | null) => void;
  onSelect: () => void;
}> = ({ route, isActive, isHovered, revealOnHover, onHover, onSelect }) => {
  const sights = useMemo(() => landmarksAlongRoute(route).length, [route]);
  const rowRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    if (isHovered && revealOnHover) {
      rowRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [isHovered, revealOnHover]);

  return (
    <li ref={rowRef}>
      <button
        type="button"
        className={`plan-route${isHovered ? ' is-hovered' : ''}${isActive ? ' is-active' : ''}`}
        onMouseEnter={() => onHover(route.id)}
        onMouseLeave={() => onHover(null)}
        onFocus={() => onHover(route.id)}
        onBlur={() => onHover(null)}
        onClick={onSelect}
      >
        <span className="plan-route-codes num">
          {route.origin.iata_code}
          <span className="plan-route-dash" />
          {route.destination.iata_code}
        </span>
        <span className="plan-route-cities">
          {route.origin.city} — {route.destination.city}
        </span>
        <span className="plan-route-meta">
          <span className="num">{route.flight_number}</span>
          <span>{formatDuration(route.real_duration_minutes)}</span>
          <span className="plan-route-sights">
            <Camera className="w-3 h-3" />
            <span className="num">{sights}</span>
          </span>
        </span>
      </button>
    </li>
  );
};

export const FlightPlanner: React.FC = () => {
  const {
    isPlannerOpen,
    closePlanner,
    plannerMode,
    setPlannerMode,
    routes,
    isLoadingRoutes,
    activeRoute,
    startFlight,
    hoveredRoute,
    setHoveredRoute,
    customFrom,
    customTo,
    setCustomFrom,
    setCustomTo,
    draftRoute,
  } = useFlight();

  const draftSights = useMemo(() => (draftRoute ? landmarksAlongRoute(draftRoute) : []), [draftRoute]);

  if (!isPlannerOpen) return null;

  return (
    <aside className="planner arrive" aria-label="Выбор маршрута">
      <header className="planner-head">
        <div>
          <span className="planner-kicker">
            <Plane className="w-3.5 h-3.5" />
            Авиарежим
          </span>
          <h2 className="planner-title">Куда летим?</h2>
        </div>
        <button className="key" onClick={closePlanner} title="Закрыть" style={{ width: 32, height: 32 }}>
          <X className="w-4 h-4" />
        </button>
      </header>

      <div className="planner-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={plannerMode === 'routes'}
          className={`planner-tab${plannerMode === 'routes' ? ' is-on' : ''}`}
          onClick={() => setPlannerMode('routes')}
        >
          Рейсы
        </button>
        <button
          role="tab"
          aria-selected={plannerMode === 'custom'}
          className={`planner-tab${plannerMode === 'custom' ? ' is-on' : ''}`}
          onClick={() => setPlannerMode('custom')}
        >
          Свой маршрут
        </button>
      </div>

      {plannerMode === 'routes' ? (
        <div className="planner-body no-scrollbar">
          {isLoadingRoutes ? (
            <p className="planner-hint">Загрузка маршрутов…</p>
          ) : (
            <ul className="plan-routes">
              {routes.map((r) => (
                <RouteRow
                  key={r.id}
                  route={r}
                  isActive={activeRoute?.id === r.id}
                  isHovered={hoveredRoute?.id === r.id}
                  revealOnHover={hoveredRoute?.source === 'globe'}
                  onHover={(id) => setHoveredRoute(id == null ? null : { id, source: 'list' })}
                  onSelect={() => startFlight(r)}
                />
              ))}
            </ul>
          )}
          <p className="planner-hint">Наведите на линию на глобусе — покажем рейс. Клик — взлёт.</p>
        </div>
      ) : (
        <div className="planner-body no-scrollbar">
          <CityField label="Откуда" value={customFrom} exclude={customTo} onChange={setCustomFrom} />
          <button
            type="button"
            className="plan-swap"
            title="Поменять местами"
            disabled={!customFrom && !customTo}
            onClick={() => {
              const f = customFrom;
              setCustomFrom(customTo);
              setCustomTo(f);
            }}
          >
            <ArrowLeftRight className="w-3.5 h-3.5" />
          </button>
          <CityField label="Куда" value={customTo} exclude={customFrom} onChange={setCustomTo} />

          {draftRoute ? (
            <div className="plan-draft">
              <div className="plan-draft-stats">
                <div>
                  <span className="plan-stat-label">Расстояние</span>
                  <span className="num">{formatKm(draftRoute.distance_km)}</span>
                </div>
                <div>
                  <span className="plan-stat-label">В пути</span>
                  <span className="num">{formatDuration(draftRoute.real_duration_minutes)}</span>
                </div>
                <div>
                  <span className="plan-stat-label">Снимков</span>
                  <span className="num">{draftSights.length}</span>
                </div>
              </div>
              {draftSights.length > 0 && (
                <p className="plan-draft-sights">
                  По пути: {draftSights.slice(0, 4).map((s) => s.landmark.name).join(', ')}
                  {draftSights.length > 4 ? ` и ещё ${draftSights.length - 4}` : ''}
                </p>
              )}
              <button className="plan-takeoff" onClick={() => startFlight(draftRoute)}>
                <Plane className="w-4 h-4" />
                Взлететь
              </button>
            </div>
          ) : (
            <p className="planner-hint">
              Выберите города в полях или щёлкните по точкам на глобусе: первый клик — вылет, второй —
              прилёт.
            </p>
          )}
        </div>
      )}
    </aside>
  );
};
