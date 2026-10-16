export interface LaunchParams {
  vibe: string | null;
  stationId: number | null;
}

const VIBES = new Set(['focus', 'night_drive', 'coffee', 'party', 'sunset', 'world_odyssey']);
const CONSUMED = ['vibe', 'station'];

export function parseLaunchParams(search: string): LaunchParams {
  const params = new URLSearchParams(search);
  const vibe = params.get('vibe');
  const station = params.get('station');
  const stationId = station && /^\d{1,9}$/.test(station) ? Number(station) : null;
  return {
    vibe: vibe && VIBES.has(vibe) ? vibe : null,
    stationId,
  };
}

export const launchParams: LaunchParams = parseLaunchParams(window.location.search);

export function clearLaunchParams(): void {
  const url = new URL(window.location.href);
  let changed = false;
  for (const key of CONSUMED) {
    if (url.searchParams.has(key)) {
      url.searchParams.delete(key);
      changed = true;
    }
  }
  if (changed) {
    window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
  }
}
