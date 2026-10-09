import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { usePlayer } from '../context/PlayerContext';
import { useFlight, slerpLatLon, calculateFlightAltitude } from '../context/FlightContext';
import { RadioStation } from '../types';
import { CITIES } from '../data/cities';
import { LANDMARKS } from '../data/landmarks';
import { formatClock, formatDuration, formatKm, landmarksAlongRoute } from '../utils/geo';
import { flightOverlay } from '../services/flightOverlay';
import { SightMarker, createSightMarker, pointAlong, styleSightMarker } from './globeSights';
import { PhotoPin } from './FlightPhotos';

interface GlobeProps {
  stations?: RadioStation[];
}

const COUNTRY_COORDS: Record<string, { lat: number; lng: number }> = {
  'USA': { lat: 37.09, lng: -95.71 },
  'United States': { lat: 37.09, lng: -95.71 },
  'United States of America': { lat: 37.09, lng: -95.71 },
  'UK': { lat: 51.51, lng: -0.13 },
  'United Kingdom': { lat: 51.51, lng: -0.13 },
  'France': { lat: 46.23, lng: 2.21 },
  'Germany': { lat: 51.17, lng: 10.45 },
  'Netherlands': { lat: 52.13, lng: 5.29 },
  'Belgium': { lat: 50.85, lng: 4.35 },
  'Switzerland': { lat: 46.82, lng: 8.23 },
  'Austria': { lat: 47.52, lng: 14.55 },
  'Italy': { lat: 41.87, lng: 12.57 },
  'Spain': { lat: 40.46, lng: -3.75 },
  'Portugal': { lat: 39.40, lng: -8.22 },
  'Russia': { lat: 61.52, lng: 105.32 },
  'Russian Federation': { lat: 61.52, lng: 105.32 },
  'Japan': { lat: 36.20, lng: 138.25 },
  'Australia': { lat: -25.27, lng: 133.78 },
  'New Zealand': { lat: -40.90, lng: 174.89 },
  'Canada': { lat: 56.13, lng: -106.35 },
  'Brazil': { lat: -14.24, lng: -51.93 },
  'Argentina': { lat: -38.42, lng: -63.62 },
  'Mexico': { lat: 23.63, lng: -102.55 },
  'South Korea': { lat: 35.91, lng: 127.77 },
  'India': { lat: 20.59, lng: 78.96 },
  'China': { lat: 35.86, lng: 104.20 },
  'Ireland': { lat: 53.14, lng: -7.69 },
  'Norway': { lat: 60.47, lng: 8.47 },
  'Sweden': { lat: 60.13, lng: 18.64 },
  'Finland': { lat: 61.92, lng: 25.75 },
  'Denmark': { lat: 56.26, lng: 9.50 },
  'Poland': { lat: 51.92, lng: 19.15 },
  'Ukraine': { lat: 48.38, lng: 31.17 },
  'Greece': { lat: 39.07, lng: 21.82 },
  'Turkey': { lat: 38.96, lng: 35.24 },
  'Egypt': { lat: 26.82, lng: 30.80 },
  'South Africa': { lat: -30.56, lng: 22.94 },
  'Nigeria': { lat: 9.08, lng: 8.68 },
  'Colombia': { lat: 4.57, lng: -74.30 },
  'Hungary': { lat: 47.16, lng: 19.50 },
  'Czechia': { lat: 49.82, lng: 15.47 },
};

const RADIUS = 78;

const toVector = (lat: number, lon: number, r = RADIUS) => {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(r * Math.sin(phi) * Math.cos(theta)),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
};

const solarPosition = (now: Date) => {
  const utcHours = now.getUTCHours() + now.getUTCMinutes() / 60;
  const lon = (12 - utcHours) * 15;
  const dayOfYear = Math.floor(
    (now.getTime() - new Date(now.getFullYear(), 0, 0).getTime()) / 86400000
  );
  const lat = -23.44 * Math.cos((2 * Math.PI / 365) * (dayOfYear + 10));
  return { lat, lon };
};

const isNightAt = (lat: number, lon: number, sun: { lat: number; lon: number }) => {
  const rad = Math.PI / 180;
  return (
    Math.sin(lat * rad) * Math.sin(sun.lat * rad) +
      Math.cos(lat * rad) * Math.cos(sun.lat * rad) * Math.cos((lon - sun.lon) * rad) <
    0
  );
};

const stationCoords = (st: RadioStation) => {
  let lat = st.latitude;
  let lon = st.longitude;
  if (lat == null || lon == null) {
    const fb = COUNTRY_COORDS[st.country];
    if (fb) {
      lat = fb.lat;
      lon = fb.lng;
    }
  }
  return lat != null && lon != null ? { lat, lon } : null;
};

const getTargetRotation = (lat: number, lon: number, currentY: number) => {
  const targetX = (lat * Math.PI) / 180;
  const rawTargetY = -(lon * Math.PI) / 180 - Math.PI / 2;
  const diffY = Math.atan2(Math.sin(rawTargetY - currentY), Math.cos(rawTargetY - currentY));
  return {
    x: Math.max(-1.45, Math.min(1.45, targetX)),
    y: currentY + diffY,
  };
};

const createAirportMarker = (iata: string, isDestination: boolean): THREE.Group => {
  const g = new THREE.Group();
  const mainColor = isDestination ? 0xf59e0b : 0x06b6d4;

  const pad = new THREE.Mesh(
    new THREE.RingGeometry(0.4, 1.8, 36),
    new THREE.MeshBasicMaterial({
      color: mainColor,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    })
  );
  pad.rotation.x = -Math.PI / 2;
  g.add(pad);

  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 16, 16),
    new THREE.MeshBasicMaterial({ color: 0xffffff })
  );
  core.position.y = 0.35;
  g.add(core);

  const canvas = document.createElement('canvas');
  canvas.width = 160;
  canvas.height = 80;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = isDestination ? '#1c1917' : '#082f49';
  if ((ctx as any).roundRect) {
    (ctx as any).roundRect(6, 6, 148, 68, 14);
  } else {
    ctx.rect(6, 6, 148, 68);
  }
  ctx.fill();

  ctx.lineWidth = 4;
  ctx.strokeStyle = isDestination ? '#f59e0b' : '#06b6d4';
  ctx.stroke();

  ctx.fillStyle = isDestination ? '#fbbf24' : '#38bdf8';
  ctx.font = 'bold 15px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillText(isDestination ? 'ARRIVAL' : 'DEPARTURE', 80, 14);

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 34px monospace';
  ctx.fillText(iata, 80, 36);

  const texture = new THREE.CanvasTexture(canvas);
  const spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
  const sprite = new THREE.Sprite(spriteMat);
  sprite.position.y = 3.2;
  sprite.scale.set(3.8, 1.9, 1);
  g.add(sprite);

  return g;
};

const createAirplaneMesh = (): THREE.Group => {
  const plane = new THREE.Group();

  const paper = new THREE.MeshStandardMaterial({
    color: 0xf5f1e8,
    side: THREE.DoubleSide,
    flatShading: true,
    roughness: 0.8,
    metalness: 0,
    emissive: 0xb8c2c6,
    emissiveIntensity: 0.55,
  });
  const fold = paper.clone();
  fold.color.set(0xd9d2c3);
  fold.emissive.set(0x8c979c);

  const tri = (a: number[], b: number[], c: number[], mat: THREE.Material) => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c], 3));
    geo.computeVertexNormals();
    return new THREE.Mesh(geo, mat);
  };

  const nose = [0, 0, 4];
  const tailL = [-4, 0.4, -3];
  const tailR = [4, 0.4, -3];
  const keel = [0, -1.2, -3];
  const mid = [0, 0, -3];

  plane.add(tri(nose, tailL, mid, paper), tri(nose, mid, tailR, paper));
  plane.add(tri(nose, mid, keel, fold));

  const creases = [
    [nose, tailL], [tailL, mid], [nose, tailR], [tailR, mid], [nose, mid], [mid, keel], [nose, keel],
  ];
  plane.add(
    new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(creases.flat().map((p) => new THREE.Vector3(p[0], p[1], p[2]))),
      new THREE.LineBasicMaterial({ color: 0x63d3f2, transparent: true, opacity: 0.6 })
    )
  );

  plane.scale.setScalar(0.75);
  return plane;
};

const buildRibbonGeometry = (points: THREE.Vector3[], halfWidth: number) => {
  const N = points.length - 1;
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];
  for (let i = 0; i <= N; i++) {
    const p = points[i];
    const tangent = points[Math.min(N, i + 1)].clone().sub(points[Math.max(0, i - 1)]).normalize();
    const binormal = new THREE.Vector3().crossVectors(tangent, p.clone().normalize()).normalize();
    const l = p.clone().addScaledVector(binormal, -halfWidth);
    const r = p.clone().addScaledVector(binormal, halfWidth);
    positions.push(l.x, l.y, l.z, r.x, r.y, r.z);
    const u = i / N;
    uvs.push(u, 0, u, 1);
    if (i < N) {
      const b = i * 2;
      indices.push(b, b + 1, b + 2, b + 1, b + 3, b + 2);
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  return geo;
};

const buildLiftedArc = (lat1: number, lon1: number, lat2: number, lon2: number, n = 96) => {
  const a = toVector(lat1, lon1, 1);
  const b = toVector(lat2, lon2, 1);
  const angle = a.angleTo(b);
  const peak = Math.min(13, 1.2 + angle * 7.5);
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const { lat, lon } = slerpLatLon(lat1, lon1, lat2, lon2, t);
    pts.push(toVector(lat, lon, RADIUS + 0.35 + peak * Math.sin(Math.PI * t)));
  }
  return pts;
};

const createPlannerArcMaterial = (color: number, density: number) =>
  new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uHover: { value: 0 },
      uDim: { value: 1 },
      uReveal: { value: 0 },
      uDensity: { value: density },
      uColor: { value: new THREE.Color(color) },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uHover;
      uniform float uDim;
      uniform float uReveal;
      uniform float uDensity;
      uniform vec3 uColor;
      varying vec2 vUv;
      void main() {
        if (vUv.x > uReveal) discard;
        float edge = abs(vUv.y - 0.5) * 2.0;
        float width = mix(0.5, 1.0, uHover);
        float body = 1.0 - smoothstep(width * 0.45, width, edge);
        float core = 1.0 - smoothstep(0.0, width * 0.35, edge);

        float f = fract(vUv.x * uDensity - uTime * (0.35 + 0.4 * uHover));
        float comet = pow(f, 7.0);

        float ends = smoothstep(0.0, 0.025, vUv.x) * smoothstep(1.0, 0.975, vUv.x);
        float tip = smoothstep(uReveal - 0.04, uReveal, vUv.x) * step(uReveal, 0.999);

        vec3 col = mix(uColor, vec3(1.0), core * (0.25 + 0.5 * uHover) + comet * 0.55 + tip);
        float a = body * (0.5 + 0.4 * uHover + comet * (0.6 + 0.4 * uHover) + tip) * ends * uDim;
        gl_FragColor = vec4(col, a);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
    depthWrite: false,
  });

const createCodeSprite = (code: string, color: string) => {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 48;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = 'rgba(7, 10, 16, 0.82)';
  if ((ctx as any).roundRect) (ctx as any).roundRect(4, 4, 120, 40, 8);
  else ctx.rect(4, 4, 120, 40);
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.globalAlpha = 0.55;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#e8e3d8';
  ctx.font = '600 24px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(code, 64, 26);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  sprite.scale.set(4.4, 1.65, 1);
  return sprite;
};

const LAND_DOT_DEG = 1.05;
const PULSE_SLOTS = 4;
const createLandMaterial = () =>
  new THREE.ShaderMaterial({
    uniforms: {
      uSun: { value: new THREE.Vector3(1, 0, 0) },
      uScale: { value: 500 },
      uSize: { value: 0.5 },
      uPulseOrigin: { value: Array.from({ length: PULSE_SLOTS }, () => new THREE.Vector3(0, 1, 0)) },
      uPulseStrength: { value: new Array(PULSE_SLOTS).fill(0) },
      uPulseSpeed: { value: [0.85, 1.6, 0.9, 0.9] },
      uPulseColor: {
        value: [
          new THREE.Color(1.0, 0.76, 0.42),
          new THREE.Color(0.45, 0.88, 1.0),
          new THREE.Color(0.45, 0.88, 1.0),
          new THREE.Color(1.0, 0.76, 0.42),
        ],
      },
      uPulseTime: { value: 0 },
    },
    vertexShader: `
      uniform vec3 uSun;
      uniform float uScale;
      uniform float uSize;
      uniform vec3 uPulseOrigin[${PULSE_SLOTS}];
      uniform float uPulseStrength[${PULSE_SLOTS}];
      uniform float uPulseSpeed[${PULSE_SLOTS}];
      uniform vec3 uPulseColor[${PULSE_SLOTS}];
      uniform float uPulseTime;
      varying float vLight;
      varying float vFacing;
      varying float vPulse;
      varying vec3 vPulseColor;
      void main() {
        vec3 n = normalize(position);
        vLight = dot(n, uSun);
        vFacing = normalize(normalMatrix * n).z;

        float total = 0.0;
        vec3 tint = vec3(0.0);
        for (int k = 0; k < ${PULSE_SLOTS}; k++) {
          if (uPulseStrength[k] <= 0.0) continue;
          float ang = acos(clamp(dot(n, uPulseOrigin[k]), -1.0, 1.0));
          if (ang > 0.4) continue;
          float g = 0.0;
          for (int i = 0; i < 2; i++) {
            float ph = fract(uPulseTime * uPulseSpeed[k] + float(i) * 0.5);
            float front = (1.0 - pow(1.0 - ph, 2.0)) * 0.3;
            g += exp(-pow((ang - front) * 34.0, 2.0)) * pow(1.0 - ph, 1.5);
          }
          g += exp(-pow(ang * 28.0, 2.0)) * 0.35;
          g *= uPulseStrength[k];
          total += g;
          tint += uPulseColor[k] * g;
        }
        vPulse = clamp(total, 0.0, 1.0);
        vPulseColor = total > 0.0 ? tint / total : vec3(1.0);

        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = max(1.0, uSize * (1.0 + vPulse * 1.2) * uScale / -mv.z);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: `
      varying float vLight;
      varying float vFacing;
      varying float vPulse;
      varying vec3 vPulseColor;
      void main() {
        float r = length(gl_PointCoord - 0.5) * 2.0;
        float disc = 1.0 - smoothstep(0.7, 1.0, r);
        if (disc <= 0.0) discard;
        float day = smoothstep(-0.12, 0.22, vLight);
        vec3 night = vec3(0.3, 0.62, 0.72);
        vec3 lit = vec3(0.86, 0.92, 0.94) * (0.6 + 0.4 * max(vLight, 0.0));
        vec3 col = mix(night, lit, day);
        col = mix(col, vPulseColor, vPulse);
        float limb = smoothstep(-0.05, 0.3, vFacing);
        gl_FragColor = vec4(col, disc * limb);
      }
    `,
    transparent: true,
    depthWrite: false,
  });

type HoverTarget =
  | { kind: 'route'; id: number }
  | { kind: 'city'; code: string }
  | { kind: 'sight'; id: string };

const sameTarget = (a: HoverTarget | null, b: HoverTarget | null) => {
  if (!a || !b) return a === b;
  if (a.kind !== b.kind) return false;
  if (a.kind === 'route') return a.id === (b as any).id;
  if (a.kind === 'city') return a.code === (b as any).code;
  return a.id === (b as any).id;
};

export const Globe: React.FC<GlobeProps> = ({ stations = [] }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { currentStation, playStation } = usePlayer();
  const {
    isFlightMode,
    activeRoute,
    flightProgress,
    followCamera,
    currentCoords,
    isPlannerOpen,
    plannerMode,
    routes,
    hoveredRoute,
    setHoveredRoute,
    draftRoute,
    customFrom,
    customTo,
    pickCity,
    startFlight,
    routeLandmarks,
    capturedLandmarks,
    developingLandmarkId,
  } = useFlight();

  const [geoData, setGeoData] = useState<any | null>(null);
  const [isTuning, setIsTuning] = useState(false);
  const [sunTick, setSunTick] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textureRef = useRef<THREE.CanvasTexture | null>(null);
  const globeGroupRef = useRef<THREE.Group | null>(null);
  const targetRotationRef = useRef<{ x: number; y: number } | null>(null);
  const isManualTuningRef = useRef<boolean>(false);
  const beaconRef = useRef<THREE.Group | null>(null);
  const prevStationIdRef = useRef<number | null>(null);
  const stationPinsGroupRef = useRef<THREE.Group | null>(null);
  const updateSunRef = useRef<() => void>(() => {});
  const landPositionsRef = useRef<Float32Array | null>(null);
  const landGroupRef = useRef<THREE.Group | null>(null);
  const landMatRef = useRef<THREE.ShaderMaterial | null>(null);

  const mountLandPoints = () => {
    const group = landGroupRef.current;
    const positions = landPositionsRef.current;
    if (!group || !positions || !landMatRef.current) return;
    group.children.forEach((c) => (c as THREE.Points).geometry?.dispose());
    group.clear();
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const points = new THREE.Points(geo, landMatRef.current);
    points.renderOrder = 1;
    group.add(points);
  };

  const flightGroupRef = useRef<THREE.Group | null>(null);
  const airplaneRef = useRef<THREE.Group | null>(null);
  const flightTrajectoryMeshRef = useRef<THREE.Mesh | null>(null);
  const originMarkerRef = useRef<THREE.Group | null>(null);
  const destMarkerRef = useRef<THREE.Group | null>(null);
  const arcPointsRef = useRef<THREE.Vector3[]>([]);

  const plannerGroupRef = useRef<THREE.Group | null>(null);
  const plannerArcsRef = useRef<
    Map<number, { mesh: THREE.Mesh; mat: THREE.ShaderMaterial; points: THREE.Vector3[]; hover: number }>
  >(new Map());
  const plannerRevealRef = useRef(0);
  const cityPointsRef = useRef<{ code: string; pos: THREE.Vector3 }[]>([]);
  const hoverRef = useRef<HoverTarget | null>(null);
  const [hoverTarget, setHoverTarget] = useState<HoverTarget | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  const sightMarkersRef = useRef<Map<string, SightMarker>>(new Map());
  const sightLayerRef = useRef<THREE.Group | null>(null);
  const pinElsRef = useRef<Map<string, HTMLDivElement>>(new Map());
  const pinProgressRef = useRef<Map<string, number>>(new Map());

  const isFlightModeRef = useRef(isFlightMode);
  isFlightModeRef.current = isFlightMode;
  const isPlannerOpenRef = useRef(isPlannerOpen);
  isPlannerOpenRef.current = isPlannerOpen;
  const plannerModeRef = useRef(plannerMode);
  plannerModeRef.current = plannerMode;
  const hoveredRouteRef = useRef(hoveredRoute);
  hoveredRouteRef.current = hoveredRoute;
  const routesRef = useRef(routes);
  routesRef.current = routes;
  const plannerActionsRef = useRef({ setHoveredRoute, pickCity, startFlight });
  plannerActionsRef.current = { setHoveredRoute, pickCity, startFlight };
  const activeRouteRef = useRef(activeRoute);
  activeRouteRef.current = activeRoute;
  const flightProgressRef = useRef(flightProgress);
  flightProgressRef.current = flightProgress;
  const followCameraRef = useRef(followCamera);
  followCameraRef.current = followCamera;
  const currentCoordsRef = useRef(currentCoords);
  currentCoordsRef.current = currentCoords;

  const stationsRef = useRef<RadioStation[]>(stations);
  stationsRef.current = stations;
  const currentStationRef = useRef<RadioStation | null>(currentStation);
  currentStationRef.current = currentStation;
  const playStationRef = useRef(playStation);
  playStationRef.current = playStation;

  useEffect(() => {
    fetch('/countries.geojson')
      .then((res) => res.json())
      .then((data) => setGeoData(data))
      .catch((e) => console.error('Failed to load countries.geojson', e));
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      updateSunRef.current();
      setSunTick((t) => t + 1);
    }, 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!geoData) return;

    const W = 2048;
    const H = 1024;

    const mask = document.createElement('canvas');
    mask.width = W;
    mask.height = H;
    const mctx = mask.getContext('2d')!;
    mctx.fillStyle = '#000';
    mctx.fillRect(0, 0, W, H);
    mctx.fillStyle = '#fff';

    const toXY = (lon: number, lat: number): [number, number] => [
      ((lon + 180) / 360) * W,
      ((90 - lat) / 180) * H,
    ];

    const tracePolygon = (ring: number[][]) => {
      if (!ring || ring.length === 0) return;
      mctx.beginPath();
      const [sx, sy] = toXY(ring[0][0], ring[0][1]);
      mctx.moveTo(sx, sy);
      for (let i = 1; i < ring.length; i++) {
        const [x, y] = toXY(ring[i][0], ring[i][1]);
        mctx.lineTo(x, y);
      }
      mctx.closePath();
      mctx.fill();
    };

    geoData.features.forEach((feat: any) => {
      const geom = feat.geometry;
      if (!geom) return;
      if (geom.type === 'Polygon') {
        geom.coordinates.forEach((ring: number[][]) => tracePolygon(ring));
      } else if (geom.type === 'MultiPolygon') {
        geom.coordinates.forEach((poly: number[][][]) =>
          poly.forEach((ring: number[][]) => tracePolygon(ring))
        );
      }
    });

    const maskData = mctx.getImageData(0, 0, W, H).data;

    let canvas = canvasRef.current;
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.width = W;
      canvas.height = H;
      canvasRef.current = canvas;
    }
    const ctx = canvas.getContext('2d')!;

    ctx.fillStyle = '#050a14';
    ctx.fillRect(0, 0, W, H);

    ctx.strokeStyle = 'rgba(120, 200, 220, 0.11)';
    ctx.lineWidth = 1.5;
    const latY = (lat: number) => ((90 - lat) / 180) * H;
    [0, 23.44, -23.44, 66.56, -66.56].forEach((lat, i) => {
      ctx.save();
      if (i > 0) ctx.setLineDash([9, 15]);
      ctx.beginPath();
      ctx.moveTo(0, latY(lat));
      ctx.lineTo(W, latY(lat));
      ctx.stroke();
      ctx.restore();
    });
    for (let m = 0; m < 12; m++) {
      ctx.save();
      ctx.setLineDash([9, 15]);
      ctx.beginPath();
      ctx.moveTo((m / 12) * W, 0);
      ctx.lineTo((m / 12) * W, H);
      ctx.stroke();
      ctx.restore();
    }

    const coords: number[] = [];
    for (let lat = -90 + LAND_DOT_DEG / 2; lat < 90; lat += LAND_DOT_DEG) {
      const n = Math.max(1, Math.round((360 * Math.cos((lat * Math.PI) / 180)) / LAND_DOT_DEG));
      const y = Math.min(H - 1, Math.floor(((90 - lat) / 180) * H));
      for (let i = 0; i < n; i++) {
        const lon = -180 + ((i + 0.5) * 360) / n;
        const x = Math.min(W - 1, Math.floor(((lon + 180) / 360) * W));
        if (maskData[(y * W + x) * 4] > 127) {
          const v = toVector(lat, lon, RADIUS + 0.06);
          coords.push(v.x, v.y, v.z);
        }
      }
    }
    landPositionsRef.current = new Float32Array(coords);
    mountLandPoints();

    if (textureRef.current) textureRef.current.needsUpdate = true;
  }, [geoData]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const width = container.clientWidth || 500;
    const height = container.clientHeight || 420;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);

    let baseDist = RADIUS * 2.8;
    let targetZoom = 1.0;
    let currentZoom = 1.0;

    const fitCamera = (w: number, h: number) => {
      const halfFov = (camera.fov * Math.PI) / 180 / 2;
      const distForHeight = (RADIUS * 1.28) / Math.tan(halfFov);
      baseDist = Math.max(distForHeight, distForHeight / (w / h));
      camera.position.z = baseDist * currentZoom;
    };
    fitCamera(width, height);

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY * 0.001;
      const minZoom = isFlightModeRef.current ? 0.45 : 0.72;
      targetZoom = Math.max(minZoom, Math.min(1.35, targetZoom + delta));
    };
    container.addEventListener('wheel', onWheel, { passive: false });

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    const globeGroup = new THREE.Group();
    scene.add(globeGroup);
    globeGroupRef.current = globeGroup;

    if (!canvasRef.current) {
      const c = document.createElement('canvas');
      c.width = 2048;
      c.height = 1024;
      const cx = c.getContext('2d')!;
      cx.fillStyle = '#050a14';
      cx.fillRect(0, 0, 2048, 1024);
      canvasRef.current = c;
    }

    const texture = new THREE.CanvasTexture(canvasRef.current);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    textureRef.current = texture;

    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, 160, 160),
      new THREE.MeshStandardMaterial({
        map: texture,
        roughness: 1,
        metalness: 0,
        emissive: new THREE.Color(0x1d5f74),
        emissiveMap: texture,
        emissiveIntensity: 0.85,
      })
    );
    globeGroup.add(sphere);

    const landGroup = new THREE.Group();
    globeGroup.add(landGroup);
    landGroupRef.current = landGroup;
    const landMat = createLandMaterial();
    landMatRef.current = landMat;
    mountLandPoints();

    const updatePointScale = () => {
      const h = renderer.getDrawingBufferSize(new THREE.Vector2()).y;
      landMat.uniforms.uScale.value = h / (2 * Math.tan((camera.fov * Math.PI) / 360));
    };
    updatePointScale();

    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 1.055, 64, 64),
      new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: new THREE.Color(0x4fd6ff) },
          uIntensity: { value: 0.55 },
        },
        vertexShader: `
          varying vec3 vNormal;
          varying vec3 vView;
          void main() {
            vNormal = normalize(normalMatrix * normal);
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            vView = normalize(-mv.xyz);
            gl_Position = projectionMatrix * mv;
          }
        `,
        fragmentShader: `
          uniform vec3 uColor;
          uniform float uIntensity;
          varying vec3 vNormal;
          varying vec3 vView;
          void main() {
            float rim = pow(1.0 - abs(dot(vNormal, vView)), 3.2);
            gl_FragColor = vec4(uColor, rim * uIntensity);
          }
        `,
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
      })
    );
    scene.add(atmosphere);

    const starCount = 1400;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const v = new THREE.Vector3()
        .randomDirection()
        .multiplyScalar(560 + Math.random() * 340);
      starPos.set([v.x, v.y, v.z], i * 3);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const stars = new THREE.Points(
      starGeo,
      new THREE.PointsMaterial({ color: 0x9fc6d8, size: 1.7, sizeAttenuation: true, transparent: true, opacity: 0.55 })
    );
    scene.add(stars);

    const stationLayer = new THREE.Group();
    globeGroup.add(stationLayer);

    const stationPinsGroup = new THREE.Group();
    stationLayer.add(stationPinsGroup);
    stationPinsGroupRef.current = stationPinsGroup;

    const plannerGroup = new THREE.Group();
    globeGroup.add(plannerGroup);
    plannerGroupRef.current = plannerGroup;

    const sightLayer = new THREE.Group();
    sightLayer.visible = false;
    globeGroup.add(sightLayer);
    sightLayerRef.current = sightLayer;
    sightMarkersRef.current.clear();
    LANDMARKS.forEach((lm) => {
      const marker = createSightMarker(lm, toVector(lm.lat, lm.lon, RADIUS + 0.05));
      styleSightMarker(marker, false, false);
      sightLayer.add(marker.group);
      sightMarkersRef.current.set(lm.id, marker);
    });

    const flightGroup = new THREE.Group();
    globeGroup.add(flightGroup);
    flightGroupRef.current = flightGroup;

    const airplane = createAirplaneMesh();
    airplane.visible = false;
    flightGroup.add(airplane);
    airplaneRef.current = airplane;

    const beacon = new THREE.Group();
    beacon.visible = false;
    stationLayer.add(beacon);
    beaconRef.current = beacon;

    const beamHeight = 34;
    const beamMat = new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(0xffb347) },
        uIntensity: { value: 0.55 },
      },
      vertexShader: `
        varying float vH;
        void main() {
          vH = uv.y;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uIntensity;
        varying float vH;
        void main() {
          gl_FragColor = vec4(uColor, (1.0 - vH) * uIntensity);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.6, 2.4, beamHeight, 24, 1, true),
      beamMat
    );
    beam.position.y = beamHeight / 2;
    beacon.add(beam);

    const coreMat = new THREE.MeshBasicMaterial({ color: 0xffc670, transparent: true, opacity: 1.0 });
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(2.1, 20, 20),
      coreMat
    );
    beacon.add(core);

    scene.add(new THREE.AmbientLight(0x1a2740, 0.55));

    const sunLight = new THREE.DirectionalLight(0xfff2d8, 2.5);
    globeGroup.add(sunLight);
    const nightFill = new THREE.DirectionalLight(0x2f6f96, 0.3);
    globeGroup.add(nightFill);

    const updateSunPosition = () => {
      const { lat, lon } = solarPosition(new Date());
      const p = toVector(lat, lon, 300);
      sunLight.position.copy(p);
      nightFill.position.copy(p).multiplyScalar(-1);
      landMat.uniforms.uSun.value.copy(p).normalize();
    };
    updateSunPosition();
    updateSunRef.current = updateSunPosition;

    let isDragging = false;
    let previous = { x: 0, y: 0 };
    let velocityX = 0;
    let velocityY = 0;
    let totalDragDistance = 0;

    let settlePending = false;

    const getStationCandidates = (): RadioStation[] => {
      const current = currentStationRef.current;
      const all = stationsRef.current || [];
      if (!current) return all;
      if (all.some((s) => s.id === current.id)) return all;
      return [current, ...all];
    };

    const getClosestStation = (g: THREE.Group, candidates: RadioStation[]) => {
      const centerLat = Math.max(-85, Math.min(85, (g.rotation.x * 180) / Math.PI));
      let centerLon = (-(g.rotation.y + Math.PI / 2) * 180) / Math.PI;
      centerLon = (((centerLon + 180) % 360) + 360) % 360 - 180;

      let closest: RadioStation | null = null;
      let minDistance = Infinity;
      const cosLat = Math.cos((centerLat * Math.PI) / 180);

      for (const st of candidates) {
        const c = stationCoords(st);
        if (!c) continue;
        const dLat = c.lat - centerLat;
        let dLon = Math.abs(c.lon - centerLon);
        if (dLon > 180) dLon = 360 - dLon;
        const dist = Math.hypot(dLat, dLon * cosLat);
        if (dist < minDistance) {
          minDistance = dist;
          closest = st;
        }
      }
      return { closest, dist: minDistance, centerLat, centerLon };
    };

    const isFreeSpin = () => isFlightModeRef.current || isPlannerOpenRef.current;

    const settleOnNearest = () => {
      settlePending = false;
      const { closest } = getClosestStation(globeGroup, getStationCandidates());
      if (!closest) return;
      const c = stationCoords(closest);
      if (c) {
        targetRotationRef.current = getTargetRotation(c.lat, c.lon, globeGroup.rotation.y);
        velocityX = 0;
        velocityY = 0;
      }
      if (closest.id !== currentStationRef.current?.id) {
        isManualTuningRef.current = true;
        playStationRef.current(closest);
      }
    };

    const startDrag = (x: number, y: number) => {
      updatePointer(x, y);
      if (isFlightModeRef.current && followCameraRef.current && !isPlannerOpenRef.current) {
        return;
      }
      isDragging = true;
      settlePending = false;
      targetRotationRef.current = null;
      if (!isFreeSpin()) {
        setIsTuning(true);
      }
      previous = { x, y };
      velocityX = 0;
      velocityY = 0;
      totalDragDistance = 0;
    };

    const moveDrag = (x: number, y: number) => {
      if (!isDragging) return;
      if (isFlightModeRef.current && followCameraRef.current && !isPlannerOpenRef.current) {
        isDragging = false;
        return;
      }
      targetRotationRef.current = null;
      const dx = x - previous.x;
      const dy = y - previous.y;
      totalDragDistance += Math.abs(dx) + Math.abs(dy);

      const deltaY = dx * 0.0035;
      const deltaX = dy * 0.0035;
      globeGroup.rotation.y += deltaY;
      globeGroup.rotation.x += deltaX;
      globeGroup.rotation.x = Math.max(-1.45, Math.min(1.45, globeGroup.rotation.x));
      velocityX = velocityX * 0.3 + deltaY * 0.7;
      velocityY = velocityY * 0.3 + deltaX * 0.7;
      previous = { x, y };
    };

    const endDrag = () => {
      if (!isDragging) return;
      isDragging = false;
      setIsTuning(false);

      if (totalDragDistance < 6 && isPlannerOpenRef.current) {
        const target = hoverRef.current;
        if (target?.kind === 'route') {
          const route = routesRef.current.find((r) => r.id === target.id);
          if (route) {
            plannerActionsRef.current.startFlight(route);
          }
          return;
        }
        if (target?.kind === 'city') {
          const city = CITIES.find((c) => c.code === target.code);
          if (city) {
            plannerActionsRef.current.pickCity(city);
          }
          return;
        }
      }

      if (isFreeSpin() || totalDragDistance < 6) {
        return;
      }
      settlePending = true;
    };

    const pointer = { x: 0, y: 0, inside: false };
    function updatePointer(clientX: number, clientY: number) {
      const rect = container.getBoundingClientRect();
      pointer.x = clientX - rect.left;
      pointer.y = clientY - rect.top;
      pointer.inside =
        pointer.x >= 0 && pointer.y >= 0 && pointer.x <= rect.width && pointer.y <= rect.height;
    }

    const _v = new THREE.Vector3();
    const _n = new THREE.Vector3();
    const _c = new THREE.Vector3();
    const project = (local: THREE.Vector3) => {
      _v.copy(local).applyMatrix4(globeGroup.matrixWorld);
      _n.copy(_v).normalize();
      const facing = _n.dot(_c.copy(camera.position).sub(_v).normalize());
      _v.project(camera);
      const w = container.clientWidth;
      const h = container.clientHeight;
      return { x: ((_v.x + 1) / 2) * w, y: ((1 - _v.y) / 2) * h, front: facing > -0.08 };
    };

    const distToSegment = (px: number, py: number, ax: number, ay: number, bx: number, by: number) => {
      const dx = bx - ax;
      const dy = by - ay;
      const len2 = dx * dx + dy * dy;
      const k = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
      return Math.hypot(px - (ax + k * dx), py - (ay + k * dy));
    };

    const pickTarget = (): HoverTarget | null => {
      if (!pointer.inside || isDragging) return null;

      let best: HoverTarget | null = null;
      let bestD = Infinity;

      if (!isPlannerOpenRef.current) {
        if (!isFlightModeRef.current) return null;
        sightMarkersRef.current.forEach((m, id) => {
          const p = project(m.tip);
          if (!p.front) return;
          const d = Math.hypot(p.x - pointer.x, p.y - pointer.y);
          const reach = m.onRoute ? 16 : 10;
          if (d < reach && d < bestD) {
            bestD = d;
            best = { kind: 'sight', id };
          }
        });
        return best;
      }

      if (plannerModeRef.current === 'custom') {
        for (const c of cityPointsRef.current) {
          const p = project(c.pos);
          if (!p.front) continue;
          const d = Math.hypot(p.x - pointer.x, p.y - pointer.y);
          if (d < 12 && d < bestD) {
            bestD = d;
            best = { kind: 'city', code: c.code };
          }
        }
        return best;
      }

      plannerArcsRef.current.forEach((arc, id) => {
        const pts = arc.points;
        let prev = project(pts[0]);
        for (let i = 2; i < pts.length; i += 2) {
          const cur = project(pts[i]);
          if (prev.front && cur.front) {
            const d = distToSegment(pointer.x, pointer.y, prev.x, prev.y, cur.x, cur.y);
            if (d < 10 && d < bestD) {
              bestD = d;
              best = { kind: 'route', id };
            }
          }
          prev = cur;
        }
      });
      return best;
    };

    const onPointerLeave = () => {
      pointer.inside = false;
    };
    container.addEventListener('mouseleave', onPointerLeave);

    const onMouseDown = (e: MouseEvent) => startDrag(e.clientX, e.clientY);
    const onMouseMove = (e: MouseEvent) => {
      updatePointer(e.clientX, e.clientY);
      moveDrag(e.clientX, e.clientY);
    };
    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) startDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length === 1) moveDrag(e.touches[0].clientX, e.touches[0].clientY);
    };

    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', endDrag);
    container.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('touchend', endDrag);

    const handleResize = () => {
      const w = container.clientWidth || 500;
      const h = container.clientHeight || 420;
      camera.aspect = w / h;
      fitCamera(w, h);
      if (viewShift !== 0) camera.setViewOffset(w, h, -viewShift, 0, w, h);
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      updatePointScale();
    };
    window.addEventListener('resize', handleResize);

    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    let animationFrameId: number;
    let t = 0;
    let viewShift = 0;
    let tilt = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      t += 0.006;

      currentZoom += (targetZoom - currentZoom) * 0.12;
      const wantTilt =
        isFlightModeRef.current && followCameraRef.current && !isPlannerOpenRef.current ? 1 : 0;
      tilt += (wantTilt - tilt) * 0.05;
      if (Math.abs(wantTilt - tilt) < 0.001) tilt = wantTilt;
      const camDist = baseDist * currentZoom;
      const altitude = camDist - RADIUS;
      camera.position.set(0, -tilt * altitude * 0.7, camDist - tilt * altitude * 0.18);
      camera.lookAt(0, tilt * RADIUS * 0.08, tilt * RADIUS);

      const cw = container.clientWidth;
      const ch = container.clientHeight;
      const wantShift = isPlannerOpenRef.current && cw > 720 ? 170 : 0;
      if (Math.abs(wantShift - viewShift) > 0.3 || (viewShift !== 0 && wantShift === 0)) {
        viewShift += (wantShift - viewShift) * 0.1;
        if (Math.abs(viewShift) < 0.5 && wantShift === 0) {
          viewShift = 0;
          camera.clearViewOffset();
        } else {
          camera.setViewOffset(cw, ch, -viewShift, 0, cw, ch);
        }
      }

      if (isFlightModeRef.current && followCameraRef.current && !isPlannerOpenRef.current) {
        velocityX = 0;
        velocityY = 0;
        targetRotationRef.current = null;
      }

      if (targetRotationRef.current && !isDragging) {
        const dy = targetRotationRef.current.y - globeGroup.rotation.y;
        const dx = targetRotationRef.current.x - globeGroup.rotation.x;
        globeGroup.rotation.y += dy * 0.08;
        globeGroup.rotation.x += dx * 0.08;
        if (Math.abs(dy) < 0.0004 && Math.abs(dx) < 0.0004) {
          globeGroup.rotation.y = targetRotationRef.current.y;
          globeGroup.rotation.x = targetRotationRef.current.x;
          targetRotationRef.current = null;
          setIsTuning(false);
        }
      } else if (!isDragging && (Math.abs(velocityX) > 0.0001 || Math.abs(velocityY) > 0.0001)) {
        globeGroup.rotation.y += velocityX;
        globeGroup.rotation.x += velocityY;
        globeGroup.rotation.x = Math.max(-1.45, Math.min(1.45, globeGroup.rotation.x));
        velocityX *= 0.95;
        velocityY *= 0.95;
      }

      if (settlePending && !isDragging && !targetRotationRef.current) {
        if (isFreeSpin()) {
          settlePending = false;
        } else if (Math.hypot(velocityX, velocityY) < 0.002) {
          settleOnNearest();
        }
      }

      stationLayer.visible = !isFlightModeRef.current && !isPlannerOpenRef.current;
      sightLayer.visible = isFlightModeRef.current && !isPlannerOpenRef.current;

      if (isPlannerOpenRef.current && plannerArcsRef.current.size > 0) {
        plannerRevealRef.current = Math.min(1, plannerRevealRef.current + 0.022);
        const reveal = 1 - Math.pow(1 - plannerRevealRef.current, 3);
        const hovered = hoveredRouteRef.current?.id ?? null;
        plannerArcsRef.current.forEach((arc, id) => {
          const target = hovered === id || plannerModeRef.current === 'custom' ? 1 : 0;
          arc.hover += (target - arc.hover) * 0.15;
          arc.mat.uniforms.uHover.value = arc.hover;
          arc.mat.uniforms.uTime.value = t * 1.6;
          arc.mat.uniforms.uReveal.value = reveal;
          const dim = hovered != null && hovered !== id ? 0.35 : 1;
          arc.mat.uniforms.uDim.value += (dim - arc.mat.uniforms.uDim.value) * 0.15;
        });
      }

      const picked = pickTarget();
      if (!sameTarget(picked, hoverRef.current)) {
        const prevHover = hoverRef.current;
        hoverRef.current = picked;
        setHoverTarget(picked);
        if (picked?.kind === 'route') {
          plannerActionsRef.current.setHoveredRoute({ id: picked.id, source: 'globe' });
        } else if (prevHover?.kind === 'route' && hoveredRouteRef.current?.source === 'globe') {
          plannerActionsRef.current.setHoveredRoute(null);
        }
        container.style.cursor =
          picked && (picked.kind === 'route' || picked.kind === 'city') ? 'pointer' : '';
      }
      if (tooltipRef.current && picked) {
        const w = container.clientWidth;
        const flip = pointer.x > w - 330;
        const tx = flip ? pointer.x - 16 : pointer.x + 18;
        tooltipRef.current.style.transform =
          'translate(' + tx + 'px, ' + (pointer.y + 18) + 'px)' + (flip ? ' translateX(-100%)' : '');
      }

      if (isFlightModeRef.current) {
        beacon.visible = false;
      }

      const pulseOrigin = landMat.uniforms.uPulseOrigin.value as THREE.Vector3[];
      const pulseStrength = landMat.uniforms.uPulseStrength.value as number[];
      landMat.uniforms.uPulseTime.value = t;
      const stationOn = stationLayer.visible && beacon.visible;
      pulseStrength[0] = stationOn ? 1 : 0;
      if (stationOn) pulseOrigin[0].copy(beacon.position).normalize();
      pulseStrength[1] = 0;
      const route = isFlightModeRef.current ? activeRouteRef.current : null;
      pulseStrength[2] = route ? 0.8 : 0;
      pulseStrength[3] = route ? 0.8 : 0;
      if (route) {
        pulseOrigin[2].copy(toVector(route.origin.latitude, route.origin.longitude, 1));
        pulseOrigin[3].copy(toVector(route.destination.latitude, route.destination.longitude, 1));
      }

      if (
        isFlightModeRef.current &&
        activeRouteRef.current &&
        airplaneRef.current &&
        arcPointsRef.current.length > 1
      ) {
        const tFrac = Math.max(0, Math.min(1, flightProgressRef.current / 100));
        const points = arcPointsRef.current;
        const N = points.length - 1;
        const exactIndex = tFrac * N;
        const i0 = Math.floor(exactIndex);
        const i1 = Math.min(N, i0 + 1);
        const subFrac = exactIndex - i0;

        const p0 = points[i0];
        const p1 = points[i1];
        const curPos = new THREE.Vector3().lerpVectors(p0, p1, subFrac);

        const futureIndex = Math.min(N, exactIndex + 0.4);
        const fi0 = Math.floor(futureIndex);
        const fi1 = Math.min(N, fi0 + 1);
        const fSubFrac = futureIndex - fi0;
        const futurePos = new THREE.Vector3().lerpVectors(points[fi0], points[fi1], fSubFrac);

        airplaneRef.current.position.copy(curPos);
        airplaneRef.current.visible = true;

        const forward = futurePos.clone().sub(curPos).normalize();
        const up = curPos.clone().normalize();
        let right = new THREE.Vector3(1, 0, 0);
        let realUp = new THREE.Vector3(0, 1, 0);
        if (forward.lengthSq() > 0.0001) {
          right = new THREE.Vector3().crossVectors(up, forward).normalize();
          realUp = new THREE.Vector3().crossVectors(forward, right).normalize();
          const mat = new THREE.Matrix4().makeBasis(right, realUp, forward);
          airplaneRef.current.quaternion.setFromRotationMatrix(mat);
        }

        if (flightTrajectoryMeshRef.current) {
          const mat = flightTrajectoryMeshRef.current.material as THREE.ShaderMaterial;
          if (mat.uniforms) {
            mat.uniforms.uProgress.value = tFrac;
            mat.uniforms.uTime.value = t;
          }
        }

        if (followCameraRef.current && !isPlannerOpenRef.current && currentCoordsRef.current) {
          const target = getTargetRotation(
            currentCoordsRef.current.lat,
            currentCoordsRef.current.lon,
            globeGroup.rotation.y
          );
          globeGroup.rotation.y += (target.y - globeGroup.rotation.y) * 0.055;
          globeGroup.rotation.x += (target.x - globeGroup.rotation.x) * 0.055;
        }
      } else {
        if (airplaneRef.current) airplaneRef.current.visible = false;
      }

      if (isFlightModeRef.current && arcPointsRef.current.length > 1) {
        const pts = arcPointsRef.current;
        pinProgressRef.current.forEach((progress, id) => {
          const anchor = pointAlong(pts, progress / 100, _anchor);
          anchor.multiplyScalar(1 + 0.6 / anchor.length());
          const p = project(anchor);
          const visible = p.front && !isPlannerOpenRef.current;
          flightOverlay.pins.set(id, { x: p.x, y: p.y, visible });
          const el = pinElsRef.current.get(id);
          if (el) {
            el.style.transform = 'translate(' + p.x.toFixed(1) + 'px, ' + p.y.toFixed(1) + 'px)';
            el.style.opacity = visible ? '1' : '0';
          }
        });
        if (airplaneRef.current) {
          const p = project(airplaneRef.current.position);
          flightOverlay.plane = { x: p.x, y: p.y, visible: p.front };
        }
      }

      renderer.render(scene, camera);
    };
    const _anchor = new THREE.Vector3();
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousedown', onMouseDown);
      container.removeEventListener('mouseleave', onPointerLeave);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', endDrag);
      container.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', endDrag);
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('resize', handleResize);
      observer.disconnect();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (!stationPinsGroupRef.current) return;
    const group = stationPinsGroupRef.current;
    group.clear();
    if (stations.length === 0) return;

    const sun = solarPosition(new Date());
    const mesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.72, 8, 8),
      new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.9 }),
      stations.length
    );

    const dummy = new THREE.Object3D();
    const night = new THREE.Color(0xffc670);
    const day = new THREE.Color(0x63d3f2);
    let n = 0;

    stations.forEach((st) => {
      const c = stationCoords(st);
      if (!c) return;
      dummy.position.copy(toVector(c.lat, c.lon, RADIUS + 0.6));
      const isNight = isNightAt(c.lat, c.lon, sun);
      dummy.scale.setScalar(isNight ? 1.3 : 0.85);
      dummy.updateMatrix();
      mesh.setMatrixAt(n, dummy.matrix);
      mesh.setColorAt(n, isNight ? night : day);
      n++;
    });

    mesh.count = n;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    group.add(mesh);
  }, [stations, sunTick]);

  useEffect(() => {
    const beacon = beaconRef.current;
    if (!beacon) return;

    if (isFlightModeRef.current) {
      beacon.visible = false;
      return;
    }

    const c = currentStation ? stationCoords(currentStation) : null;
    if (!c) {
      beacon.visible = false;
      return;
    }

    const p = toVector(c.lat, c.lon);
    beacon.position.copy(p);
    beacon.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p.clone().normalize());
    beacon.visible = true;

    const isNewStation = currentStation?.id !== prevStationIdRef.current;
    prevStationIdRef.current = currentStation?.id ?? null;

    if (isManualTuningRef.current) {
      isManualTuningRef.current = false;
      return;
    }

    if (isNewStation && globeGroupRef.current) {
      targetRotationRef.current = getTargetRotation(
        c.lat,
        c.lon,
        globeGroupRef.current.rotation.y
      );
    }
  }, [currentStation]);

  useEffect(() => {
    const flightGroup = flightGroupRef.current;
    if (!flightGroup) return;

    if (flightTrajectoryMeshRef.current) {
      flightGroup.remove(flightTrajectoryMeshRef.current);
      flightTrajectoryMeshRef.current.geometry.dispose();
      if (Array.isArray(flightTrajectoryMeshRef.current.material)) {
        flightTrajectoryMeshRef.current.material.forEach((m) => m.dispose());
      } else {
        flightTrajectoryMeshRef.current.material.dispose();
      }
      flightTrajectoryMeshRef.current = null;
    }
    if (originMarkerRef.current) {
      flightGroup.remove(originMarkerRef.current);
      originMarkerRef.current = null;
    }
    if (destMarkerRef.current) {
      flightGroup.remove(destMarkerRef.current);
      destMarkerRef.current = null;
    }

    if (!isFlightMode || !activeRoute) {
      if (airplaneRef.current) airplaneRef.current.visible = false;
      arcPointsRef.current = [];
      if (beaconRef.current && currentStationRef.current) {
        const c = stationCoords(currentStationRef.current);
        if (c) {
          const p = toVector(c.lat, c.lon);
          beaconRef.current.position.copy(p);
          beaconRef.current.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p.clone().normalize());
          beaconRef.current.visible = true;
        }
      }
      return;
    }

    if (beaconRef.current) {
      beaconRef.current.visible = false;
    }

    const N = 120;
    const points: THREE.Vector3[] = [];
    for (let i = 0; i <= N; i++) {
      const frac = i / N;
      const { lat, lon } = slerpLatLon(
        activeRoute.origin.latitude,
        activeRoute.origin.longitude,
        activeRoute.destination.latitude,
        activeRoute.destination.longitude,
        frac
      );
      const alt = calculateFlightAltitude(4.2, frac);
      points.push(toVector(lat, lon, RADIUS + 0.25 + alt));
    }
    arcPointsRef.current = points;

    const trajectoryGeo = buildRibbonGeometry(points, 0.75);
    let arcLength = 0;
    for (let i = 1; i < points.length; i++) arcLength += points[i].distanceTo(points[i - 1]);

    const trajectoryMat = new THREE.ShaderMaterial({
      uniforms: {
        uProgress: { value: flightProgressRef.current },
        uTime: { value: 0.0 },
        uColorFlown: { value: new THREE.Color(0x38bdf8) },
        uColorRemaining: { value: new THREE.Color(0x63d3f2) },
        uLength: { value: arcLength },
      },
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float uProgress;
        uniform float uTime;
        uniform float uLength;
        uniform vec3 uColorFlown;
        uniform vec3 uColorRemaining;
        varying vec2 vUv;

        float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
        float noise(vec2 p) {
          vec2 i = floor(p);
          vec2 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                     mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
        }

        void main() {
          float e = abs(vUv.y - 0.5) * 2.0;

          if (vUv.x > uProgress) {
            float line = 1.0 - smoothstep(0.03, 0.09, e);
            gl_FragColor = vec4(uColorRemaining, line * 0.22);
            return;
          }

          float dist = (uProgress - vUv.x) * uLength;
          float age = clamp(dist / 24.0, 0.0, 1.0);
          float width = mix(0.1, 1.0, pow(age, 0.6));
          float n = noise(vec2(vUv.x * uLength * 0.9 - uTime * 0.8, vUv.y * 6.0));
          float body = 1.0 - smoothstep(width * 0.4, width, e);
          float fade = mix(1.0, 0.16, age);
          float spine = (1.0 - smoothstep(0.0, 0.06, e)) * 0.25;
          vec3 col = mix(vec3(1.0), uColorFlown, age * 0.7);
          gl_FragColor = vec4(col, body * fade * (0.55 + 0.45 * n) * 0.9 + spine);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });

    const trajectoryMesh = new THREE.Mesh(trajectoryGeo, trajectoryMat);
    flightGroup.add(trajectoryMesh);
    flightTrajectoryMeshRef.current = trajectoryMesh;

    const origMarker = createAirportMarker(activeRoute.origin.iata_code, false);
    const origPos = toVector(activeRoute.origin.latitude, activeRoute.origin.longitude, RADIUS + 0.1);
    origMarker.position.copy(origPos);
    origMarker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), origPos.clone().normalize());
    flightGroup.add(origMarker);
    originMarkerRef.current = origMarker;

    const destMarker = createAirportMarker(activeRoute.destination.iata_code, true);
    const destPos = toVector(activeRoute.destination.latitude, activeRoute.destination.longitude, RADIUS + 0.1);
    destMarker.position.copy(destPos);
    destMarker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), destPos.clone().normalize());
    flightGroup.add(destMarker);
    destMarkerRef.current = destMarker;

    if (airplaneRef.current) {
      airplaneRef.current.visible = true;
    }

    if (globeGroupRef.current) {
      targetRotationRef.current = getTargetRotation(
        activeRoute.origin.latitude,
        activeRoute.origin.longitude,
        globeGroupRef.current.rotation.y
      );
    }
  }, [isFlightMode, activeRoute]);

  useEffect(() => {
    const group = plannerGroupRef.current;
    if (!group) return;

    group.traverse((obj) => {
      const o = obj as THREE.Mesh;
      if (o.geometry) o.geometry.dispose();
      const m = o.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(m)) m.forEach((x) => x.dispose());
      else if (m) {
        (m as any).map?.dispose?.();
        m.dispose();
      }
    });
    group.clear();
    plannerArcsRef.current.clear();
    cityPointsRef.current = [];
    if (!isPlannerOpen) {
      plannerRevealRef.current = 0;
      return;
    }

    const addArc = (id: number, route: { origin: any; destination: any }, color: number) => {
      const pts = buildLiftedArc(
        route.origin.latitude,
        route.origin.longitude,
        route.destination.latitude,
        route.destination.longitude
      );
      let len = 0;
      for (let i = 1; i < pts.length; i++) len += pts[i].distanceTo(pts[i - 1]);
      const mat = createPlannerArcMaterial(color, Math.max(1.5, len / 30));
      const mesh = new THREE.Mesh(buildRibbonGeometry(pts, 0.55), mat);
      mesh.renderOrder = 2;
      group.add(mesh);
      plannerArcsRef.current.set(id, { mesh, mat, points: pts, hover: 0 });
    };

    const addAirport = (code: string, lat: number, lon: number, color: number, withLabel: boolean) => {
      const p = toVector(lat, lon, RADIUS + 0.3);
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.55, 12, 12),
        new THREE.MeshBasicMaterial({ color })
      );
      dot.position.copy(p);
      group.add(dot);
      if (withLabel) {
        const label = createCodeSprite(code, '#' + color.toString(16).padStart(6, '0'));
        label.position.copy(toVector(lat, lon, RADIUS + 2.4));
        group.add(label);
      }
    };

    if (plannerMode === 'routes') {
      const seen = new Set<string>();
      routes.forEach((r) => {
        addArc(r.id, r, 0x63d3f2);
        [r.origin, r.destination].forEach((a) => {
          if (seen.has(a.iata_code)) return;
          seen.add(a.iata_code);
          addAirport(a.iata_code, a.latitude, a.longitude, 0xe8e3d8, true);
        });
      });
    } else {
      const dotGeo = new THREE.SphereGeometry(0.5, 10, 10);
      const dots = new THREE.InstancedMesh(
        dotGeo,
        new THREE.MeshBasicMaterial({ color: 0xe8e3d8, transparent: true, opacity: 0.75 }),
        CITIES.length
      );
      const dummy = new THREE.Object3D();
      CITIES.forEach((c, i) => {
        const pos = toVector(c.lat, c.lon, RADIUS + 0.3);
        dummy.position.copy(pos);
        const selected = c.code === customFrom?.code || c.code === customTo?.code;
        dummy.scale.setScalar(selected ? 0 : 1);
        dummy.updateMatrix();
        dots.setMatrixAt(i, dummy.matrix);
        cityPointsRef.current.push({ code: c.code, pos });
      });
      dots.instanceMatrix.needsUpdate = true;
      group.add(dots);

      if (customFrom) {
        const m = createAirportMarker(customFrom.code, false);
        const pos = toVector(customFrom.lat, customFrom.lon, RADIUS + 0.1);
        m.position.copy(pos);
        m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pos.clone().normalize());
        group.add(m);
      }
      if (customTo) {
        const m = createAirportMarker(customTo.code, true);
        const pos = toVector(customTo.lat, customTo.lon, RADIUS + 0.1);
        m.position.copy(pos);
        m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pos.clone().normalize());
        group.add(m);
      }
      if (draftRoute) {
        addArc(draftRoute.id, draftRoute, 0xffb347);
        plannerRevealRef.current = 0;
      }
    }

    if (plannerMode === 'custom' && globeGroupRef.current) {
      const focus = draftRoute
        ? slerpLatLon(
            draftRoute.origin.latitude,
            draftRoute.origin.longitude,
            draftRoute.destination.latitude,
            draftRoute.destination.longitude,
            0.5
          )
        : customFrom
          ? { lat: customFrom.lat, lon: customFrom.lon }
          : null;
      if (focus) {
        targetRotationRef.current = getTargetRotation(focus.lat, focus.lon, globeGroupRef.current.rotation.y);
      }
    }
  }, [isPlannerOpen, plannerMode, routes, draftRoute, customFrom, customTo]);

  useEffect(() => {
    const onRoute = new Set(routeLandmarks.map((rl) => rl.landmark.id));
    const taken = new Set(capturedLandmarks.map((rl) => rl.landmark.id));
    sightMarkersRef.current.forEach((m, id) => {
      const r = onRoute.has(id);
      const c = taken.has(id) && id !== developingLandmarkId;
      if (m.onRoute !== r || m.isCaptured !== c) styleSightMarker(m, r, c);
    });
    pinProgressRef.current = new Map(capturedLandmarks.map((rl) => [rl.landmark.id, rl.progress]));
    flightOverlay.pins.forEach((_, id) => {
      if (!pinProgressRef.current.has(id)) flightOverlay.pins.delete(id);
    });
  }, [routeLandmarks, capturedLandmarks, developingLandmarkId]);

  useEffect(() => {
    if (!isPlannerOpen || !globeGroupRef.current) return;
    targetRotationRef.current = getTargetRotation(38, 25, globeGroupRef.current.rotation.y);
  }, [isPlannerOpen]);

  useEffect(() => {
    if (!isPlannerOpen || !hoveredRoute || hoveredRoute.source !== 'list') return;
    const r = routes.find((x) => x.id === hoveredRoute.id);
    if (!r || !globeGroupRef.current) return;
    const mid = slerpLatLon(
      r.origin.latitude,
      r.origin.longitude,
      r.destination.latitude,
      r.destination.longitude,
      0.5
    );
    targetRotationRef.current = getTargetRotation(mid.lat, mid.lon, globeGroupRef.current.rotation.y);
  }, [hoveredRoute, isPlannerOpen, routes]);

  const tooltipRoute =
    hoverTarget?.kind === 'route' ? routes.find((r) => r.id === hoverTarget.id) ?? null : null;
  const tooltipCity =
    hoverTarget?.kind === 'city' ? CITIES.find((c) => c.code === hoverTarget.code) ?? null : null;
  const tooltipSight =
    hoverTarget?.kind === 'sight' ? LANDMARKS.find((l) => l.id === hoverTarget.id) ?? null : null;
  const tooltipSightOnRoute = tooltipSight
    ? routeLandmarks.find((rl) => rl.landmark.id === tooltipSight.id) ?? null
    : null;
  const tooltipSights = React.useMemo(
    () => (tooltipRoute ? landmarksAlongRoute(tooltipRoute) : []),
    [tooltipRoute]
  );

  return (
    <>
      <div
        ref={containerRef}
        className={`stage-canvas${isFlightMode && followCamera ? ' is-follow-camera' : ''}`}
      />

      <div className="pin-layer" aria-hidden={capturedLandmarks.length === 0}>
        {isFlightMode &&
          capturedLandmarks.map((rl, i) => (
            <PhotoPin
              key={rl.landmark.id}
              rl={rl}
              side={i % 2 === 0 ? 'l' : 'r'}
              tier={Math.floor(i / 2) % 3}
              waiting={rl.landmark.id === developingLandmarkId}
              ref={(el) => {
                if (el) pinElsRef.current.set(rl.landmark.id, el);
                else pinElsRef.current.delete(rl.landmark.id);
              }}
            />
          ))}
      </div>

      {(tooltipRoute || tooltipCity || tooltipSight) && (
        <div ref={tooltipRef} className="globe-tip" role="tooltip">
          {tooltipRoute && (
            <>
              <div className="globe-tip-head">
                <span className="num globe-tip-flight">{tooltipRoute.flight_number}</span>
                <span>{tooltipRoute.airline}</span>
              </div>
              <div className="globe-tip-codes num">
                <span>{tooltipRoute.origin.iata_code}</span>
                <span className="globe-tip-line" />
                <span className="is-dest">{tooltipRoute.destination.iata_code}</span>
              </div>
              <div className="globe-tip-cities">
                <span>{tooltipRoute.origin.city}</span>
                <span>{tooltipRoute.destination.city}</span>
              </div>
              <div className="globe-tip-stats">
                <span className="num">{formatKm(tooltipRoute.distance_km)}</span>
                <span className="num">{formatDuration(tooltipRoute.real_duration_minutes)}</span>
                <span className="num">{tooltipSights.length} снимков</span>
              </div>
              {tooltipRoute.description && <p className="globe-tip-desc">{tooltipRoute.description}</p>}
              <div className="globe-tip-cta">Нажмите, чтобы взлететь</div>
            </>
          )}
          {tooltipSight && (
            <>
              <div className="globe-tip-head">
                <span className={`globe-tip-kind is-${tooltipSight.kind}`}>
                  {tooltipSight.kind === 'scenic' ? 'Живописное место' : 'Достопримечательность'}
                </span>

              </div>
              <div className="globe-tip-title">{tooltipSight.name}</div>
              <div className="globe-tip-cities">
                <span>{tooltipSight.caption}</span>
              </div>
              {tooltipSightOnRoute && activeRoute && tooltipSightOnRoute.progress > flightProgress && (
                <div className="globe-tip-cta">
                  {'Снимок через ' +
                    formatClock(
                      ((tooltipSightOnRoute.progress - flightProgress) / 100) *
                        activeRoute.real_duration_minutes
                    )}
                </div>
              )}
            </>
          )}
          {tooltipCity && (
            <>
              <div className="globe-tip-head">
                <span className="num globe-tip-flight">{tooltipCity.code}</span>
                <span>{tooltipCity.country}</span>
              </div>
              <div className="globe-tip-title">{tooltipCity.name}</div>
              <div className="globe-tip-cta">
                {!customFrom || customTo ? 'Клик — город вылета' : 'Клик — город прилёта'}
              </div>
            </>
          )}
        </div>
      )}

      {!isFlightMode && !isPlannerOpen && (
        <div
          className={`needle${isTuning ? ' is-tuning' : ''}`}
          aria-hidden="true"
        >
          <svg width="120" height="120" viewBox="-60 -60 120 120">
            <line className="needle-line" x1="0" y1="-58" x2="0" y2="-20" />
            <line className="needle-line" x1="0" y1="20" x2="0" y2="58" />
            <path className="needle-bracket" d="M -20 -11 L -20 -20 L -11 -20" />
            <path className="needle-bracket" d="M 11 -20 L 20 -20 L 20 -11" />
            <path className="needle-bracket" d="M 20 11 L 20 20 L 11 20" />
            <path className="needle-bracket" d="M -11 20 L -20 20 L -20 11" />
          </svg>
        </div>
      )}
    </>
  );
};
