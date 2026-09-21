import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { usePlayer } from '../context/PlayerContext';
import { RadioStation } from '../types';

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

/** Surface point for a lat/lon, in the globe's local frame. */
const toVector = (lat: number, lon: number, r = RADIUS) => {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(r * Math.sin(phi) * Math.cos(theta)),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
};

/** Subsolar point for a moment — drives the terminator and the lit pins. */
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

export const Globe: React.FC<GlobeProps> = ({ stations = [] }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { currentStation, playStation } = usePlayer();

  const [geoData, setGeoData] = useState<any | null>(null);
  const [isTuning, setIsTuning] = useState(false);
  const [sunTick, setSunTick] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textureRef = useRef<THREE.CanvasTexture | null>(null);
  const globeGroupRef = useRef<THREE.Group | null>(null);
  const targetRotationRef = useRef<{ x: number; y: number } | null>(null);
  const beaconRef = useRef<THREE.Group | null>(null);
  const stationPinsGroupRef = useRef<THREE.Group | null>(null);
  const updateSunRef = useRef<() => void>(() => {});

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

  // The land is drawn as a dot matrix rather than filled shapes: continents
  // read as a grid of emitters, which is what the sphere is — a map of
  // transmitters. Rendered once; the tuned station is marked by the beacon, so
  // nothing here needs redrawing when the station changes.
  useEffect(() => {
    if (!geoData) return;

    const W = 2048;
    const H = 1024;

    // 1. Land mask, offscreen
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

    // 2. Paint the sphere texture
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

    // Graticule: only lines that mean something, drawn under the dots
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

    // Dot matrix over the land mask. Spacing shrinks toward the poles so the
    // equirectangular stretch does not smear the dots into lines.
    const STEP = 6;
    ctx.fillStyle = '#dfe9ee';
    for (let y = 0; y < H; y += STEP) {
      const lat = 90 - (y / H) * 180;
      const lonStep = Math.min(STEP / Math.max(Math.cos((lat * Math.PI) / 180), 0.08), STEP * 8);
      for (let x = 0; x < W; x += lonStep) {
        const idx = (y * W + Math.floor(x)) * 4;
        if (maskData[idx] > 127) {
          ctx.fillRect(Math.floor(x), y, 2, 2);
        }
      }
    }

    if (textureRef.current) textureRef.current.needsUpdate = true;
  }, [geoData]);

  // Scene
  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const width = container.clientWidth || 500;
    const height = container.clientHeight || 420;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 2000);

    // Fit the sphere to the narrower axis, or it is cropped on a phone.
    const fitCamera = (w: number, h: number) => {
      const halfFov = (camera.fov * Math.PI) / 180 / 2;
      const distForHeight = (RADIUS * 1.28) / Math.tan(halfFov);
      camera.position.z = Math.max(distForHeight, distForHeight / (w / h));
    };
    fitCamera(width, height);

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

    // Sphere. Emissive through the same map keeps the night hemisphere alive
    // as a field of cold lights instead of a black hole.
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, 96, 96),
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

    // Fresnel halo: the atmosphere seen edge-on, brightest at the limb.
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

    // Starfield, so the surround has depth instead of flat black
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

    const stationPinsGroup = new THREE.Group();
    globeGroup.add(stationPinsGroup);
    stationPinsGroupRef.current = stationPinsGroup;

    // Beacon: the tuned station throws a shaft of light off the surface, with
    // rings running out from its foot.
    const beacon = new THREE.Group();
    beacon.visible = false;
    globeGroup.add(beacon);
    beaconRef.current = beacon;

    const beamHeight = 34;
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.6, 2.4, beamHeight, 24, 1, true),
      new THREE.ShaderMaterial({
        uniforms: { uColor: { value: new THREE.Color(0xffb347) } },
        vertexShader: `
          varying float vH;
          void main() {
            vH = uv.y;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 uColor;
          varying float vH;
          void main() {
            gl_FragColor = vec4(uColor, (1.0 - vH) * 0.55);
          }
        `,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
    );
    beam.position.y = beamHeight / 2;
    beacon.add(beam);

    const core = new THREE.Mesh(
      new THREE.SphereGeometry(2.1, 20, 20),
      new THREE.MeshBasicMaterial({ color: 0xffc670 })
    );
    beacon.add(core);

    const rings: THREE.Mesh[] = [];
    for (let i = 0; i < 2; i++) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(4.4, 4.9, 56),
        new THREE.MeshBasicMaterial({
          color: 0xffb347,
          side: THREE.DoubleSide,
          transparent: true,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
      );
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.4;
      beacon.add(ring);
      rings.push(ring);
    }

    // Real-time solar lighting, in the globe's frame so the terminator stays
    // over the right longitude while the user spins.
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
    };
    updateSunPosition();
    updateSunRef.current = updateSunPosition;

    // Spin to tune
    let isDragging = false;
    let previous = { x: 0, y: 0 };
    let velocityX = 0;
    let velocityY = 0;
    let totalDragDistance = 0;

    const tuneToCenterStation = () => {
      const g = globeGroupRef.current;
      const candidates = stationsRef.current;
      if (!g || !candidates || candidates.length === 0) return;

      let centerLat = (g.rotation.x * 180) / Math.PI;
      let centerLon = (-(g.rotation.y + Math.PI / 2) * 180) / Math.PI;
      centerLon = (((centerLon + 180) % 360) + 360) % 360 - 180;
      centerLat = Math.max(-85, Math.min(85, centerLat));

      let closest: RadioStation | null = null;
      let minDistance = Infinity;

      for (const st of candidates) {
        const c = stationCoords(st);
        if (!c) continue;
        const dLat = c.lat - centerLat;
        let dLon = Math.abs(c.lon - centerLon);
        if (dLon > 180) dLon = 360 - dLon;
        const dist = dLat * dLat + dLon * dLon;
        if (dist < minDistance) {
          minDistance = dist;
          closest = st;
        }
      }

      if (closest && closest.id !== currentStationRef.current?.id) {
        playStationRef.current(closest);
      }
    };

    const startDrag = (x: number, y: number) => {
      isDragging = true;
      setIsTuning(true);
      targetRotationRef.current = null;
      previous = { x, y };
      velocityX = 0;
      velocityY = 0;
      totalDragDistance = 0;
    };

    const moveDrag = (x: number, y: number) => {
      if (!isDragging) return;
      const dx = x - previous.x;
      const dy = y - previous.y;
      totalDragDistance += Math.abs(dx) + Math.abs(dy);

      globeGroup.rotation.y += dx * 0.006;
      globeGroup.rotation.x += dy * 0.006;
      globeGroup.rotation.x = Math.max(-1.1, Math.min(1.1, globeGroup.rotation.x));

      velocityX = dx * 0.006;
      velocityY = dy * 0.006;
      previous = { x, y };
    };

    const endDrag = () => {
      if (!isDragging) return;
      isDragging = false;
      setIsTuning(false);
      if (totalDragDistance > 20) tuneToCenterStation();
    };

    const onMouseDown = (e: MouseEvent) => startDrag(e.clientX, e.clientY);
    const onMouseMove = (e: MouseEvent) => moveDrag(e.clientX, e.clientY);
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
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // The stage is a flexible grid row and can resize without the window.
    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    let animationFrameId: number;
    let t = 0;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      t += 0.006;

      if (targetRotationRef.current) {
        globeGroup.rotation.y += (targetRotationRef.current.y - globeGroup.rotation.y) * 0.06;
        globeGroup.rotation.x += (targetRotationRef.current.x - globeGroup.rotation.x) * 0.06;
        if (
          Math.abs(targetRotationRef.current.y - globeGroup.rotation.y) < 0.001 &&
          Math.abs(targetRotationRef.current.x - globeGroup.rotation.x) < 0.001
        ) {
          targetRotationRef.current = null;
        }
      } else if (!isDragging && (Math.abs(velocityX) > 0.0001 || Math.abs(velocityY) > 0.0001)) {
        // Inertia after release only — never any idle self-rotation.
        globeGroup.rotation.y += velocityX;
        globeGroup.rotation.x += velocityY;
        globeGroup.rotation.x = Math.max(-1.1, Math.min(1.1, globeGroup.rotation.x));
        velocityX *= 0.9;
        velocityY *= 0.9;
      }

      if (beacon.visible) {
        rings.forEach((ring, i) => {
          const phase = (t + i * 0.5) % 1;
          const s = 1 + phase * 2.4;
          ring.scale.set(s, s, 1);
          (ring.material as THREE.MeshBasicMaterial).opacity = 0.7 * (1 - phase);
        });
      }

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', endDrag);
      container.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchmove', onTouchMove);
      window.removeEventListener('touchend', endDrag);
      window.removeEventListener('resize', handleResize);
      observer.disconnect();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Pins for every station of the current vibe. Night-side ones burn warm like
  // lit windows; day-side ones sit cool against the sunlit dots.
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

  // Plant the beacon and bring the station under the needle, however the
  // change was made.
  useEffect(() => {
    const beacon = beaconRef.current;
    if (!beacon) return;

    const c = currentStation ? stationCoords(currentStation) : null;
    if (!c) {
      beacon.visible = false;
      return;
    }

    const p = toVector(c.lat, c.lon);
    beacon.position.copy(p);
    // Stand the beacon up along the surface normal.
    beacon.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p.clone().normalize());
    beacon.visible = true;

    targetRotationRef.current = {
      x: (c.lat * Math.PI) / 180,
      y: -(c.lon * Math.PI) / 180 - Math.PI / 2,
    };
  }, [currentStation]);

  return (
    <>
      <div ref={containerRef} className="stage-canvas" />

      {/* The needle. Fixed at centre; the planet turns beneath it. */}
      <div className={`needle${isTuning ? ' is-tuning' : ''}`} aria-hidden="true">
        <svg width="120" height="120" viewBox="-60 -60 120 120">
          <line className="needle-line" x1="0" y1="-58" x2="0" y2="-20" />
          <line className="needle-line" x1="0" y1="20" x2="0" y2="58" />
          <path className="needle-bracket" d="M -20 -11 L -20 -20 L -11 -20" />
          <path className="needle-bracket" d="M 11 -20 L 20 -20 L 20 -11" />
          <path className="needle-bracket" d="M 20 11 L 20 20 L 11 20" />
          <path className="needle-bracket" d="M -11 20 L -20 20 L -20 11" />
        </svg>
      </div>
    </>
  );
};
