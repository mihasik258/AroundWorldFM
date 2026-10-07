import { Airport, FlightRoute } from '../types';
import { City } from '../data/cities';
import { LANDMARKS, Landmark } from '../data/landmarks';

const RAD = Math.PI / 180;
const EARTH_KM = 6371;

type Vec3 = [number, number, number];

const unit = (lat: number, lon: number): Vec3 => [
  Math.cos(lat * RAD) * Math.cos(lon * RAD),
  Math.cos(lat * RAD) * Math.sin(lon * RAD),
  Math.sin(lat * RAD),
];

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

export const haversineKm = (lat1: number, lon1: number, lat2: number, lon2: number) =>
  Math.acos(Math.max(-1, Math.min(1, dot(unit(lat1, lon1), unit(lat2, lon2))))) * EARTH_KM;

const slerpUnit = (a: Vec3, b: Vec3, omega: number, t: number): Vec3 => {
  if (omega < 1e-6) return a;
  const s = Math.sin(omega);
  const w1 = Math.sin((1 - t) * omega) / s;
  const w2 = Math.sin(t * omega) / s;
  return [w1 * a[0] + w2 * b[0], w1 * a[1] + w2 * b[1], w1 * a[2] + w2 * b[2]];
};

export interface RouteLandmark {
  landmark: Landmark;
  progress: number;
  distanceKm: number;
}

const SIGHT_RANGE_KM = { landmark: 320, scenic: 460 };

export const landmarksAlongRoute = (route: FlightRoute): RouteLandmark[] => {
  const a = unit(route.origin.latitude, route.origin.longitude);
  const b = unit(route.destination.latitude, route.destination.longitude);
  const omega = Math.acos(Math.max(-1, Math.min(1, dot(a, b))));
  const SAMPLES = 360;
  const track: Vec3[] = [];
  for (let i = 0; i <= SAMPLES; i++) track.push(slerpUnit(a, b, omega, i / SAMPLES));

  const found: RouteLandmark[] = [];
  for (const lm of LANDMARKS) {
    const v = unit(lm.lat, lm.lon);
    let best = -2;
    let bestI = 0;
    for (let i = 0; i <= SAMPLES; i++) {
      const d = dot(track[i], v);
      if (d > best) {
        best = d;
        bestI = i;
      }
    }
    const km = Math.acos(Math.max(-1, Math.min(1, best))) * EARTH_KM;
    if (km > SIGHT_RANGE_KM[lm.kind]) continue;
    if ((bestI === 0 || bestI === SAMPLES) && km > 120) continue;
    const progress = Math.max(2.5, Math.min(97.5, (bestI / SAMPLES) * 100));
    found.push({ landmark: lm, progress, distanceKm: km });
  }

  found.sort((x, y) => x.progress - y.progress);

  for (let i = 1; i < found.length; i++) {
    if (found[i].progress - found[i - 1].progress < 1.2) {
      found[i].progress = Math.min(99, found[i - 1].progress + 1.2);
    }
  }
  return found;
};

const cityAirport = (city: City, id: number): Airport => ({
  id,
  iata_code: city.code,
  icao_code: null,
  name: `${city.nameEn} Airport`,
  city: city.name,
  country: city.country,
  country_code: city.countryCode,
  latitude: city.lat,
  longitude: city.lon,
  altitude_m: 0,
  timezone: 'UTC',
});

const CRUISE_KMH = 880;

export const buildCustomRoute = (from: City, to: City, vibe: string): FlightRoute => {
  const distance = haversineKm(from.lat, from.lon, to.lat, to.lon);
  const minutes = Math.round((distance / CRUISE_KMH) * 60 + 30);
  const seed = Math.abs(
    [...(from.code + to.code)].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) | 0, 7)
  );
  return {
    id: -(1 + (seed % 900000)),
    flight_number: `AFM${100 + (seed % 900)}`,
    airline: 'Around FM Charter',
    title: `${from.name} → ${to.name}`,
    origin_airport_id: -1,
    destination_airport_id: -2,
    distance_km: Math.round(distance),
    real_duration_minutes: Math.max(45, minutes),
    cruising_altitude_m: distance < 1500 ? 9800 : 11200,
    cruising_speed_kmh: CRUISE_KMH,
    recommended_vibe: vibe,
    description: null,
    is_featured: false,
    origin: cityAirport(from, -1),
    destination: cityAirport(to, -2),
  };
};

export const isCustomRoute = (route: FlightRoute) => route.id < 0;

export const formatDuration = (minutes: number) => {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m} мин`;
  return m > 0 ? `${h} ч ${m} мин` : `${h} ч`;
};

export const formatClock = (minutes: number) => {
  const total = Math.max(0, Math.round(minutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
};

export const formatKm = (km: number) => `${Math.round(km).toLocaleString('ru-RU')} км`;
