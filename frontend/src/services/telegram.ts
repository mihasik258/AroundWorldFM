interface TelegramWebApp {
  initData: string;
  ready: () => void;
  expand: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  HapticFeedback?: { selectionChanged: () => void };
  openTelegramLink?: (url: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

const SDK_URL = 'https://telegram.org/js/telegram-web-app.js';
const BACKGROUND = '#070a10';

export function launchedFromTelegram(): boolean {
  const hash = window.location.hash;
  const search = window.location.search;
  return hash.includes('tgWebAppData') || search.includes('tgWebAppStartParam');
}

let sdkPromise: Promise<TelegramWebApp | null> | null = null;

export function loadTelegramWebApp(): Promise<TelegramWebApp | null> {
  if (!launchedFromTelegram()) return Promise.resolve(null);
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve) => {
      const script = document.createElement('script');
      script.src = SDK_URL;
      script.async = true;
      script.onload = () => {
        const webApp = window.Telegram?.WebApp;
        if (!webApp || !webApp.initData) {
          resolve(null);
          return;
        }
        webApp.ready();
        webApp.expand();
        webApp.setHeaderColor?.(BACKGROUND);
        webApp.setBackgroundColor?.(BACKGROUND);
        resolve(webApp);
      };
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    });
  }
  return sdkPromise;
}

export function openTelegramLink(url: string): void {
  const webApp = window.Telegram?.WebApp;
  if (webApp?.openTelegramLink) {
    webApp.openTelegramLink(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

export function hapticTick(): void {
  window.Telegram?.WebApp?.HapticFeedback?.selectionChanged();
}
