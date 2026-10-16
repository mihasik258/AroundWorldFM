export type UserRole = 'user' | 'admin';

export type AuthProviderId = 'password' | 'telegram';

export interface UserIdentity {
  provider: AuthProviderId;
  display_name: string | null;
  created_at: string;
}

export interface User {
  id: number;
  email: string | null;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  auth_providers: AuthProviderId[];
  identities: UserIdentity[];
}

export interface AuthProviders {
  telegram: { enabled: boolean; bot_username: string | null };
}

export interface NowPlaying {
  station_id: number;
  has_track: boolean;
  raw_title: string | null;
  artist: string | null;
  title: string | null;
  spotify_url: string | null;
}

export interface UserSession {
  id: number;
  device_name?: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
  last_used_at: string;
  is_current?: boolean;
}

export interface RadioStation {
  id: number;
  station_uuid?: string | null;
  name: string;
  stream_url: string;
  homepage_url?: string | null;
  favicon_url?: string | null;
  country: string;
  country_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  language?: string | null;
  tags: string[];
  location_precision?: 'exact' | 'country';
  codec: string;
  bitrate: number;
  is_active: boolean;
  last_checked_at?: string | null;
  created_at: string;
}

export interface StationPoint {
  id: number;
  latitude: number;
  longitude: number;
}

export interface SystemStats {
  total_users: number;
  total_stations: number;
  active_stations: number;
  stream_availability_percentage: number;
  active_sessions: number;
}

export interface Airport {
  id: number;
  iata_code: string;
  icao_code?: string | null;
  name: string;
  city: string;
  country: string;
  country_code: string;
  latitude: number;
  longitude: number;
  altitude_m: number;
  timezone: string;
}

export interface FlightRoute {
  id: number;
  flight_number: string;
  airline: string;
  title: string;
  origin_airport_id: number;
  destination_airport_id: number;
  distance_km: number;
  real_duration_minutes: number;
  cruising_altitude_m: number;
  cruising_speed_kmh: number;
  recommended_vibe: string;
  description?: string | null;
  is_featured: boolean;
  origin: Airport;
  destination: Airport;
}

export interface FlightTuning {
  route_id: number;
  progress_percent: number;
  current_lat: number;
  current_lon: number;
  current_altitude_m: number;
  distance_from_origin_km: number;
  distance_to_destination_km: number;
  elapsed_minutes: number;
  remaining_minutes: number;
  region_label: string;
  station?: RadioStation | null;
}
