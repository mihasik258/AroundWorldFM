import * as THREE from 'three';
import { Landmark } from '../data/landmarks';

type Role = 'body' | 'glow' | 'stem' | 'ring' | 'fill' | 'sglow';
type State = 'normal' | 'dim' | 'captured';

const SKY = 0x63d3f2;
const TEAL = 0x5fe0c1;
const AMBER = 0xffb347;

const basic = (color: number, opacity: number, extra: THREE.MeshBasicMaterialParameters = {}) =>
  new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity, ...extra });

const body = (state: State) =>
  new THREE.MeshStandardMaterial({
    color: state === 'captured' ? 0xffe6c2 : 0xe8e3d8,
    roughness: 0.55,
    metalness: 0.1,
    emissive: state === 'captured' ? 0xb8641a : 0x2a6f84,
    emissiveIntensity: state === 'captured' ? 0.55 : 0.5,
    transparent: state === 'dim',
    opacity: state === 'dim' ? 0.35 : 1,
  });

const MATERIALS: Record<State, Record<Role, THREE.Material>> = {
  normal: {
    body: body('normal'),
    glow: basic(SKY, 1),
    stem: basic(0xe8e3d8, 0.55),
    ring: basic(TEAL, 0.9, { side: THREE.DoubleSide, depthWrite: false }),
    fill: basic(TEAL, 0.12, { side: THREE.DoubleSide, depthWrite: false }),
    sglow: basic(TEAL, 1),
  },
  dim: {
    body: body('dim'),
    glow: basic(SKY, 0.35),
    stem: basic(0xe8e3d8, 0.2),
    ring: basic(TEAL, 0.3, { side: THREE.DoubleSide, depthWrite: false }),
    fill: basic(TEAL, 0.04, { side: THREE.DoubleSide, depthWrite: false }),
    sglow: basic(TEAL, 0.35),
  },
  captured: {
    body: body('captured'),
    glow: basic(AMBER, 1),
    stem: basic(AMBER, 0.6),
    ring: basic(AMBER, 0.95, { side: THREE.DoubleSide, depthWrite: false }),
    fill: basic(AMBER, 0.14, { side: THREE.DoubleSide, depthWrite: false }),
    sglow: basic(AMBER, 1),
  },
};

const DOUBLE: Record<State, Partial<Record<Role, THREE.Material>>> = { normal: {}, dim: {}, captured: {} };
const materialFor = (state: State, role: Role, double: boolean) => {
  if (!double) return MATERIALS[state][role];
  let m = DOUBLE[state][role];
  if (!m) {
    m = MATERIALS[state][role].clone();
    m.side = THREE.DoubleSide;
    DOUBLE[state][role] = m;
  }
  return m;
};

const twoSided = (m: THREE.Mesh) => {
  m.userData.double = true;
  m.material = materialFor('normal', m.userData.role, true);
  return m;
};

const part = (
  geo: THREE.BufferGeometry,
  role: Role = 'body',
  x = 0,
  y = 0,
  z = 0,
  rx = 0,
  ry = 0,
  rz = 0
) => {
  const m = new THREE.Mesh(geo, MATERIALS.normal[role]);
  m.userData.role = role;
  m.position.set(x, y, z);
  m.rotation.set(rx, ry, rz);
  return m;
};

const box = (w: number, h: number, d: number) => new THREE.BoxGeometry(w, h, d);
const frustum = (rTop: number, rBottom: number, h: number, seg = 4) => {
  const g = new THREE.CylinderGeometry(rTop, rBottom, h, seg);
  if (seg === 4) g.rotateY(Math.PI / 4);
  return g;
};
const dome = (r: number) => new THREE.SphereGeometry(r, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2);
const ball = (r: number) => new THREE.SphereGeometry(r, 12, 10);

const stack = (g: THREE.Group, pieces: [THREE.BufferGeometry, number, Role?][], y0 = 0) => {
  let y = y0;
  pieces.forEach(([geo, h, role]) => {
    g.add(part(geo, role ?? 'body', 0, y + h / 2, 0));
    y += h;
  });
  return y;
};

const mosque = (g: THREE.Group, domeR: number, minaretH: number) => {
  g.add(part(box(0.9, 0.06, 0.9), 'body', 0, 0.03, 0));
  g.add(part(box(0.44, 0.28, 0.44), 'body', 0, 0.2, 0));
  const d = part(dome(domeR), 'body', 0, 0.34, 0);
  d.scale.y = 1.25;
  g.add(d);
  g.add(part(frustum(0.004, 0.02, 0.1, 6), 'glow', 0, 0.34 + domeR * 1.25 + 0.05, 0));
  [-1, 1].forEach((sx) =>
    [-1, 1].forEach((sz) => {
      g.add(part(new THREE.CylinderGeometry(0.025, 0.03, minaretH, 8), 'body', sx * 0.38, minaretH / 2, sz * 0.38));
      g.add(part(frustum(0.002, 0.035, 0.08, 8), 'body', sx * 0.38, minaretH + 0.04, sz * 0.38));
    })
  );
};

const MODELS: Record<string, (g: THREE.Group) => void> = {
  eiffel: (g) => {
    stack(g, [
      [frustum(0.13, 0.34, 0.32), 0.32],
      [box(0.3, 0.03, 0.3), 0.03],
      [frustum(0.06, 0.13, 0.32), 0.32],
      [box(0.15, 0.025, 0.15), 0.025],
      [frustum(0.012, 0.06, 0.36), 0.36],
      [ball(0.022), 0.03, 'glow'],
    ]);
  },
  tokyotower: (g) => {
    stack(g, [
      [frustum(0.1, 0.32, 0.36), 0.36],
      [box(0.2, 0.05, 0.2), 0.05],
      [frustum(0.045, 0.1, 0.3), 0.3],
      [box(0.1, 0.03, 0.1), 0.03],
      [frustum(0.006, 0.04, 0.32), 0.32],
      [ball(0.02), 0.03, 'glow'],
    ]);
  },
  giza: (g) => {
    const pyr = (r: number, x: number, z: number) => {
      const c = new THREE.ConeGeometry(r, r * 1.1, 4);
      c.rotateY(Math.PI / 4);
      g.add(part(c, 'body', x, (r * 1.1) / 2, z));
    };
    pyr(0.42, -0.3, -0.2);
    pyr(0.36, 0.28, 0.12);
    pyr(0.2, 0.62, 0.45);
  },
  bigben: (g) => {
    const top = stack(g, [
      [box(0.2, 0.62, 0.2), 0.62],
      [box(0.24, 0.2, 0.24), 0.2],
      [box(0.2, 0.08, 0.2), 0.08],
      [frustum(0.02, 0.15, 0.26), 0.26],
    ]);
    g.add(part(new THREE.CircleGeometry(0.07, 20), 'glow', 0, 0.72, 0.121));
    g.add(part(new THREE.CircleGeometry(0.07, 20), 'glow', 0.121, 0.72, 0, 0, Math.PI / 2));
    g.add(part(ball(0.018), 'glow', 0, top + 0.02, 0));
  },
  liberty: (g) => {
    stack(g, [
      [box(0.46, 0.14, 0.46), 0.14],
      [frustum(0.13, 0.17, 0.28), 0.28],
      [new THREE.CylinderGeometry(0.05, 0.1, 0.34, 10), 0.34],
      [ball(0.05), 0.08],
    ]);
    g.add(part(new THREE.CylinderGeometry(0.018, 0.02, 0.2, 8), 'body', 0.07, 0.86, 0, 0, 0, -0.25));
    g.add(part(ball(0.035), 'glow', 0.1, 0.98, 0));
  },
  christ: (g) => {
    stack(g, [
      [box(0.16, 0.2, 0.16), 0.2],
      [new THREE.CylinderGeometry(0.05, 0.08, 0.46, 10), 0.46],
      [ball(0.045), 0.08],
    ]);
    g.add(part(box(0.56, 0.05, 0.06), 'body', 0, 0.6, 0));
  },
  burj: (g) => {
    const top = stack(g, [
      [frustum(0.14, 0.18, 0.3, 6), 0.3],
      [frustum(0.1, 0.13, 0.28, 6), 0.28],
      [frustum(0.07, 0.095, 0.24, 6), 0.24],
      [frustum(0.045, 0.065, 0.18, 6), 0.18],
      [frustum(0.004, 0.04, 0.3, 6), 0.3],
    ]);
    g.add(part(ball(0.015), 'glow', 0, top, 0));
  },
  cntower: (g) => {
    stack(g, [
      [frustum(0.05, 0.14, 0.2, 3), 0.2],
      [new THREE.CylinderGeometry(0.035, 0.05, 0.55, 10), 0.55],
      [new THREE.CylinderGeometry(0.12, 0.08, 0.07, 16), 0.07, 'glow'],
      [new THREE.CylinderGeometry(0.03, 0.035, 0.12, 10), 0.12],
      [frustum(0.004, 0.02, 0.32, 8), 0.32],
    ]);
  },
  spaceneedle: (g) => {
    stack(g, [
      [new THREE.CylinderGeometry(0.04, 0.12, 0.3, 6), 0.3],
      [new THREE.CylinderGeometry(0.05, 0.04, 0.28, 6), 0.28],
      [new THREE.CylinderGeometry(0.2, 0.08, 0.08, 20), 0.08, 'glow'],
      [frustum(0.05, 0.12, 0.06, 20), 0.06],
      [frustum(0.004, 0.02, 0.28, 8), 0.28],
    ]);
  },
  petronas: (g) => {
    [-0.15, 0.15].forEach((x) => {
      g.add(part(new THREE.CylinderGeometry(0.06, 0.09, 0.8, 8), 'body', x, 0.4, 0));
      g.add(part(frustum(0.004, 0.04, 0.24, 8), 'body', x, 0.92, 0));
    });
    g.add(part(box(0.22, 0.03, 0.05), 'glow', 0, 0.44, 0));
  },
  marinabay: (g) => {
    [-0.3, 0, 0.3].forEach((x) => g.add(part(box(0.12, 0.56, 0.16), 'body', x, 0.28, 0)));
    g.add(part(box(0.95, 0.04, 0.16), 'glow', 0.05, 0.58, 0));
  },
  colosseum: (g) => {
    const wall = new THREE.CylinderGeometry(0.46, 0.46, 0.22, 32, 1, true, 0, Math.PI * 1.7);
    g.add(twoSided(part(wall, 'body', 0, 0.11, 0)));
    g.add(part(new THREE.CylinderGeometry(0.34, 0.34, 0.12, 32, 1, true), 'body', 0, 0.06, 0));
    g.add(part(new THREE.CylinderGeometry(0.26, 0.26, 0.02, 32), 'glow', 0, 0.01, 0));
  },
  tajmahal: (g) => mosque(g, 0.17, 0.5),
  hagiasophia: (g) => mosque(g, 0.2, 0.42),
  zayed: (g) => mosque(g, 0.15, 0.55),
  stbasil: (g) => {
    g.add(part(box(0.56, 0.2, 0.4), 'body', 0, 0.1, 0));
    const onion = (x: number, z: number, h: number, r: number, role: Role) => {
      g.add(part(new THREE.CylinderGeometry(r * 0.7, r * 0.8, h, 8), 'body', x, 0.2 + h / 2, z));
      const o = part(ball(r), role, x, 0.2 + h + r * 0.7, z);
      o.scale.y = 1.3;
      g.add(o);
      g.add(part(frustum(0.004, r * 0.5, r * 1.4, 8), role, x, 0.2 + h + r * 1.9, z));
    };
    onion(0, 0, 0.42, 0.08, 'glow');
    onion(-0.2, -0.1, 0.2, 0.07, 'body');
    onion(0.2, -0.1, 0.24, 0.07, 'body');
    onion(-0.18, 0.13, 0.16, 0.06, 'body');
    onion(0.18, 0.13, 0.18, 0.06, 'body');
  },
  brandenburg: (g) => {
    g.add(part(box(0.8, 0.04, 0.2), 'body', 0, 0.02, 0));
    for (let i = 0; i < 6; i++) {
      g.add(part(new THREE.CylinderGeometry(0.03, 0.03, 0.36, 8), 'body', -0.33 + i * 0.132, 0.22, 0));
    }
    g.add(part(box(0.84, 0.1, 0.22), 'body', 0, 0.45, 0));
    g.add(part(box(0.16, 0.1, 0.1), 'glow', 0, 0.55, 0));
  },
  acropolis: (g) => {
    g.add(part(box(0.9, 0.08, 0.5), 'body', 0, 0.04, 0));
    for (let i = 0; i < 7; i++) {
      [-0.19, 0.19].forEach((z) =>
        g.add(part(new THREE.CylinderGeometry(0.025, 0.028, 0.28, 8), 'body', -0.36 + i * 0.12, 0.22, z))
      );
    }
    g.add(part(box(0.86, 0.05, 0.46), 'body', 0, 0.385, 0));
    const roof = new THREE.CylinderGeometry(0.0, 0.24, 0.86, 3, 1);
    roof.rotateZ(Math.PI / 2);
    const r = part(roof, 'body', 0, 0.44, 0);
    r.scale.set(1, 0.35, 1);
    g.add(r);
  },
  goldengate: (g) => {
    [-0.45, 0.45].forEach((x) => {
      g.add(part(box(0.05, 0.62, 0.05), 'body', x, 0.31, -0.05));
      g.add(part(box(0.05, 0.62, 0.05), 'body', x, 0.31, 0.05));
      g.add(part(box(0.05, 0.05, 0.15), 'body', x, 0.52, 0));
    });
    g.add(part(box(1.6, 0.03, 0.12), 'body', 0, 0.2, 0));
    [-0.05, 0.05].forEach((z) => {
      const pts: THREE.Vector3[] = [];
      for (let i = 0; i <= 24; i++) {
        const x = -0.8 + (1.6 * i) / 24;
        const ax = Math.abs(x);
        const y = ax <= 0.45 ? 0.62 - 0.38 * (1 - (ax / 0.45) ** 2) : 0.62 - ((ax - 0.45) / 0.35) * 0.4;
        pts.push(new THREE.Vector3(x, y, z));
      }
      g.add(part(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 0.008, 5), 'glow'));
    });
  },
  operahouse: (g) => {
    g.add(part(box(0.9, 0.08, 0.45), 'body', 0, 0.04, 0));
    const sail = (x: number, s: number, flip: number) => {
      const geo = new THREE.SphereGeometry(0.3, 14, 8, 0, Math.PI, 0, Math.PI / 2);
      const m = part(geo, 'body', x, 0.08, 0, 0, flip ? Math.PI / 2 : -Math.PI / 2, 0);
      m.scale.set(s * 0.55, s * 1.5, s);
      g.add(twoSided(m));
    };
    sail(-0.28, 1, 0);
    sail(-0.05, 0.9, 0);
    sail(0.18, 0.75, 0);
    sail(0.36, 0.55, 1);
  },
  sagrada: (g) => {
    g.add(part(box(0.5, 0.18, 0.3), 'body', 0, 0.09, 0));
    [
      [-0.18, 0.6],
      [-0.06, 0.72],
      [0.06, 0.72],
      [0.18, 0.6],
      [0, 0.9],
    ].forEach(([x, h], i) => {
      g.add(part(new THREE.CylinderGeometry(0.02, 0.045, h, 8), 'body', x, 0.18 + h / 2, i === 4 ? -0.05 : 0.08));
      g.add(part(ball(0.022), 'glow', x, 0.18 + h + 0.01, i === 4 ? -0.05 : 0.08));
    });
  },
  greatwall: (g) => {
    const path = [
      [-0.7, -0.2],
      [-0.35, 0.1],
      [0, -0.05],
      [0.35, 0.2],
      [0.7, 0],
    ];
    for (let i = 0; i < path.length - 1; i++) {
      const [x1, z1] = path[i];
      const [x2, z2] = path[i + 1];
      const len = Math.hypot(x2 - x1, z2 - z1);
      g.add(part(box(len, 0.1, 0.06), 'body', (x1 + x2) / 2, 0.05, (z1 + z2) / 2, 0, -Math.atan2(z2 - z1, x2 - x1), 0));
    }
    path.forEach(([x, z]) => g.add(part(box(0.1, 0.18, 0.1), 'body', x, 0.09, z)));
    g.add(part(box(0.06, 0.04, 0.06), 'glow', 0, 0.2, -0.05));
  },
};

const STEM_GEO = new THREE.CylinderGeometry(0.05, 0.05, 1.5, 6);
const CRYSTAL_GEO = new THREE.OctahedronGeometry(0.38);
const RING_GEO = new THREE.RingGeometry(1.15, 1.4, 48);
const FILL_GEO = new THREE.CircleGeometry(1.15, 48);
const DOT_GEO = new THREE.SphereGeometry(0.24, 10, 8);

const MODEL_HEIGHT = 3.2;

export interface SightMarker {
  landmark: Landmark;
  group: THREE.Group;
  tip: THREE.Vector3;
  onRoute: boolean;
  isCaptured: boolean;
  hasModel: boolean;
}

export const hasSightModel = (id: string) => id in MODELS;

export const createSightMarker = (landmark: Landmark, surface: THREE.Vector3): SightMarker => {
  const group = new THREE.Group();
  const normal = surface.clone().normalize();
  group.position.copy(surface);
  group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), normal);

  const inner = new THREE.Group();
  group.add(inner);
  let tipHeight = 1;
  const build = MODELS[landmark.id];

  if (build) {
    const model = new THREE.Group();
    build(model);
    const size = new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3());
    const k = MODEL_HEIGHT / Math.max(size.y, Math.max(size.x, size.z) * 0.55);
    model.scale.setScalar(k);
    model.rotation.y = (landmark.lat * 7 + landmark.lon * 3) % (Math.PI * 2);
    inner.add(model);
    tipHeight = size.y * k * 0.6;
  } else if (landmark.kind === 'landmark') {
    inner.add(part(STEM_GEO, 'stem', 0, 0.75, 0));
    const c = part(CRYSTAL_GEO, 'glow', 0, 1.85, 0);
    c.scale.y = 1.5;
    inner.add(c);
    tipHeight = 1.8;
  } else {
    inner.add(part(FILL_GEO, 'fill', 0, 0.05, 0, -Math.PI / 2));
    inner.add(part(RING_GEO, 'ring', 0, 0.06, 0, -Math.PI / 2));
    inner.add(part(DOT_GEO, 'sglow', 0, 0.2, 0));
    tipHeight = 0.3;
  }

  const tip = surface.clone().addScaledVector(normal, tipHeight);
  inner.traverse((o) => {
    o.renderOrder = 3;
  });
  return { landmark, group, tip, onRoute: false, isCaptured: false, hasModel: !!build };
};

export const styleSightMarker = (m: SightMarker, onRoute: boolean, isCaptured: boolean) => {
  m.onRoute = onRoute;
  m.isCaptured = isCaptured;
  const state: State = isCaptured ? 'captured' : onRoute ? 'normal' : 'dim';
  m.group.traverse((o) => {
    const role = o.userData.role as Role | undefined;
    if (role) (o as THREE.Mesh).material = materialFor(state, role, !!o.userData.double);
  });
  const inner = m.group.children[0];
  inner.scale.setScalar(onRoute ? 1 : m.hasModel ? 0.6 : 0.65);
};

export const pointAlong = (points: THREE.Vector3[], t: number, out = new THREE.Vector3()) => {
  const N = points.length - 1;
  const x = Math.max(0, Math.min(1, t)) * N;
  const i0 = Math.floor(x);
  const i1 = Math.min(N, i0 + 1);
  return out.lerpVectors(points[i0], points[i1], x - i0);
};
