import { useEffect, useState } from 'react';

const STORAGE_KEY = 'afm_landmark_photos_v1';
const API = 'https://en.wikipedia.org/w/api.php';
const THUMB_PX = 800;
const BATCH = 45;

type Entry = string | null;

const cache = new Map<string, Entry>();
const pending = new Set<string>();
const listeners = new Set<() => void>();

try {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) {
    const saved = JSON.parse(raw) as Record<string, Entry>;
    Object.entries(saved).forEach(([k, v]) => {
      if (v) cache.set(k, v);
    });
  }
} catch {
}

const persist = () => {
  try {
    const obj: Record<string, Entry> = {};
    cache.forEach((v, k) => {
      if (v) obj[k] = v;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  } catch {
  }
};

const notify = () => listeners.forEach((fn) => fn());

const preload = (url: string) => {
  const img = new Image();
  img.decoding = 'async';
  img.src = url;
};

const fetchBatch = async (titles: string[]) => {
  const params = new URLSearchParams({
    action: 'query',
    format: 'json',
    formatversion: '2',
    redirects: '1',
    prop: 'pageimages',
    piprop: 'thumbnail',
    pithumbsize: String(THUMB_PX),
    origin: '*',
    titles: titles.map((t) => t.replace(/_/g, ' ')).join('|'),
  });

  const res = await fetch(`${API}?${params.toString()}`);
  if (!res.ok) throw new Error(`wiki ${res.status}`);
  const data = await res.json();

  const alias = new Map<string, string>();
  (data.query?.normalized ?? []).forEach((n: any) => alias.set(n.from, n.to));
  (data.query?.redirects ?? []).forEach((n: any) => alias.set(n.from, n.to));
  const pages = new Map<string, any>();
  (data.query?.pages ?? []).forEach((p: any) => pages.set(p.title, p));

  titles.forEach((title) => {
    let t = title.replace(/_/g, ' ');
    for (let hops = 0; hops < 4 && alias.has(t); hops++) t = alias.get(t)!;
    const url: Entry = pages.get(t)?.thumbnail?.source ?? null;
    cache.set(title, url);
    if (url) preload(url);
  });
};

export const prefetchLandmarkPhotos = async (titles: string[]) => {
  const todo = [...new Set(titles)].filter((t) => !cache.has(t) && !pending.has(t));
  if (todo.length === 0) {
    titles.forEach((t) => {
      const u = cache.get(t);
      if (u) preload(u);
    });
    return;
  }
  todo.forEach((t) => pending.add(t));
  try {
    for (let i = 0; i < todo.length; i += BATCH) {
      await fetchBatch(todo.slice(i, i + BATCH));
    }
  } catch (e) {
    console.warn('Landmark photos unavailable:', e);
    todo.forEach((t) => {
      if (!cache.has(t)) cache.set(t, null);
    });
  } finally {
    todo.forEach((t) => pending.delete(t));
    persist();
    notify();
  }
};

export const useLandmarkPhoto = (title: string | null | undefined): Entry | undefined => {
  const [, force] = useState(0);
  useEffect(() => {
    const fn = () => force((n) => n + 1);
    listeners.add(fn);
    if (title && !cache.has(title)) prefetchLandmarkPhotos([title]);
    return () => {
      listeners.delete(fn);
    };
  }, [title]);
  if (!title) return null;
  return cache.has(title) ? cache.get(title)! : undefined;
};
