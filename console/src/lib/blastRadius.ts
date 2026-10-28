/**
 * blastRadius — the view model behind the 3D "blast radius" scene.
 *
 * Pure function of a LoadedBundle. Every node it returns IS a bundle record
 * (`node.record === bundle.bySeq.get(node.seq)`); nothing is synthesised.
 * The layout is computed over the WHOLE bundle (cursor-independent) so replay
 * never re-lays-out the scene — the cursor only ghosts / reveals.
 *
 * Space:
 *  - X is the time axis: ordinal rank of the drawn records in seq order (like
 *    DivergenceFlow's ordinal columns, so bursts stay legible). ts_mono is not
 *    used for position — bursts of same-millisecond records would collapse.
 *  - The (Y, Z) plane holds the process tree: each recorded pid is a lifeline
 *    parallel to X, from its first proc_event to its exit (or the end). Roots
 *    (pids whose ppid is not itself a recorded pid) sit on the centre axis;
 *    children branch outward by ppid → pid, one ring per tree depth.
 *  - marker_read / outbound_post carry `peer_pid`: when that pid is a recorded
 *    process they are drawn as satellites of its lifeline at their own seq.
 *    When it is not (e.g. a grandchild the pgroup watcher never saw, or an
 *    escaped peer) they go on an outer ring, unattached — no process
 *    association is invented.
 *  - fs_event carries NO pid (schema: op/path/bytes/sha256/protected only), so
 *    file events are NOT attached to any process. They sit on a helix around
 *    the time axis, outside the tree, in seq order (angle steps per fs event).
 *  - Findings and actions sit on a "witness rail" above the tree at their seq.
 *
 * Cut (no field to ground it): the unrecorded parent of a root process (its
 * ppid has no proc_event of its own) is not drawn as a node.
 * Cut: assistant_claim records are the agent's self-report, not recorded
 * activity — this scene shows only what the recorder observed.
 */
import type { ActionResult, BundleRecord, Finding, FindingKind, Severity } from '../schema/bundle';
import type { LoadedBundle } from './loadBundle';
import { isFlowRecord } from './divergence';

export type Vec3 = readonly [number, number, number];

export type BrNodeKind = 'proc' | 'fs' | 'net' | 'finding' | 'action';

/** A finding whose `evidence_seqs` cites this node. */
export interface Citation {
  findingSeq: number;
  severity: Severity;
  fkind: FindingKind;
}

export interface BrNode {
  seq: number;
  record: BundleRecord;
  kind: BrNodeKind;
  /** ordinal position along the time axis */
  rank: number;
  pos: Vec3;
  /**
   * recorded pid this node belongs to: proc → its own pid; net → peer_pid
   * when that pid is a recorded process; everything else → null.
   */
  pid: number | null;
  citedBy: Citation[];
}

export interface BrProcess {
  pid: number;
  /** first non-null ppid on this pid's proc_events */
  ppid: number | null;
  /** ppid when that pid is itself a recorded process, else null (a root) */
  parentPid: number | null;
  exe: string | null;
  firstSeq: number;
  exitSeq: number | null;
  /** every proc_event seq for this pid */
  seqs: number[];
  depth: number;
  angle: number;
  /** lifeline position in the (Y, Z) plane */
  yz: readonly [number, number];
  children: number[];
}

/** ppid → pid, established by the proc_event record `seq`. */
export interface SpawnEdge {
  parentPid: number;
  pid: number;
  seq: number;
}

export interface BrBlast {
  seq: number;
  record: ActionResult;
  findingSeq: number;
  /** severity of the finding this action answered (null if that seq is not a finding) */
  severity: Severity | null;
  /**
   * The action changed something: ok, and backend detail is not a no-op.
   * `noop` / `already_closed` are drawn as a static marker, not a shockwave.
   */
  effective: boolean;
  center: Vec3;
  radius: number;
  /** stop_pgroup: recorded pids of the stopped group still alive at this seq */
  reachedPids: number[];
  /** the action's own recorded latency — labelled, never used as animation time */
  latencyMs: number;
}

export interface BlastRadius {
  nodes: BrNode[];
  bySeq: Map<number, BrNode>;
  processes: Map<number, BrProcess>;
  spawnEdges: SpawnEdge[];
  /** net node seq → owning recorded pid */
  peerEdges: { seq: number; pid: number }[];
  /** finding seq → evidence seq, only where the evidence is drawn in the scene */
  evidenceEdges: { findingSeq: number; seq: number }[];
  /** evidence seqs that are real records but not scene nodes (claims, tailer, …) */
  offSceneEvidence: { findingSeq: number; seq: number }[];
  blasts: BrBlast[];
  /** x of a given rank */
  xOfRank: (rank: number) => number;
  rankCount: number;
  /** half-length of the time axis */
  halfLength: number;
  /** y of the witness rail */
  railY: number;
  /** outermost radius used by tree / fs helix / unattached net */
  outerRadius: number;
}

/* ---- layout constants (presentational spacing only — never data) ---- */
export const STEP = 2.2;
const RING = 3.4;
const ROOT_SPREAD = 2.6;
const NET_OFFSET = 1.7;
const FS_GAP = 2.4;
const FS_TURN = 0.85;
const RAIL_GAP = 3.2;
const BLAST_MIN = 2.2;
const BLAST_MARGIN = 1.2;
const CLOSE_RADIUS = 1.6;
const NOOP_DETAILS = new Set(['noop', 'already_closed']);

/** Records drawn as nodes. */
export function isSceneRecord(r: BundleRecord): boolean {
  switch (r.kind) {
    case 'proc_event':
    case 'marker_read':
    case 'outbound_post':
    case 'finding':
      return true;
    case 'fs_event':
      // same internal-path filter as the divergence flow (witness's own .session/ files)
      return isFlowRecord(r);
    case 'action_result':
      return r.action === 'stop_pgroup' || r.action === 'close_marker';
    default:
      return false;
  }
}

function kindOf(r: BundleRecord): BrNodeKind {
  switch (r.kind) {
    case 'proc_event':
      return 'proc';
    case 'fs_event':
      return 'fs';
    case 'finding':
      return 'finding';
    case 'action_result':
      return 'action';
    default:
      return 'net';
  }
}

const SEV_RANK: Record<Severity, number> = { stop: 0, warn: 1, info: 2 };

/** Loudest severity among the findings citing this node that have fired by `cursor`. */
export function loudestCitation(n: BrNode, cursor: number = Number.POSITIVE_INFINITY): Severity | null {
  let best: Severity | null = null;
  for (const c of n.citedBy) {
    if (c.findingSeq > cursor) continue;
    if (best === null || SEV_RANK[c.severity] < SEV_RANK[best]) best = c.severity;
  }
  return best;
}

export function blastRadius(b: LoadedBundle): BlastRadius {
  const sceneRecs = b.records.filter(isSceneRecord);
  const rankCount = sceneRecs.length;
  const halfLength = rankCount > 1 ? ((rankCount - 1) * STEP) / 2 : 0;
  const xOfRank = (rank: number) => rank * STEP - halfLength;
  const rankOf = new Map(sceneRecs.map((r, i) => [r.seq, i]));

  /* ---- process tree from proc_event pid / ppid ---- */
  // NOTE: pid reuse within one run is not disambiguated; a reused pid joins the earlier lifeline.
  const processes = new Map<number, BrProcess>();
  for (const r of b.byKind.proc_event) {
    if (r.kind !== 'proc_event') continue;
    let p = processes.get(r.pid);
    if (!p) {
      p = { pid: r.pid, ppid: null, parentPid: null, exe: null, firstSeq: r.seq, exitSeq: null, seqs: [], depth: 0, angle: 0, yz: [0, 0], children: [] };
      processes.set(r.pid, p);
    }
    p.seqs.push(r.seq);
    if (p.ppid === null && r.ppid !== null) p.ppid = r.ppid;
    if (p.exe === null && r.exe !== null) p.exe = r.exe;
    if (r.op === 'exit' && p.exitSeq === null) p.exitSeq = r.seq;
  }
  const spawnEdges: SpawnEdge[] = [];
  for (const p of processes.values()) {
    if (p.ppid !== null && p.ppid !== p.pid && processes.has(p.ppid)) {
      p.parentPid = p.ppid;
      processes.get(p.ppid)!.children.push(p.pid);
      // the record that established the edge: first proc_event of the child carrying that ppid
      const est = p.seqs.map((s) => b.bySeq.get(s)).find((r) => r?.kind === 'proc_event' && r.ppid === p.ppid);
      spawnEdges.push({ parentPid: p.ppid, pid: p.pid, seq: est ? est.seq : p.firstSeq });
    }
  }
  // guard against ppid cycles (malformed bundles): anything unreachable from a root becomes a root
  const roots = [...processes.values()].filter((p) => p.parentPid === null).sort((a, c) => a.firstSeq - c.firstSeq);
  const placed = new Set<number>();
  const place = (p: BrProcess, depth: number, a0: number, a1: number) => {
    if (placed.has(p.pid)) return;
    placed.add(p.pid);
    p.depth = depth;
    p.angle = (a0 + a1) / 2;
    if (depth > 0) p.yz = [Math.cos(p.angle) * RING * depth, Math.sin(p.angle) * RING * depth];
    const kids = p.children.map((c) => processes.get(c)!).sort((x, y) => x.firstSeq - y.firstSeq);
    const w = (a1 - a0) / Math.max(1, kids.length);
    kids.forEach((k, i) => place(k, depth + 1, a0 + i * w, a0 + (i + 1) * w));
  };
  const placeRoots = (rs: BrProcess[]) => {
    rs.forEach((r, i) => {
      const wedge = (Math.PI * 2) / Math.max(1, rs.length);
      const a0 = Math.PI / 2 + i * wedge;
      place(r, 0, a0, a0 + wedge);
      if (rs.length > 1) r.yz = [Math.cos(r.angle) * ROOT_SPREAD, Math.sin(r.angle) * ROOT_SPREAD];
    });
  };
  placeRoots(roots);
  const orphans = [...processes.values()].filter((p) => !placed.has(p.pid));
  if (orphans.length) {
    for (const o of orphans) o.parentPid = null;
    placeRoots(orphans);
  }
  // children inherit their root's offset when there are several roots
  if (roots.length + orphans.length > 1) {
    for (const p of processes.values()) {
      if (p.depth === 0) continue;
      let r = p;
      while (r.parentPid !== null) r = processes.get(r.parentPid)!;
      p.yz = [p.yz[0] + r.yz[0], p.yz[1] + r.yz[1]];
    }
  }
  let treeR = 0;
  for (const p of processes.values()) treeR = Math.max(treeR, Math.hypot(p.yz[0], p.yz[1]));

  /* ---- findings → citations ---- */
  const citations = new Map<number, Citation[]>();
  const evidenceEdges: { findingSeq: number; seq: number }[] = [];
  const offSceneEvidence: { findingSeq: number; seq: number }[] = [];
  for (const f of b.findings) {
    for (const s of new Set(f.evidence_seqs)) {
      if (!b.bySeq.has(s)) continue;
      if (rankOf.has(s)) {
        const list = citations.get(s) ?? [];
        list.push({ findingSeq: f.seq, severity: f.severity, fkind: f.fkind });
        citations.set(s, list);
        evidenceEdges.push({ findingSeq: f.seq, seq: s });
      } else offSceneEvidence.push({ findingSeq: f.seq, seq: s });
    }
  }

  /* ---- nodes ---- */
  const fsR = treeR + FS_GAP + (processes.size ? 0.6 : 0);
  const outerNetR = treeR + RING * 0.85 + 1.2;
  const railY = Math.max(fsR, outerNetR) + RAIL_GAP;
  const nodes: BrNode[] = [];
  const peerEdges: { seq: number; pid: number }[] = [];
  const satCount = new Map<number, number>();
  let fsIdx = 0;
  let looseIdx = 0;
  let actIdx = 0;
  for (const r of sceneRecs) {
    const rank = rankOf.get(r.seq)!;
    const x = xOfRank(rank);
    const kind = kindOf(r);
    let pos: Vec3 = [x, 0, 0];
    let pid: number | null = null;
    if (r.kind === 'proc_event') {
      const p = processes.get(r.pid)!;
      pid = p.pid;
      pos = [x, p.yz[0], p.yz[1]];
    } else if (r.kind === 'marker_read' || r.kind === 'outbound_post') {
      const owner = r.peer_pid !== null ? processes.get(r.peer_pid) : undefined;
      if (owner) {
        pid = owner.pid;
        const k = satCount.get(owner.pid) ?? 0;
        satCount.set(owner.pid, k + 1);
        const a = (owner.depth === 0 ? -Math.PI / 2 : owner.angle) + (k % 2 ? 0.55 : -0.55);
        pos = [x, owner.yz[0] + Math.cos(a) * NET_OFFSET, owner.yz[1] + Math.sin(a) * NET_OFFSET];
        peerEdges.push({ seq: r.seq, pid: owner.pid });
      } else {
        const a = -Math.PI / 2 + 0.7 + looseIdx++ * 0.8;
        pos = [x, Math.cos(a) * outerNetR, Math.sin(a) * outerNetR];
      }
    } else if (r.kind === 'fs_event') {
      const a = Math.PI + fsIdx++ * FS_TURN;
      pos = [x, Math.cos(a) * fsR, Math.sin(a) * fsR];
    } else if (r.kind === 'finding') {
      pos = [x, railY, 0];
    } else if (r.kind === 'action_result') {
      // consecutive actions alternate between two rail heights so their labels don't collide
      pos = [x, railY + 1.5 + (actIdx++ % 2) * 1.3, 0];
    }
    nodes.push({ seq: r.seq, record: r, kind, rank, pos, pid, citedBy: citations.get(r.seq) ?? [] });
  }
  const bySeq = new Map(nodes.map((n) => [n.seq, n]));

  /* ---- blasts: close_marker / stop_pgroup action_results ---- */
  const rootOf = (pid: number): BrProcess => {
    let p = processes.get(pid)!;
    const seen = new Set<number>();
    while (p.parentPid !== null && !seen.has(p.pid)) {
      seen.add(p.pid);
      p = processes.get(p.parentPid)!;
    }
    return p;
  };
  const subtree = (root: BrProcess): BrProcess[] => {
    const out: BrProcess[] = [];
    const stack = [root];
    while (stack.length) {
      const p = stack.pop()!;
      out.push(p);
      for (const c of p.children) stack.push(processes.get(c)!);
    }
    return out;
  };
  const blasts: BrBlast[] = [];
  for (const n of nodes) {
    const r = n.record;
    if (r.kind !== 'action_result') continue;
    const f = b.bySeq.get(r.finding_seq);
    const finding: Finding | null = f?.kind === 'finding' ? f : null;
    const evidenceNodes = (finding?.evidence_seqs ?? []).map((s) => bySeq.get(s)).filter((e): e is BrNode => !!e);
    const effective = r.ok && !(r.detail !== null && NOOP_DETAILS.has(r.detail));
    const x = n.pos[0];
    let center: Vec3 = [x, 0, 0];
    let radius = CLOSE_RADIUS;
    let reachedPids: number[] = [];
    if (r.action === 'stop_pgroup') {
      // the stopped group: root of the evidence's owning process (else the first recorded root)
      const ownerPid = evidenceNodes.find((e) => e.pid !== null)?.pid ?? null;
      const root = ownerPid !== null ? rootOf(ownerPid) : roots[0] ?? null;
      if (root) {
        center = [x, root.yz[0], root.yz[1]];
        const alive = subtree(root).filter((p) => p.firstSeq <= r.seq && (p.exitSeq === null || p.exitSeq >= r.seq));
        reachedPids = alive.map((p) => p.pid).sort((a, c) => a - c);
        let reach = 0;
        for (const p of alive) reach = Math.max(reach, Math.hypot(p.yz[0] - root.yz[0], p.yz[1] - root.yz[1]));
        // satellites of reached processes are part of what the stop cut off
        for (const e of peerEdges) {
          if (!reachedPids.includes(e.pid)) continue;
          const sn = bySeq.get(e.seq)!;
          reach = Math.max(reach, Math.hypot(sn.pos[1] - root.yz[0], sn.pos[2] - root.yz[1]));
        }
        radius = Math.max(BLAST_MIN, reach + BLAST_MARGIN);
      }
    } else {
      // close_marker closes the decoy endpoint: centre on the decoy-net evidence it answered
      const ev = evidenceNodes.find((e) => e.kind === 'net') ?? evidenceNodes[0];
      if (ev) center = [x, ev.pos[1], ev.pos[2]];
    }
    blasts.push({
      seq: r.seq,
      record: r,
      findingSeq: r.finding_seq,
      severity: finding ? finding.severity : null,
      effective,
      center,
      radius,
      reachedPids,
      latencyMs: r.latency_ms,
    });
  }

  return {
    nodes,
    bySeq,
    processes,
    spawnEdges,
    peerEdges,
    evidenceEdges,
    offSceneEvidence,
    blasts,
    xOfRank,
    rankCount,
    halfLength,
    railY,
    outerRadius: Math.max(fsR, outerNetR, treeR),
  };
}

/** x of the replay playhead: just past the last scene record at or before `cursor`. */
export function playheadX(m: BlastRadius, cursor: number): number {
  let last = -1;
  for (const n of m.nodes) if (n.seq <= cursor) last = n.rank;
  if (last < 0) return m.xOfRank(0) - STEP / 2;
  if (last >= m.rankCount - 1) return m.xOfRank(m.rankCount - 1) + STEP / 2;
  return m.xOfRank(last) + STEP / 2;
}
