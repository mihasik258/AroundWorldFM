import { afterEach, describe, expect, it, vi } from 'vitest';
import { launchedFromTelegram, loadTelegramWebApp, openTelegramLink } from './telegram';

describe('telegram', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/');
    delete window.Telegram;
  });

  it('detects Mini App launch from the hash', () => {
    expect(launchedFromTelegram()).toBe(false);
    window.history.replaceState(null, '', '/#tgWebAppData=abc');
    expect(launchedFromTelegram()).toBe(true);
  });

  it('does not load the SDK for regular visitors', async () => {
    await expect(loadTelegramWebApp()).resolves.toBeNull();
    expect(document.querySelector('script[src*="telegram"]')).toBeNull();
  });

  it('loads the SDK once inside Telegram and initialises it', async () => {
    window.history.replaceState(null, '', '/#tgWebAppData=abc');
    const pending = loadTelegramWebApp();
    expect(loadTelegramWebApp()).toBe(pending);
    const script = document.querySelector<HTMLScriptElement>('script[src="https://telegram.org/js/telegram-web-app.js"]');
    expect(script).not.toBeNull();
    const webApp = { initData: 'signed', ready: vi.fn(), expand: vi.fn(), setHeaderColor: vi.fn() };
    window.Telegram = { WebApp: webApp };
    script?.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBe(webApp);
    expect(webApp.ready).toHaveBeenCalled();
    expect(webApp.expand).toHaveBeenCalled();
    expect(webApp.setHeaderColor).toHaveBeenCalledWith('#070a10');
  });

  it('opens links through the Mini App when available', () => {
    const openTelegram = vi.fn();
    window.Telegram = { WebApp: { initData: 'x', ready: vi.fn(), expand: vi.fn(), openTelegramLink: openTelegram } };
    openTelegramLink('https://t.me/bot?start=link_x');
    expect(openTelegram).toHaveBeenCalledWith('https://t.me/bot?start=link_x');
  });

  it('falls back to a new tab', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    openTelegramLink('https://t.me/bot');
    expect(open).toHaveBeenCalledWith('https://t.me/bot', '_blank', 'noopener,noreferrer');
  });
});
