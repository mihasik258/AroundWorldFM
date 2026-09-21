export type UserRole = 'user' | 'admin';

export interface User {
  id: number;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface UserSession {
  id: number;
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
  tags: string;
  vibes?: string;
  codec: string;
  bitrate: number;
  is_active: boolean;
  last_checked_at?: string | null;
  created_at: string;
  tag_list: string[];
  vibe_list?: string[];
}

export interface SystemStats {
  total_users: number;
  total_stations: number;
  active_stations: number;
  stream_availability_percentage: number;
  active_sessions: number;
}
