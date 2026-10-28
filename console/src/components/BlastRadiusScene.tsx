/**
 * BlastRadiusScene — one session's recorded activity as a 3D graph, with the
 * witness's stop actions drawn as expanding shockwaves.
 *
 * Every mesh is one bundle record (lib/blastRadius.ts builds the view model;
 * this file only draws it):
 *  - X is seq order (ordinal); a process is a lifeline from its first
 *    proc_event to its exit, branching from its parent's lifeline (ppid → pid);
 *  - decoy-net records hang off their real `peer_pid`'s lifeline, or float on
 *    an outer ring when that pid was never recorded (no owner is invented);
 *  - fs_event has no pid in the schema, so files ride a seq-order helix
 *    around the axis and are NOT attached to a process;
 *  - nodes cited by a finding's `evidence_seqs` glow in that finding's
 *    severity colour (once the finding has fired, as of the replay cursor);
 *  - each effective close_marker / stop_pgroup action_result fires a ring at
 *    its own seq; a stop_pgroup ring's radius is the extent of the recorded
 *    process group still alive at that seq (+ its satellites).
 *
 * The shockwave's expansion time is presentational — a 3 ms stop would be
 * invisible. The real `latency_ms` is printed on the ring, never encoded as
 * a duration. Records after the replay cursor are ghosted, like
 * DivergenceFlow. Hover a node for its seq; click to jump the timeline.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import type { BundleRecord } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import { blastRadius, loudestCitation, playheadX, STEP, type BlastRadius, type BrBlast, type BrNode } from '../lib/blastRadius';
import { traced } from '../lib/derive';
import { describe } from '../lib/describe';
import { ACTION_LABEL, FINDING_TITLE, SEVERITY_LABEL } from '../lib/codes';
import { useNav, type Nav } from '../lib/nav';
import { C, LANE_COLOR, SEV_COLOR } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

const HEIGHT = 520;
const GHOST = 0.12;
/** presentational shockwave timing (seconds) — NOT the recorded latency */
const EXPAND_S = 1.5;
const PERIOD_S = 3.4;
const MONO = "'JetBrains Mono Variable', ui-monospace, Menlo, monospace";

function base(p: string): string {
  const i = p.lastIndexOf('/');
  return i >= 0 && i < p.length - 1 ? p.slice(i + 1) : p;
}

/** short, schema-only node label (null → unlabelled) */
function nodeLabel(n: BrNode & { effective?: boolean }): string | null {
  const r = n.record;
  switch (r.kind) {
    case 'proc_event':
      return r.op === 'exit' ? null : `${r.op === 'spawn' ? '' : `${r.op} `}${r.exe ?? 'pid'} · ${r.pid}`;
    case 'fs_event':
      return `${r.op} ${base(r.path)}`;
    case 'marker_read':
    case 'outbound_post': {
      const what = r.kind === 'marker_read' ? 'decoy key read' : r.contains_marker ? 'POST + decoy' : 'POST → sink';
      const esc = r.peer_escaped ? ' · ESCAPED' : '';
      return n.pid === null ? `${what} · pid ${r.peer_pid ?? '?'} not in tree${esc}` : `${what}${esc}`;
    }
    case 'finding':
      return `${SEVERITY_LABEL[r.severity]}  ${FINDING_TITLE[r.fkind]}  #${r.seq}`;
    case 'action_result':
      // an effective action's ring carries the full label; here only the no-op / failed ones
      if (n.effective) return null;
      return `${ACTION_LABEL[r.action]} · ${r.ok ? (r.detail ?? 'no-op') : 'FAILED'} · ${r.latency_ms} ms`;
    default:
      return null;
  }
}

function nodeColor(n: BrNode, m: BlastRadius): string {
  const r = n.record;
  switch (r.kind) {
    case 'proc_event':
      return LANE_COLOR.proc;
    case 'fs_event':
      return LANE_COLOR.fs;
    case 'finding':
      return SEV_COLOR[r.severity];
    case 'action_result': {
      const bl = m.blasts.find((x) => x.seq === r.seq);
      return bl && bl.effective && bl.severity ? SEV_COLOR[bl.severity] : C.fg4;
    }
    default:
      return LANE_COLOR.net;
  }
}

/** label for an EFFECTIVE blast ring (no-op / failed actions are labelled on their rail node) */
function blastLabel(bl: BrBlast): string {
  const a = bl.record;
  const head = `${bl.severity ? SEVERITY_LABEL[bl.severity] : 'ACTION'} · ${ACTION_LABEL[a.action]}`;
  const lat = `${a.latency_ms} ms recorded`;
  const reach = a.action === 'stop_pgroup' ? ` · reached pid ${bl.reachedPids.join(', ') || '—'}` : '';
  return `${head} · ${lat}${a.detail ? ` · ${a.detail}` : ''}${reach}`;
}

/* ------------------------------------------------------------- three helpers */

function textSprite(text: string, color: string, height: number, anchorLeft = true): THREE.Sprite {
  const px = 44;
  const font = `600 ${px}px ${MONO}`;
  const c = document.createElement('canvas');
  const ctx = c.getContext('2d');
  const pad = 14;
  let w = 256;
  if (ctx) {
    ctx.font = font;
    w = Math.ceil(ctx.measureText(text).width) + pad * 2;
  }
  c.width = w;
  c.height = px + 20;
  if (ctx) {
    ctx.font = font;
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(6,8,13,0.62)';
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.fillStyle = color;
    ctx.fillText(text, pad, c.height / 2 + 2);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false });
  const s = new THREE.Sprite(mat);
  s.scale.set((height * c.width) / c.height, height, 1);
  s.center.set(anchorLeft ? 0 : 0.5, 0.5);
  s.renderOrder = 10;
  return s;
}

let haloTex: THREE.CanvasTexture | null = null;
function haloTexture(): THREE.CanvasTexture {
  if (haloTex) return haloTex;
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d');
  if (ctx) {
    const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.25, 'rgba(255,255,255,0.55)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
  }
  haloTex = new THREE.CanvasTexture(c);
  return haloTex;
}

function tube(curve: THREE.Curve<THREE.Vector3>, radius: number, color: string, opacity: number, segs = 24): THREE.Mesh<THREE.TubeGeometry, THREE.MeshBasicMaterial> {
  const geo = new THREE.TubeGeometry(curve, segs, radius, 8, false);
  const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
  return new THREE.Mesh(geo, mat);
}

function line(a: THREE.Vector3, b: THREE.Vector3, color: string, opacity: number, dashed = false): THREE.Line {
  const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
  const mat = dashed
    ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 0.35, gapSize: 0.25, depthWrite: false })
    : new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
  const l = new THREE.Line(geo, mat);
  if (dashed) l.computeLineDistances();
  return l;
}

/** a ring lying in the plane perpendicular to the time axis (normal = +X) */
function ringGeo(inner: number, outer: number): THREE.RingGeometry {
  const g = new THREE.RingGeometry(inner, outer, 128);
  g.rotateY(Math.PI / 2);
  return g;
}

const v3 = (p: readonly [number, number, number]) => new THREE.Vector3(p[0], p[1], p[2]);

/* -------------------------------------------------------------- scene build */

interface SceneHandle {
  apply: (cursor: number, hover: ReadonlySet<number>, selected: number | null) => void;
  resetView: () => void;
  setSway: (on: boolean) => void;
  dispose: () => void;
}

interface NodeView {
  n: BrNode;
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
  label: THREE.Sprite | null;
  halo: THREE.Sprite | null;
  baseScale: number;
}

interface BlastView {
  bl: BrBlast;
  group: THREE.Group;
  waves: THREE.Mesh<THREE.RingGeometry, THREE.MeshBasicMaterial>[];
  shell: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial> | null;
  flash: THREE.Sprite | null;
  t0: number | null;
}

function buildScene(
  host: HTMLDivElement,
  m: BlastRadius,
  navRef: React.RefObject<Nav>,
  onHover: (h: { seq: number; x: number; y: number } | null) => void,
  reducedMotion: boolean,
): SceneHandle {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  const W0 = Math.max(320, host.clientWidth);
  renderer.setSize(W0, HEIGHT);
  renderer.setClearColor(C.well, 1);
  host.appendChild(renderer.domElement);
  renderer.domElement.style.display = 'block';

  const scene = new THREE.Scene();
  // background as a scene Color, not only the clear colour: through the EffectComposer the bare
  // clear colour gets sRGB-encoded twice (washed-out grey); scene.background clears in linear space.
  scene.background = new THREE.Color(C.well);
  scene.fog = new THREE.Fog(C.well, 40, 140);
  scene.add(new THREE.AmbientLight(0xffffff, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 1.1);
  key.position.set(-10, 18, 14);
  scene.add(key);

  const camera = new THREE.PerspectiveCamera(40, W0 / HEIGHT, 0.1, 600);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 4;
  controls.maxDistance = 220;

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(W0, HEIGHT), 0.8, 0.45, 0.32);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  const outer = m.outerRadius;
  const xs = m.rankCount ? [m.xOfRank(0), m.xOfRank(m.rankCount - 1)] : [0, 0];
  const xMin = (xs[0] as number) - STEP * 0.8;
  const xMax = (xs[1] as number) + STEP * 0.8;
  const floorY = -(outer + 1.6);

  /* time ruler: one tick per drawn record, labelled with its real seq */
  const ruler = new THREE.Group();
  ruler.add(line(new THREE.Vector3(xMin, floorY, 0), new THREE.Vector3(xMax, floorY, 0), C.lineStrong, 0.9));
  const every = m.rankCount > 28 ? Math.ceil(m.rankCount / 14) : 1;
  for (const n of m.nodes) {
    const x = n.pos[0];
    ruler.add(line(new THREE.Vector3(x, floorY - 0.25, 0), new THREE.Vector3(x, floorY + 0.25, 0), C.fg5, 0.9));
    if (n.rank % every === 0) {
      const t = textSprite(`#${n.seq}`, C.fg4, 0.42, false);
      t.position.set(x, floorY - 0.7, 0);
      ruler.add(t);
    }
  }
  const axisCap = textSprite('seq order →', C.fg4, 0.5);
  axisCap.position.set(xMax + 0.4, floorY, 0);
  ruler.add(axisCap);
  scene.add(ruler);

  /* process lifelines (ghost + revealed) and spawn branches */
  const lifelines: { start: number; end: number; live: THREE.Mesh<THREE.CylinderGeometry, THREE.MeshBasicMaterial> }[] = [];
  const unitCyl = new THREE.CylinderGeometry(0.075, 0.075, 1, 10, 1, true);
  unitCyl.rotateZ(-Math.PI / 2);
  for (const p of m.processes.values()) {
    const first = m.bySeq.get(p.firstSeq);
    const exit = p.exitSeq !== null ? m.bySeq.get(p.exitSeq) : undefined;
    if (!first) continue;
    const start = first.pos[0];
    const end = exit ? exit.pos[0] : xMax; // never exited within the recording → runs to the end
    const [y, z] = p.yz;
    const ghost = tube(new THREE.LineCurve3(new THREE.Vector3(start, y, z), new THREE.Vector3(end, y, z)), 0.05, LANE_COLOR.proc, 0.14, 2);
    scene.add(ghost);
    const live = new THREE.Mesh(unitCyl, new THREE.MeshBasicMaterial({ color: LANE_COLOR.proc, transparent: true, opacity: 0.85 }));
    live.position.set(start, y, z);
    scene.add(live);
    lifelines.push({ start, end, live });
  }
  const spawnEdges: { seq: number; obj: THREE.Mesh<THREE.TubeGeometry, THREE.MeshBasicMaterial> }[] = [];
  for (const e of m.spawnEdges) {
    const parent = m.processes.get(e.parentPid)!;
    const child = m.processes.get(e.pid)!;
    const cn = m.bySeq.get(child.firstSeq);
    if (!cn) continue;
    const x = cn.pos[0];
    const a = new THREE.Vector3(x - STEP * 0.55, parent.yz[0], parent.yz[1]);
    const b = new THREE.Vector3(x, child.yz[0], child.yz[1]);
    const ctrl = new THREE.Vector3(x - STEP * 0.1, parent.yz[0], parent.yz[1]);
    const obj = tube(new THREE.QuadraticBezierCurve3(a, ctrl, b), 0.05, LANE_COLOR.proc, 0.7);
    scene.add(obj);
    spawnEdges.push({ seq: e.seq, obj });
  }

  /* fs helix thread — the drawing of seq order between file events (no pid exists to attach them) */
  const fsNodes = m.nodes.filter((n) => n.kind === 'fs');
  if (fsNodes.length >= 2) {
    const thread = tube(new THREE.CatmullRomCurve3(fsNodes.map((n) => v3(n.pos))), 0.025, LANE_COLOR.fs, 0.22, fsNodes.length * 16);
    scene.add(thread);
  }

  /* nodes */
  const geos = {
    spawn: new THREE.SphereGeometry(0.46, 28, 18),
    exit: new THREE.SphereGeometry(0.28, 20, 12),
    fs: new THREE.BoxGeometry(0.56, 0.56, 0.56),
    net: new THREE.OctahedronGeometry(0.52),
    finding: new THREE.IcosahedronGeometry(0.62),
    stop: new THREE.BoxGeometry(0.78, 0.78, 0.78),
    close: new THREE.TorusGeometry(0.42, 0.12, 12, 32),
  };
  const nodeViews: NodeView[] = [];
  const pickables: THREE.Object3D[] = [];
  for (const n of m.nodes) {
    const r = n.record;
    const col = nodeColor(n, m);
    const geo =
      r.kind === 'proc_event'
        ? r.op === 'exit'
          ? geos.exit
          : geos.spawn
        : r.kind === 'fs_event'
          ? geos.fs
          : r.kind === 'finding'
            ? geos.finding
            : r.kind === 'action_result'
              ? r.action === 'stop_pgroup'
                ? geos.stop
                : geos.close
              : geos.net;
    const mat = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.55, roughness: 0.38, metalness: 0.15, transparent: true });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(v3(n.pos));
    if (r.kind === 'fs_event') mesh.rotation.set(0.5, 0.6, 0);
    mesh.userData.seq = n.seq;
    scene.add(mesh);
    pickables.push(mesh);

    let halo: THREE.Sprite | null = null;
    if (n.citedBy.length) {
      halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTexture(), color: C.info, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
      halo.position.copy(mesh.position);
      halo.scale.setScalar(2.6);
      scene.add(halo);
    }
    const text = nodeLabel({ ...n, effective: m.blasts.find((x) => x.seq === n.seq)?.effective ?? false });
    let label: THREE.Sprite | null = null;
    if (text) {
      const tc = r.kind === 'finding' ? SEV_COLOR[r.severity] : r.kind === 'action_result' ? col : C.fg2;
      label = textSprite(text, tc, r.kind === 'finding' || r.kind === 'action_result' ? 0.52 : 0.44);
      // adjacent findings alternate label height (presentational only) so their titles don't collide
      const dy = r.kind === 'finding' && n.rank % 2 ? -0.95 : 0.55;
      label.position.set(n.pos[0] + 0.7, n.pos[1] + dy, n.pos[2]);
      scene.add(label);
    }
    nodeViews.push({ n, mesh, label, halo, baseScale: 1 });
  }

  /* edges: net → owner lifeline, finding → evidence, action → finding */
  const seqEdges: { seq: number; obj: THREE.Line; on: number }[] = [];
  for (const e of m.peerEdges) {
    const sn = m.bySeq.get(e.seq)!;
    const p = m.processes.get(e.pid)!;
    const l = line(v3(sn.pos), new THREE.Vector3(sn.pos[0], p.yz[0], p.yz[1]), LANE_COLOR.net, 0.7);
    scene.add(l);
    seqEdges.push({ seq: e.seq, obj: l, on: 0.7 });
  }
  for (const e of m.evidenceEdges) {
    const fn = m.bySeq.get(e.findingSeq)!;
    const en = m.bySeq.get(e.seq)!;
    const f = fn.record;
    const l = line(v3(fn.pos), v3(en.pos), f.kind === 'finding' ? SEV_COLOR[f.severity] : C.fg4, 0.6, true);
    scene.add(l);
    seqEdges.push({ seq: e.findingSeq, obj: l, on: 0.6 });
  }

  /* blasts */
  const blastViews: BlastView[] = [];
  for (const bl of m.blasts) {
    const an = m.bySeq.get(bl.seq)!;
    const fn = m.bySeq.get(bl.findingSeq);
    if (fn) {
      const l = line(v3(an.pos), v3(fn.pos), nodeColor(an, m), 0.55);
      scene.add(l);
      seqEdges.push({ seq: bl.seq, obj: l, on: 0.55 });
    }
    const col = bl.effective && bl.severity ? SEV_COLOR[bl.severity] : C.fg4;
    const group = new THREE.Group();
    group.position.copy(v3(bl.center));
    const drop = line(new THREE.Vector3(0, an.pos[1] - bl.center[1], an.pos[2] - bl.center[2]), new THREE.Vector3(0, 0, 0), col, 0.45, true);
    group.add(drop);
    const waves: BlastView['waves'] = [];
    let shell: BlastView['shell'] = null;
    let flash: BlastView['flash'] = null;
    if (bl.effective) {
      // static extent: how far this action reached (the recorded group), drawn at its seq
      group.add(new THREE.Mesh(ringGeo(bl.radius - 0.06, bl.radius), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false })));
      const disc = new THREE.Mesh(new THREE.CircleGeometry(bl.radius, 96).rotateY(Math.PI / 2), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.06, side: THREE.DoubleSide, depthWrite: false }));
      group.add(disc);
      for (let i = 0; i < 2; i++) {
        const w = new THREE.Mesh(ringGeo(0.9, 1), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending }));
        group.add(w);
        waves.push(w);
      }
      shell = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 20), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0, wireframe: true, depthWrite: false, blending: THREE.AdditiveBlending }));
      group.add(shell);
      flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTexture(), color: col, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
      group.add(flash);
    } else {
      group.add(new THREE.Mesh(ringGeo(0.62, 0.7), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.6, side: THREE.DoubleSide, depthWrite: false })));
    }
    if (bl.effective) {
      const lab = textSprite(blastLabel(bl), col, 0.6, false);
      lab.position.set(0, -bl.radius - 0.75, 0);
      group.add(lab);
    }
    scene.add(group);
    blastViews.push({ bl, group, waves, shell, flash, t0: null });
  }

  /* playhead: a translucent slice through the scene at the replay cursor */
  const ph = new THREE.Group();
  const phR = outer + 0.9;
  ph.add(new THREE.Mesh(ringGeo(phR - 0.04, phR), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0.4, side: THREE.DoubleSide, depthWrite: false })));
  ph.add(new THREE.Mesh(new THREE.CircleGeometry(phR, 96).rotateY(Math.PI / 2), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0.035, side: THREE.DoubleSide, depthWrite: false })));
  scene.add(ph);
  let phTarget = xMax;
  ph.position.x = xMax;

  /* camera framing */
  const top = m.railY + 4.6; // highest action node + its label
  const target = new THREE.Vector3(0, (top + floorY) / 2, 0);
  const dir = new THREE.Vector3(-0.32, 0.4, 0.86).normalize();
  const frame = () => {
    const vf = (camera.fov * Math.PI) / 180;
    const hf = 2 * Math.atan(Math.tan(vf / 2) * camera.aspect);
    const halfW = (xMax - xMin) / 2 + 3;
    const halfH = (top - floorY) / 2 + 1.2;
    const d = Math.max(halfW / Math.tan(hf / 2), halfH / Math.tan(vf / 2), 14) * 1.02;
    camera.position.copy(target).addScaledVector(dir, d);
    controls.target.copy(target);
    camera.lookAt(target);
    controls.update();
  };
  frame();

  /* sway (gentle parallax) until the user grabs the camera */
  let sway = !reducedMotion;
  let swayBase: THREE.Spherical | null = null;
  const captureSway = () => {
    swayBase = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
  };
  captureSway();
  controls.addEventListener('start', () => {
    sway = false;
  });

  /* state applied from React */
  let cursor = Number.POSITIVE_INFINITY;
  let hover: ReadonlySet<number> = new Set();
  let selected: number | null = null;
  const clock = new THREE.Clock();

  const apply = (c: number, h: ReadonlySet<number>, sel: number | null) => {
    cursor = c;
    hover = h;
    selected = sel;
    phTarget = playheadX(m, c);
    // like DivergenceFlow: no playhead once the cursor is past the last drawn record
    ph.visible = m.nodes.length > 0 && c < (m.nodes[m.nodes.length - 1] as BrNode).seq;
    for (const v of nodeViews) {
      const past = v.n.seq <= cursor;
      v.mesh.material.opacity = past ? 1 : GHOST;
      v.mesh.material.emissiveIntensity = past ? 0.55 : 0.1;
      if (v.label) {
        v.label.material.opacity = past ? 1 : 0.1;
        // like DivergenceFlow: a finding's title is not shown before the replay reaches it
        v.label.visible = past || v.n.kind !== 'finding';
      }
      const sev = loudestCitation(v.n, cursor);
      if (v.halo) {
        v.halo.visible = sev !== null;
        if (sev) v.halo.material.color.set(SEV_COLOR[sev]);
      }
      v.baseScale = hover.has(v.n.seq) || selected === v.n.seq ? 1.45 : 1;
    }
    for (const e of spawnEdges) e.obj.material.opacity = e.seq <= cursor ? 0.7 : 0.08;
    for (const e of seqEdges) (e.obj.material as THREE.LineBasicMaterial).opacity = e.seq <= cursor ? e.on : 0.05;
    const now = clock.getElapsedTime();
    for (const b of blastViews) {
      const past = b.bl.seq <= cursor;
      b.group.visible = past;
      if (past && b.t0 === null) b.t0 = now; // fires when the replay crosses the action's seq
      if (!past) b.t0 = null;
    }
  };

  /* picking */
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let hoverSeq: number | null = null;
  let down: { x: number; y: number } | null = null;
  const pick = (ev: PointerEvent): number | null => {
    const rect = renderer.domElement.getBoundingClientRect();
    ndc.set(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false)[0];
    return hit ? (hit.object.userData.seq as number) : null;
  };
  const onMove = (ev: PointerEvent) => {
    const s = pick(ev);
    const rect = renderer.domElement.getBoundingClientRect();
    if (s !== hoverSeq) {
      hoverSeq = s;
      navRef.current?.setHoverSeqs(s === null ? [] : [s]);
    }
    onHover(s === null ? null : { seq: s, x: ev.clientX - rect.left, y: ev.clientY - rect.top });
    renderer.domElement.style.cursor = s === null ? 'grab' : 'pointer';
  };
  const onLeave = () => {
    if (hoverSeq !== null) navRef.current?.setHoverSeqs([]);
    hoverSeq = null;
    onHover(null);
  };
  const onDown = (ev: PointerEvent) => {
    down = { x: ev.clientX, y: ev.clientY };
  };
  const onUp = (ev: PointerEvent) => {
    if (!down || Math.hypot(ev.clientX - down.x, ev.clientY - down.y) > 4) return;
    const s = pick(ev);
    if (s !== null) navRef.current?.jump(s);
  };
  const el = renderer.domElement;
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerleave', onLeave);
  el.addEventListener('pointerdown', onDown);
  el.addEventListener('pointerup', onUp);

  /* resize */
  const ro = new ResizeObserver(() => {
    const w = Math.max(320, host.clientWidth);
    renderer.setSize(w, HEIGHT);
    composer.setSize(w, HEIGHT);
    bloom.resolution.set(w, HEIGHT);
    camera.aspect = w / HEIGHT;
    camera.updateProjectionMatrix();
  });
  ro.observe(host);

  /* loop */
  let raf = 0;
  const tick = () => {
    raf = requestAnimationFrame(tick);
    const t = clock.getElapsedTime();
    if (sway && swayBase) {
      const s = swayBase.clone();
      s.theta += Math.sin(t * 0.22) * 0.32;
      s.phi += Math.sin(t * 0.13) * 0.06;
      camera.position.setFromSpherical(s).add(controls.target);
      camera.lookAt(controls.target);
    }
    controls.update();
    ph.position.x += (phTarget - ph.position.x) * (reducedMotion ? 1 : 0.12);
    for (const l of lifelines) {
      const len = Math.max(0.0001, Math.min(l.end, ph.position.x) - l.start);
      l.live.visible = ph.position.x > l.start;
      l.live.scale.set(len, 1, 1);
      l.live.position.x = l.start + len / 2;
    }
    const pulse = reducedMotion ? 1 : 1 + 0.18 * Math.sin(t * 3.2);
    for (const v of nodeViews) {
      v.mesh.scale.setScalar(v.baseScale);
      if (v.halo && v.halo.visible) v.halo.scale.setScalar(2.6 * pulse * v.baseScale);
      if (v.n.kind === 'finding' && !reducedMotion) v.mesh.rotation.y = t * 0.6;
    }
    for (const b of blastViews) {
      if (!b.group.visible || !b.bl.effective || b.t0 === null) continue;
      const R = b.bl.radius;
      if (reducedMotion) {
        b.waves.forEach((w) => {
          w.scale.setScalar(R);
          w.material.opacity = 0.5;
        });
        continue;
      }
      const age = (t - b.t0) % PERIOD_S;
      b.waves.forEach((w, i) => {
        const a = (age - i * 0.28) / EXPAND_S;
        if (a < 0 || a > 1) {
          w.material.opacity = 0;
          return;
        }
        const e = 1 - Math.pow(1 - a, 3);
        w.scale.setScalar(Math.max(0.02, e * R));
        w.material.opacity = (1 - a) * 0.95;
      });
      if (b.shell) {
        const a = age / EXPAND_S;
        const on = a <= 1;
        b.shell.visible = on;
        if (on) {
          const e = 1 - Math.pow(1 - a, 3);
          b.shell.scale.setScalar(Math.max(0.02, e * R));
          b.shell.material.opacity = (1 - a) * 0.22;
        }
      }
      if (b.flash) {
        const a = age / 0.6;
        b.flash.material.opacity = a <= 1 ? 1 - a : 0;
        b.flash.scale.setScalar(1.5 + 4 * Math.min(1, a));
      }
    }
    composer.render();
  };
  tick();

  return {
    apply,
    resetView: () => {
      frame();
      captureSway();
    },
    setSway: (on: boolean) => {
      if (on) captureSway();
      sway = on && !reducedMotion;
    },
    dispose: () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
      el.removeEventListener('pointerdown', onDown);
      el.removeEventListener('pointerup', onUp);
      controls.dispose();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
        for (const mt of mats) {
          const map = (mt as THREE.SpriteMaterial).map;
          if (map && map !== haloTex) map.dispose();
          mt.dispose();
        }
      });
      composer.dispose();
      renderer.dispose();
      el.remove();
    },
  };
}

/* ---------------------------------------------------------------- component */

function webglLikely(): boolean {
  return typeof window !== 'undefined' && ('WebGL2RenderingContext' in window || 'WebGLRenderingContext' in window);
}

function tip(r: BundleRecord): { title: string; parts: string[] } {
  const d = describe(r);
  return { title: d.title, parts: d.parts.slice(0, 3) };
}

export function BlastRadiusScene({ bundle, cursor }: { bundle: LoadedBundle; cursor: number }) {
  const nav = useNav();
  const navRef = useRef<Nav>(nav);
  navRef.current = nav;
  const host = useRef<HTMLDivElement>(null);
  const handle = useRef<SceneHandle | null>(null);
  const model = useMemo(() => blastRadius(bundle), [bundle]);
  const [failed, setFailed] = useState<string | null>(webglLikely() ? null : 'WebGL is not available in this browser.');
  const [hover, setHover] = useState<{ seq: number; x: number; y: number } | null>(null);
  const [sway, setSway] = useState(true);
  const applyArgs = useRef({ cursor, hover: new Set(nav.hoverSeqs) as ReadonlySet<number>, selected: nav.selected });
  applyArgs.current = { cursor, hover: new Set(nav.hoverSeqs), selected: nav.selected };

  useEffect(() => {
    if (failed || !host.current || model.nodes.length === 0) return;
    const el = host.current;
    let cancelled = false;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    const fontsReady: Promise<unknown> = document.fonts?.ready ?? Promise.resolve();
    fontsReady.then(() => {
      if (cancelled) return;
      try {
        handle.current = buildScene(el, model, navRef, setHover, reduced);
        const a = applyArgs.current;
        handle.current.apply(a.cursor, a.hover, a.selected);
      } catch (e) {
        setFailed(e instanceof Error ? `3D view unavailable: ${e.message}` : '3D view unavailable.');
      }
    });
    return () => {
      cancelled = true;
      handle.current?.dispose();
      handle.current = null;
    };
  }, [model, failed]);

  useEffect(() => {
    handle.current?.apply(cursor, new Set(nav.hoverSeqs), nav.selected);
  }, [cursor, nav.hoverSeqs, nav.selected]);

  /* header numbers — every one traced */
  const spawnSeqs = [...model.processes.values()].map((p) => p.firstSeq);
  const procCount = traced(model.processes.size, spawnSeqs, 'distinct pids across proc_event records');
  const shown = model.blasts.filter((b) => b.seq <= cursor && b.effective);
  const blastCount = traced(shown.length, shown.map((b) => b.seq), 'effective close_marker / stop_pgroup action_results so far (ok, not noop / already_closed)');
  const stops = model.blasts.filter((b) => b.record.action === 'stop_pgroup' && b.seq <= cursor);
  const stoppedNow = stops.some((b) => b.effective);
  const unattached = model.nodes.filter((n) => n.kind === 'net' && n.pid === null).length;
  const fsCount = model.nodes.filter((n) => n.kind === 'fs').length;
  const hovered = hover ? model.bySeq.get(hover.seq) : undefined;

  return (
    <section className="card overflow-hidden" aria-label="Blast radius — recorded activity in 3D">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-3 border-b border-line px-5 py-4">
        <div className="min-w-[300px] flex-1">
          <div className="eyebrow text-accent">Blast radius</div>
          <h2 className="mt-1.5 text-[20px] font-semibold leading-tight tracking-[-0.02em] text-fg">
            What the agent actually touched
            {stoppedNow ? (
              <span className="text-stop"> — and where it was stopped</span>
            ) : model.blasts.some((b) => b.record.action === 'stop_pgroup') ? null : (
              <span className="text-fg-4"> — no process-group stop in this run</span>
            )}
          </h2>
          <p className="mt-1 max-w-[780px] text-[12.5px] text-fg-3">
            Left → right is seq order. Process lifelines branch by ppid → pid; decoy-net calls hang off their real peer pid; file events ride a helix (the schema records no pid for them). Evidence glows in its finding’s severity. Each stop action fires a ring at its own seq, sized to the process group it reached.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {stops.map((b) => (
            <div
              key={b.seq}
              className="flex items-center gap-2 rounded-md border px-2.5 py-1.5"
              style={{ borderColor: `${b.effective ? C.stop : C.fg4}73`, background: `${b.effective ? C.stop : C.fg4}14`, boxShadow: b.effective ? `0 0 28px -10px ${C.stop}` : undefined }}
            >
              <span className="font-mono text-[10px] font-bold tracking-[0.14em]" style={{ color: b.effective ? C.stop : C.fg3 }}>
                {b.record.ok ? 'STOPPED' : 'STOP FAILED'}
              </span>
              <SeqChip seq={b.seq} />
              <span className="font-mono text-[12px] text-fg-2">
                <TraceNumber t={traced(b.latencyMs, [b.seq], `latency_ms field of action_result seq ${b.seq}`)} title="Recorded stop latency" format={(v) => <span>{v} ms</span>} />
              </span>
            </div>
          ))}
          <div className="text-right font-mono text-[10.5px] leading-tight text-fg-4">
            processes
            <div className="text-[18px] font-semibold text-fg">
              <TraceNumber t={procCount} title="Recorded processes" format={(v) => <span>{v}</span>} />
            </div>
          </div>
          <div className="text-right font-mono text-[10.5px] leading-tight text-fg-4">
            blasts
            <div className="text-[18px] font-semibold text-fg">
              <TraceNumber t={blastCount} title="Effective containment actions" format={(v) => <span>{v}</span>} />
            </div>
          </div>
        </div>
      </div>

      <div className="relative w-full bg-bg-well" style={{ height: HEIGHT }}>
        {failed ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-[12.5px] text-fg-4">
            {failed} Every record is still on the timeline and divergence flow above.
          </div>
        ) : model.nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-[12.5px] text-fg-4">No process, file or decoy-net records in this bundle.</div>
        ) : (
          <div ref={host} className="absolute inset-0" data-testid="blast-radius-canvas" />
        )}
        {!failed ? (
          <div className="absolute right-3 top-3 flex gap-2">
            <button
              type="button"
              className="btn"
              onClick={() => {
                const next = !sway;
                setSway(next);
                handle.current?.setSway(next);
              }}
            >
              {sway ? 'Hold camera' : 'Sway'}
            </button>
            <button type="button" className="btn" onClick={() => handle.current?.resetView()}>
              Reset view
            </button>
          </div>
        ) : null}
        {hovered && hover ? (
          <div
            className="pointer-events-none absolute z-10 max-w-[340px] rounded-md border border-line-strong bg-bg/95 px-3 py-2 font-mono text-[11px] shadow-lg"
            style={{ left: Math.min(hover.x + 14, 9999), top: hover.y + 14 }}
          >
            <div className="text-fg">
              <span className="text-fg-4">seq {hovered.seq} · </span>
              {tip(hovered.record).title}
            </div>
            {tip(hovered.record).parts.length ? <div className="mt-0.5 text-fg-3">{tip(hovered.record).parts.join(' · ')}</div> : null}
            {hovered.citedBy.length ? (
              <div className="mt-1 text-fg-3">
                evidence for{' '}
                {hovered.citedBy.map((c) => (
                  <span key={c.findingSeq} className="mr-1.5" style={{ color: SEV_COLOR[c.severity] }}>
                    {SEVERITY_LABEL[c.severity]} #{c.findingSeq}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="mt-1 text-fg-5">click to jump the timeline</div>
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line px-5 py-2.5 font-mono text-[10.5px] text-fg-4">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: LANE_COLOR.proc }} /> process (lifeline)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rotate-45" style={{ background: LANE_COLOR.net }} /> decoy net{unattached ? ` · ${unattached} peer pid not in tree` : ''}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2" style={{ background: LANE_COLOR.fs }} /> file ({fsCount}) · no pid in schema → helix
        </span>
        {(['stop', 'warn', 'info'] as const).map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: SEV_COLOR[s], boxShadow: `0 0 8px ${SEV_COLOR[s]}` }} /> {SEVERITY_LABEL[s]} evidence
          </span>
        ))}
        {model.offSceneEvidence.length ? <span>{model.offSceneEvidence.length} cited records off-scene (claims / tailer)</span> : null}
        <span className="ml-auto">ring expansion is animation only — the label carries the recorded latency_ms</span>
      </div>
    </section>
  );
}

export default BlastRadiusScene;
