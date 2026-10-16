import { describe, expect, it } from 'vitest';
import { clearLaunchParams, parseLaunchParams } from './launchParams';

describe('parseLaunchParams', () => {
  it('accepts known vibes and numeric station ids', () => {
    expect(parseLaunchParams('?vibe=focus&station=42')).toMatchObject({ vibe: 'focus', stationId: 42 });
  });

  it('rejects unknown vibes and malformed ids', () => {
    expect(parseLaunchParams('?vibe=<script>&station=1e3')).toMatchObject({ vibe: null, stationId: null });
    expect(parseLaunchParams('?station=12345678901').stationId).toBeNull();
  });
});

describe('clearLaunchParams', () => {
  it('removes consumed params and keeps the rest', () => {
    window.history.replaceState(null, '', '/?vibe=focus&station=3&keep=1#h');
    clearLaunchParams();
    expect(window.location.search).toBe('?keep=1');
    expect(window.location.hash).toBe('#h');
  });
});
