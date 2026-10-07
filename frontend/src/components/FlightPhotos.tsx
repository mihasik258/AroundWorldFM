import React, { useEffect, useRef, useState } from 'react';
import { useFlight } from '../context/FlightContext';
import { Landmark } from '../data/landmarks';
import { RouteLandmark, formatClock } from '../utils/geo';
import { useLandmarkPhoto } from '../services/landmarkPhotos';
import { flightOverlay } from '../services/flightOverlay';
import '../styles/flight-photos.css';

export const SnapshotImage: React.FC<{ landmark: Landmark; className?: string }> = ({
  landmark,
  className,
}) => {
  const url = useLandmarkPhoto(landmark.wiki);
  const [failed, setFailed] = useState(false);

  if (url && !failed) {
    return (
      <img
        className={className}
        src={url}
        alt={landmark.name}
        draggable={false}
        onError={() => setFailed(true)}
      />
    );
  }
  return (
    <div className={`${className ?? ''} snap-fallback is-${landmark.kind}`} aria-label={landmark.name}>
      <span>{landmark.icon}</span>
    </div>
  );
};

export const PhotoPin = React.forwardRef<
  HTMLDivElement,
  { rl: RouteLandmark; side: 'l' | 'r'; tier: number; waiting: boolean }
>(({ rl, side, tier, waiting }, ref) => (
  <div
    ref={ref}
    className={`ppin is-${side}${waiting ? ' is-waiting' : ''}`}
    style={{ '--stem': `${30 + tier * 22}px` } as React.CSSProperties}
  >
    <span className="ppin-stem" />
    <div className="ppin-card">
      <span className="ppin-head" />
      <SnapshotImage landmark={rl.landmark} className="ppin-img" />
      <div className="ppin-caption">
        <strong>{rl.landmark.name}</strong>
        <span>{rl.landmark.caption}</span>
      </div>
    </div>
  </div>
));
PhotoPin.displayName = 'PhotoPin';

let audioCtx: AudioContext | null = null;

const playShutter = () => {
  try {
    const AC = window.AudioContext || (window as any).webkitAudioContext;
    if (!AC) return;
    audioCtx = audioCtx ?? new AC();
    const ctx = audioCtx;
    if (ctx.state === 'suspended') ctx.resume();
    const now = ctx.currentTime;

    const master = ctx.createGain();
    master.gain.value = 0.3;
    const muffle = ctx.createBiquadFilter();
    muffle.type = 'lowpass';
    muffle.frequency.value = 2600;
    master.connect(muffle).connect(ctx.destination);

    const tick = (at: number, dur: number, freq: number, level: number) => {
      const len = Math.ceil(ctx.sampleRate * dur);
      const buf = ctx.createBuffer(1, len, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
      const src = ctx.createBufferSource();
      src.buffer = buf;
      const band = ctx.createBiquadFilter();
      band.type = 'bandpass';
      band.frequency.value = freq;
      band.Q.value = 1.4;
      const g = ctx.createGain();
      g.gain.setValueAtTime(level, at);
      g.gain.exponentialRampToValueAtTime(0.001, at + dur);
      src.connect(band).connect(g).connect(master);
      src.start(at);
    };

    tick(now, 0.035, 1900, 0.9);
    tick(now + 0.085, 0.05, 1200, 0.7);

    const thump = ctx.createOscillator();
    thump.type = 'sine';
    thump.frequency.setValueAtTime(140, now);
    thump.frequency.exponentialRampToValueAtTime(60, now + 0.08);
    const tg = ctx.createGain();
    tg.gain.setValueAtTime(0.35, now);
    tg.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
    thump.connect(tg).connect(master);
    thump.start(now);
    thump.stop(now + 0.12);
  } catch {
  }
};

const DEVELOP_MS = 5200;
const FLY_MS = 900;

type Phase = 'develop' | 'fly';

export const FlightSnapshots: React.FC = () => {
  const {
    isFlightMode,
    activeRoute,
    flightProgress,
    routeLandmarks,
    setDevelopingLandmarkId,
  } = useFlight();

  const [queue, setQueue] = useState<RouteLandmark[]>([]);
  const [current, setCurrent] = useState<{ rl: RouteLandmark; phase: Phase; at: number } | null>(null);
  const [flashKey, setFlashKey] = useState(0);
  const prevProgressRef = useRef<number | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [flyTo, setFlyTo] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    prevProgressRef.current = null;
    setQueue([]);
    setCurrent(null);
    setDevelopingLandmarkId(null);
  }, [activeRoute?.id, isFlightMode, setDevelopingLandmarkId]);

  useEffect(() => {
    if (!isFlightMode || !activeRoute) return;
    const prev = prevProgressRef.current;
    prevProgressRef.current = flightProgress;
    if (prev == null) return;

    if (flightProgress < prev) {
      setQueue((q) => q.filter((rl) => rl.progress <= flightProgress));
      setCurrent((c) => {
        if (c && c.rl.progress > flightProgress) {
          setDevelopingLandmarkId(null);
          return null;
        }
        return c;
      });
      return;
    }

    if (flightProgress - prev > 3.5) return;

    const crossed = routeLandmarks.filter((rl) => rl.progress > prev && rl.progress <= flightProgress);
    if (crossed.length) {
      setQueue((q) => [...q, ...crossed].slice(-2));
    }
  }, [flightProgress, isFlightMode, activeRoute, routeLandmarks, setDevelopingLandmarkId]);

  useEffect(() => {
    if (current || queue.length === 0) return;
    const [next, ...rest] = queue;
    setQueue(rest);
    setFlyTo(null);
    setCurrent({ rl: next, phase: 'develop', at: Date.now() });
    setDevelopingLandmarkId(next.landmark.id);
    setFlashKey((k) => k + 1);
    playShutter();
  }, [queue, current, setDevelopingLandmarkId]);

  useEffect(() => {
    if (!current) return;
    if (current.phase === 'develop') {
      const id = window.setTimeout(() => {
        const pin = flightOverlay.pins.get(current.rl.landmark.id);
        const card = cardRef.current;
        const stage = card?.offsetParent as HTMLElement | null;
        if (card && stage) {
          const cr = card.getBoundingClientRect();
          const sr = stage.getBoundingClientRect();
          const cx = cr.left - sr.left + cr.width / 2;
          const cy = cr.top - sr.top + cr.height / 2;
          const target = pin && pin.visible ? pin : flightOverlay.plane;
          setFlyTo({ x: target.x - cx, y: target.y - 60 - cy });
        }
        setCurrent((c) => (c ? { ...c, phase: 'fly' } : c));
      }, DEVELOP_MS);
      return () => window.clearTimeout(id);
    }
    const id = window.setTimeout(() => {
      setDevelopingLandmarkId(null);
      setCurrent(null);
    }, FLY_MS);
    return () => window.clearTimeout(id);
  }, [current, setDevelopingLandmarkId]);

  if (!isFlightMode || !activeRoute) return null;

  const lm = current?.rl.landmark;
  const shotAt = current ? (current.rl.progress / 100) * activeRoute.real_duration_minutes : 0;

  return (
    <>
      {flashKey > 0 && <div key={flashKey} className="snap-flash" aria-hidden="true" />}

      {current && lm && (
        <div
          key={lm.id}
          ref={cardRef}
          className={`snap-card is-${current.phase}`}
          style={
            flyTo
              ? ({ '--fx': `${flyTo.x}px`, '--fy': `${flyTo.y}px` } as React.CSSProperties)
              : undefined
          }
          role="status"
        >
          <div className="snap-photo">
            <SnapshotImage landmark={lm} className="snap-img" />
            <div className="snap-fog" />
          </div>
          <div className="snap-caption">
            <strong>{lm.name}</strong>
            <span>{lm.caption}</span>
            <span className="snap-meta num">
              {activeRoute.flight_number} · {formatClock(shotAt)} в пути
            </span>
          </div>
        </div>
      )}
    </>
  );
};
