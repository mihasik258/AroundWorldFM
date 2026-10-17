import { describe, expect, it } from 'vitest';
import { formatClock, formatDuration, formatKm, haversineKm } from './geo';

describe('geo utils', () => {
  it('computes great-circle distance', () => {
    expect(Math.round(haversineKm(52.37, 13.5, 40.64, -73.78))).toBeGreaterThan(6300);
    expect(haversineKm(10, 10, 10, 10)).toBeCloseTo(0, 2);
  });

  it('formats values for the HUD', () => {
    expect(formatKm(6384.4)).toMatch(/^6\s?384 км$/);
    expect(formatDuration(870)).toBe('14 ч 30 мин');
    expect(formatDuration(45)).toBe('45 мин');
    expect(formatDuration(120)).toBe('2 ч');
    expect(formatClock(65)).toBe('01:05');
    expect(formatClock(-3)).toBe('00:00');
  });
});
