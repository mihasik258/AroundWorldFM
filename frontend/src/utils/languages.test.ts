import { describe, expect, it } from 'vitest';
import { languageLabel } from './languages';

describe('languageLabel', () => {
  it('translates known codes', () => {
    expect(languageLabel('german')).toBe('Немецкий');
    expect(languageLabel('English')).toBe('Английский');
    expect(languageLabel('instrumental')).toBe('Без слов');
  });

  it('capitalizes unknown codes and handles empty values', () => {
    expect(languageLabel('klingon')).toBe('Klingon');
    expect(languageLabel(null)).toBe('');
  });
});
