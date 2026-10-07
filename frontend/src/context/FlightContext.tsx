import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from 'react';
import { apiRequest } from '../api/client';
import { FlightRoute, FlightTuning, RadioStation } from '../types';
import { usePlayer } from './PlayerContext';
import { City } from '../data/cities';
import {
  RouteLandmark,
  buildCustomRoute,
  isCustomRoute,
  landmarksAlongRoute,
} from '../utils/geo';
import { prefetchLandmarkPhotos } from '../services/landmarkPhotos';

export type PlannerMode = 'routes' | 'custom';

export interface RouteHover {
  id: number;
  source: 'list' | 'globe';
}

export const slerpLatLon = (
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
  t: number
): { lat: number; lon: number } => {
  t = Math.max(0, Math.min(1, t));
  if (t <= 0) return { lat: lat1, lon: lon1 };
  if (t >= 1) return { lat: lat2, lon: lon2 };

  const phi1 = (lat1 * Math.PI) / 180;
  const lam1 = (lon1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const lam2 = (lon2 * Math.PI) / 180;

  const x1 = Math.cos(phi1) * Math.cos(lam1);
  const y1 = Math.cos(phi1) * Math.sin(lam1);
  const z1 = Math.sin(phi1);

  const x2 = Math.cos(phi2) * Math.cos(lam2);
  const y2 = Math.cos(phi2) * Math.sin(lam2);
  const z2 = Math.sin(phi2);

  const dot = Math.max(-1, Math.min(1, x1 * x2 + y1 * y2 + z1 * z2));
  const omega = Math.acos(dot);
  if (omega < 1e-6) return { lat: lat1, lon: lon1 };

  const sinOmega = Math.sin(omega);
  const w1 = Math.sin((1 - t) * omega) / sinOmega;
  const w2 = Math.sin(t * omega) / sinOmega;

  let x = w1 * x1 + w2 * x2;
  let y = w1 * y1 + w2 * y2;
  let z = w1 * z1 + w2 * z2;

  const norm = Math.hypot(x, y, z);
  if (norm < 1e-9) return { lat: lat1, lon: lon1 };

  x /= norm;
  y /= norm;
  z /= norm;

  const lat = (Math.asin(Math.max(-1, Math.min(1, z))) * 180) / Math.PI;
  const lon = (Math.atan2(y, x) * 180) / Math.PI;
  return { lat, lon };
};

export const calculateFlightAltitude = (cruisingAltM: number, t: number): number => {
  t = Math.max(0, Math.min(1, t));
  const climb = 0.08;
  const descent = 0.08;
  if (t < climb) {
    return cruisingAltM * Math.sin((t / climb) * (Math.PI / 2));
  } else if (t > 1 - descent) {
    return cruisingAltM * Math.sin(((1 - t) / descent) * (Math.PI / 2));
  }
  return cruisingAltM;
};

interface FlightContextType {
  isFlightMode: boolean;
  routes: FlightRoute[];
  activeRoute: FlightRoute | null;
  flightProgress: number;
  flightSpeed: number;
  isFlightPlaying: boolean;
  followCamera: boolean;
  flightTuning: FlightTuning | null;
  currentCoords: { lat: number; lon: number; altitude_m: number } | null;
  isLoadingRoutes: boolean;

  isPlannerOpen: boolean;
  plannerMode: PlannerMode;
  hoveredRoute: RouteHover | null;
  customFrom: City | null;
  customTo: City | null;
  draftRoute: FlightRoute | null;

  routeLandmarks: RouteLandmark[];
  capturedLandmarks: RouteLandmark[];
  developingLandmarkId: string | null;
  setDevelopingLandmarkId: (id: string | null) => void;

  openPlanner: () => void;
  closePlanner: () => void;
  setPlannerMode: (mode: PlannerMode) => void;
  setHoveredRoute: (hover: RouteHover | null) => void;
  setCustomFrom: (city: City | null) => void;
  setCustomTo: (city: City | null) => void;
  pickCity: (city: City) => void;
  startFlight: (route: FlightRoute, initialProgress?: number) => void;
  exitFlight: () => void;
  seekFlight: (progressPercent: number) => void;
  stepFlightTime: (minutesDelta: number) => void;
  setSpeed: (multiplier: number) => void;
  toggleFlightPlay: () => void;
  setFollowCamera: (follow: boolean) => void;
}

const FlightContext = createContext<FlightContextType | undefined>(undefined);

export const FlightProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { playStation, currentStation, setIsAutoRotateEnabled, resetRotationTimer, currentVibe } =
    usePlayer();

  const [routes, setRoutes] = useState<FlightRoute[]>([]);
  const [isLoadingRoutes, setIsLoadingRoutes] = useState(false);
  const [isFlightMode, setIsFlightMode] = useState(false);
  const [activeRoute, setActiveRoute] = useState<FlightRoute | null>(null);
  const [flightProgress, setFlightProgress] = useState<number>(0.0);
  const [flightSpeed, setFlightSpeed] = useState<number>(1.0);
  const [isFlightPlaying, setIsFlightPlaying] = useState<boolean>(true);
  const [followCamera, setFollowCamera] = useState<boolean>(true);
  const [isPlannerOpen, setIsPlannerOpen] = useState(false);
  const [plannerMode, setPlannerMode] = useState<PlannerMode>('routes');
  const [hoveredRoute, setHoveredRoute] = useState<RouteHover | null>(null);
  const [customFrom, setCustomFrom] = useState<City | null>(null);
  const [customTo, setCustomTo] = useState<City | null>(null);
  const [developingLandmarkId, setDevelopingLandmarkId] = useState<string | null>(null);
  const [flightTuning, setFlightTuning] = useState<FlightTuning | null>(null);

  const activeRouteRef = useRef<FlightRoute | null>(null);
  activeRouteRef.current = activeRoute;
  const flightProgressRef = useRef<number>(flightProgress);
  flightProgressRef.current = flightProgress;
  const flightSpeedRef = useRef<number>(flightSpeed);
  flightSpeedRef.current = flightSpeed;
  const isFlightPlayingRef = useRef<boolean>(isFlightPlaying);
  isFlightPlayingRef.current = isFlightPlaying;
  const isFlightModeRef = useRef<boolean>(isFlightMode);
  isFlightModeRef.current = isFlightMode;

  const currentStationRef = useRef(currentStation);
  currentStationRef.current = currentStation;
  const playStationRef = useRef(playStation);
  playStationRef.current = playStation;

  const lastTimeRef = useRef<number | null>(null);
  const lastTuningFetchRef = useRef<number>(0);
  const isFetchingTuningRef = useRef<boolean>(false);

  useEffect(() => {
    setIsLoadingRoutes(true);
    apiRequest<FlightRoute[]>('/flights/routes')
      .then((data) => {
        setRoutes(data);
      })
      .catch((err) => {
        console.error('Failed to load flight routes:', err);
      })
      .finally(() => {
        setIsLoadingRoutes(false);
      });
  }, []);

  const currentCoords = React.useMemo(() => {
    if (!activeRoute) return null;
    const t = flightProgress / 100.0;
    const { lat, lon } = slerpLatLon(
      activeRoute.origin.latitude,
      activeRoute.origin.longitude,
      activeRoute.destination.latitude,
      activeRoute.destination.longitude,
      t
    );
    const alt = calculateFlightAltitude(activeRoute.cruising_altitude_m, t);
    return { lat, lon, altitude_m: alt };
  }, [activeRoute, flightProgress]);

  const fetchTuning = useCallback(async (routeId: number, progress: number) => {
    if (isFetchingTuningRef.current) return;
    isFetchingTuningRef.current = true;
    try {
      const curId = currentStationRef.current?.id;
      const queryParam = curId ? `&current_station_id=${curId}` : '';
      const route = activeRouteRef.current;
      let data: FlightTuning;

      if (route && route.id === routeId && isCustomRoute(route)) {
        const t = progress / 100;
        const pos = slerpLatLon(
          route.origin.latitude,
          route.origin.longitude,
          route.destination.latitude,
          route.destination.longitude,
          t
        );
        const point = await apiRequest<{ distance_km: number; station?: RadioStation | null }>(
          `/flights/tuning/point?lat=${pos.lat.toFixed(4)}&lon=${pos.lon.toFixed(4)}${queryParam}`
        );
        const elapsed = Math.round(route.real_duration_minutes * t);
        data = {
          route_id: route.id,
          progress_percent: progress,
          current_lat: pos.lat,
          current_lon: pos.lon,
          current_altitude_m: calculateFlightAltitude(route.cruising_altitude_m, t),
          distance_from_origin_km: route.distance_km * t,
          distance_to_destination_km: route.distance_km * (1 - t),
          elapsed_minutes: elapsed,
          remaining_minutes: Math.max(0, route.real_duration_minutes - elapsed),
          region_label: '',
          station: point.station ?? null,
        };
      } else {
        data = await apiRequest<FlightTuning>(
          `/flights/routes/${routeId}/tuning?progress=${progress.toFixed(2)}${queryParam}`
        );
      }
      setFlightTuning(data);

      if (data.station && (!currentStationRef.current || currentStationRef.current.id !== data.station.id)) {
        playStationRef.current(data.station);
      }
    } catch (e) {
      console.warn('Flight tuning request error:', e);
    } finally {
      isFetchingTuningRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!isFlightMode || !activeRoute) {
      lastTimeRef.current = null;
      return;
    }

    let animId: number;

    const tick = (now: number) => {
      if (lastTimeRef.current == null) {
        lastTimeRef.current = now;
      }
      const deltaSec = (now - lastTimeRef.current) / 1000;
      lastTimeRef.current = now;

      if (isFlightPlayingRef.current && activeRouteRef.current) {
        const totalDurationSec = Math.max(60, activeRouteRef.current.real_duration_minutes * 60);
        const speed = flightSpeedRef.current;
        const progressInc = (deltaSec / totalDurationSec) * speed * 100.0;

        let nextProgress = flightProgressRef.current + progressInc;
        if (nextProgress >= 100.0) {
          nextProgress = 100.0;
          setIsFlightPlaying(false);
        }

        setFlightProgress(nextProgress);

        if (now - lastTuningFetchRef.current > 3500) {
          lastTuningFetchRef.current = now;
          fetchTuning(activeRouteRef.current.id, nextProgress);
        }
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isFlightMode, activeRoute, fetchTuning]);

  const openPlanner = useCallback(() => {
    setHoveredRoute(null);
    setIsPlannerOpen(true);
  }, []);
  const closePlanner = useCallback(() => {
    setHoveredRoute(null);
    setIsPlannerOpen(false);
  }, []);

  const customFromRef = useRef<City | null>(null);
  customFromRef.current = customFrom;
  const customToRef = useRef<City | null>(null);
  customToRef.current = customTo;
  const pickCity = useCallback((city: City) => {
    const from = customFromRef.current;
    const to = customToRef.current;
    if (!from || (from && to)) {
      setCustomFrom(city);
      setCustomTo(null);
    } else if (city.code !== from.code) {
      setCustomTo(city);
    }
  }, []);

  const draftRoute = React.useMemo(
    () =>
      customFrom && customTo && customFrom.code !== customTo.code
        ? buildCustomRoute(customFrom, customTo, currentVibe)
        : null,
    [customFrom, customTo, currentVibe]
  );

  const routeLandmarks = React.useMemo(
    () => (activeRoute ? landmarksAlongRoute(activeRoute) : []),
    [activeRoute]
  );
  const capturedLandmarks = React.useMemo(
    () => routeLandmarks.filter((rl) => rl.progress <= flightProgress),
    [routeLandmarks, flightProgress]
  );

  const startFlight = useCallback(
    (route: FlightRoute, initialProgress = 0.0) => {
      setActiveRoute(route);
      setFlightProgress(initialProgress);
      setIsFlightPlaying(true);
      setIsFlightMode(true);
      setIsAutoRotateEnabled(false);
      setIsPlannerOpen(false);
      setHoveredRoute(null);
      lastTimeRef.current = null;
      activeRouteRef.current = route;

      prefetchLandmarkPhotos(landmarksAlongRoute(route).map((rl) => rl.landmark.wiki));

      fetchTuning(route.id, initialProgress);
    },
    [fetchTuning, setIsAutoRotateEnabled]
  );

  const exitFlight = useCallback(() => {
    setIsFlightMode(false);
    setIsPlannerOpen(false);
    setActiveRoute(null);
    setIsAutoRotateEnabled(true);
    resetRotationTimer();
  }, [setIsAutoRotateEnabled, resetRotationTimer]);

  const seekFlight = useCallback(
    (progressPercent: number) => {
      const clamped = Math.max(0.0, Math.min(100.0, progressPercent));
      setFlightProgress(clamped);
      if (activeRouteRef.current) {
        fetchTuning(activeRouteRef.current.id, clamped);
      }
    },
    [fetchTuning]
  );

  const stepFlightTime = useCallback(
    (minutesDelta: number) => {
      if (!activeRouteRef.current) return;
      const totalMinutes = activeRouteRef.current.real_duration_minutes;
      const deltaPercent = (minutesDelta / totalMinutes) * 100.0;
      seekFlight(flightProgressRef.current + deltaPercent);
    },
    [seekFlight]
  );

  const setSpeed = useCallback((multiplier: number) => {
    setFlightSpeed(multiplier);
  }, []);

  const toggleFlightPlay = useCallback(() => {
    setIsFlightPlaying((prev) => !prev);
  }, []);

  return (
    <FlightContext.Provider
      value={{
        isFlightMode,
        routes,
        activeRoute,
        flightProgress,
        flightSpeed,
        isFlightPlaying,
        followCamera,
        flightTuning,
        currentCoords,
        isLoadingRoutes,
        isPlannerOpen,
        plannerMode,
        hoveredRoute,
        customFrom,
        customTo,
        draftRoute,
        routeLandmarks,
        capturedLandmarks,
        developingLandmarkId,
        setDevelopingLandmarkId,
        openPlanner,
        closePlanner,
        setPlannerMode,
        setHoveredRoute,
        setCustomFrom,
        setCustomTo,
        pickCity,
        startFlight,
        exitFlight,
        seekFlight,
        stepFlightTime,
        setSpeed,
        toggleFlightPlay,
        setFollowCamera,
      }}
    >
      {children}
    </FlightContext.Provider>
  );
};

export const useFlight = (): FlightContextType => {
  const context = useContext(FlightContext);
  if (!context) {
    throw new Error('useFlight must be used within a FlightProvider');
  }
  return context;
};
