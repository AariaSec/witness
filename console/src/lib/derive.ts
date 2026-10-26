/**
 * derive — pure functions from a LoadedBundle to every number the UI shows.
 *
 * Contract (14_fable_architecture_phases.md §3.4): every derived number is a
 * `Traced` — `{ value, seqs }` — and the UI's number components accept ONLY
 * `Traced`, so a number with no seq provenance cannot be rendered. `basis` is
 * a fixed, console-authored sentence describing how the number was computed.
 *
 * Every function takes an optional `upto` seq (inclusive) so the replay
 * scrubber can show the state of the run "as of" any record.
 */
import type {
  ActionResult,
  AssistantClaim,
  BundleRecord,
  FindingKind,
  Finding,
  Kind,
  Severity,
} from '../schema/bundle';
import type { LoadedBundle } from './loadBundle';

export interface Traced<T = number> {
  readonly value: T;
  readonly seqs: readonly number[];
  readonly basis: string;
}

export function traced<T>(value: T, seqs: Iterable<number>, basis: string): Traced<T> {
  return { value, seqs: [...new Set(seqs)].sort((a, b) => a - b), basis };
}

const ALL = Number.POSITIVE_INFINITY;

export function upTo(b: LoadedBundle, upto: number = ALL): BundleRecord[] {
  if (upto === ALL) return b.records;
  return b.records.filter((r) => r.seq <= upto);
}

/* ------------------------------------------------------------------ lanes */

export type Lane = 'claim' | 'proc' | 'fs' | 'net' | 'witness' | 'meta';

export const LANES: readonly { id: Lane; label: string; sub: string }[] = [
  { id: 'claim', label: 'Agent said', sub: 'narration digests' },
  { id: 'fs', label: 'Files', sub: 'fs watcher' },
  { id: 'proc', label: 'Processes', sub: 'pgroup watcher' },
  { id: 'net', label: 'Decoy net', sub: 'marker · sink' },
  { id: 'witness', label: 'Witness', sub: 'findings · actions' },
  { id: 'meta', label: 'Recorder', sub: 'manifest · tailer · clock' },
];

const KIND_LANE: Record<Kind, Lane> = {
  assistant_claim: 'claim',
  fs_event: 'fs',
  proc_event: 'proc',
  marker_read: 'net',
  outbound_post: 'net',
  finding: 'witness',
  action_result: 'witness',
  receipt: 'witness',
  run_end: 'witness',
  manifest: 'meta',
  tail_meta: 'meta',
  clock_warning: 'meta',
  report: 'meta',
};

export function laneOf(r: BundleRecord): Lane {
  return KIND_LANE[r.kind];
}

/* ---------------------------------------------------------- run summary */

export interface RunStats {
  records: Traced;
  duration: Traced;
  laneCounts: Record<Lane, Traced>;
}

export function runStats(b: LoadedBundle, upto: number = ALL): RunStats {
  const rs = upTo(b, upto);
  const first = rs[0];
  const last = rs[rs.length - 1];
  const laneSeqs: Record<Lane, number[]> = { claim: [], proc: [], fs: [], net: [], witness: [], meta: [] };
  for (const r of rs) laneSeqs[laneOf(r)].push(r.seq);
  const laneCounts = Object.fromEntries(
    (Object.keys(laneSeqs) as Lane[]).map((l) => [
      l,
      traced(laneSeqs[l].length, laneSeqs[l], `count of records in the ${l} lane`),
    ]),
  ) as Record<Lane, Traced>;
  return {
    records: traced(rs.length, rs.map((r) => r.seq), 'count of records in the bundle'),
    duration: traced(
      first && last ? last.ts_mono - first.ts_mono : 0,
      first && last ? [first.seq, last.seq] : [],
      'ts_mono(last) − ts_mono(first), monotonic seconds',
    ),
    laneCounts,
  };
}

/* ------------------------------------------------------------- findings */

export interface FindingCounts {
  total: Traced;
  bySeverity: Record<Severity, Traced>;
  byKind: Partial<Record<FindingKind, Traced>>;
}

export function findingCounts(b: LoadedBundle, upto: number = ALL): FindingCounts {
  const fs = b.findings.filter((f) => f.seq <= upto);
  const sev = (s: Severity) => {
    const l = fs.filter((f) => f.severity === s);
    return traced(l.length, l.map((f) => f.seq), `finding records with severity=${s}`);
  };
  const byKind: Partial<Record<FindingKind, Traced>> = {};
  for (const f of fs) {
    const l = fs.filter((x) => x.fkind === f.fkind);
    byKind[f.fkind] = traced(l.length, l.map((x) => x.seq), `finding records with fkind=${f.fkind}`);
  }
  return {
    total: traced(fs.length, fs.map((f) => f.seq), 'count of finding records'),
    bySeverity: { stop: sev('stop'), warn: sev('warn'), info: sev('info') },
    byKind,
  };
}

/** Earliest (by ts_mono, then seq) evidence record a finding cites. */
export function earliestEvidence(b: LoadedBundle, f: Finding): BundleRecord | null {
  let best: BundleRecord | null = null;
  for (const s of f.evidence_seqs) {
    const r = b.bySeq.get(s);
    if (!r || r.seq >= f.seq) continue;
    if (!best || r.ts_mono < best.ts_mono || (r.ts_mono === best.ts_mono && r.seq < best.seq)) best = r;
  }
  return best;
}

/** Time-to-detect: ts_mono(finding) − ts_mono(earliest evidence), in ms. */
export function timeToDetect(b: LoadedBundle, f: Finding): Traced<number | null> {
  const e = earliestEvidence(b, f);
  if (!e) return traced(null, [f.seq], 'no resolvable evidence record');
  return traced(
    Math.max(0, (f.ts_mono - e.ts_mono) * 1000),
    [e.seq, f.seq],
    `ts_mono(finding seq ${f.seq}) − ts_mono(earliest evidence seq ${e.seq})`,
  );
}

export interface ActionTiming {
  action: ActionResult;
  latency: Traced;
  /** earliest evidence → action completed */
  evidenceToDone: Traced<number | null>;
}

export function actionTimings(b: LoadedBundle, f: Finding, upto: number = ALL): ActionTiming[] {
  const acts = (b.actionsByFinding.get(f.seq) ?? []).filter((a) => a.seq <= upto);
  const e = earliestEvidence(b, f);
  return acts.map((a) => ({
    action: a,
    latency: traced(a.latency_ms, [a.seq], `latency_ms reported by action seq ${a.seq}`),
    evidenceToDone: e
      ? traced(
          Math.max(0, (a.ts_mono - e.ts_mono) * 1000),
          [e.seq, f.seq, a.seq],
          `ts_mono(action seq ${a.seq}) − ts_mono(earliest evidence seq ${e.seq})`,
        )
      : traced(null, [a.seq], 'no resolvable evidence record'),
  }));
}

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? (s[mid] as number) : ((s[mid - 1] as number) + (s[mid] as number)) / 2;
}

/** Median time-to-detect over non-drift findings (drift is experimental and excluded). */
export function medianTimeToDetect(b: LoadedBundle, upto: number = ALL): Traced<number | null> {
  const ts = b.findings
    .filter((f) => f.seq <= upto && f.fkind !== 'drift')
    .map((f) => timeToDetect(b, f))
    .filter((t): t is Traced<number> => t.value !== null);
  return traced(
    median(ts.map((t) => t.value)),
    ts.flatMap((t) => t.seqs),
    'median of time-to-detect across non-drift findings',
  );
}

export interface StopSummary {
  status: 'not_needed' | 'ok' | 'failed' | 'pending';
  /** first stop_pgroup action */
  action: ActionResult | null;
  latency: Traced<number | null>;
  /** earliest evidence of the triggering finding → stop completed */
  evidenceToStop: Traced<number | null>;
}

export function stopSummary(b: LoadedBundle, upto: number = ALL): StopSummary {
  const stopFinding = b.findings.find((f) => f.seq <= upto && f.severity === 'stop') ?? null;
  const a = b.byKind.action_result.find((x) => x.action === 'stop_pgroup' && x.seq <= upto) ?? null;
  if (!a) {
    return {
      status: stopFinding ? 'pending' : 'not_needed',
      action: null,
      latency: traced(null, stopFinding ? [stopFinding.seq] : [], 'no stop_pgroup action recorded'),
      evidenceToStop: traced(null, stopFinding ? [stopFinding.seq] : [], 'no stop_pgroup action recorded'),
    };
  }
  const f = b.bySeq.get(a.finding_seq);
  const timing = f && f.kind === 'finding' ? actionTimings(b, f, upto).find((t) => t.action.seq === a.seq) : undefined;
  return {
    status: a.ok ? 'ok' : 'failed',
    action: a,
    latency: traced(a.latency_ms, [a.seq], `latency_ms reported by stop action seq ${a.seq}`),
    evidenceToStop: timing?.evidenceToDone ?? traced(null, [a.seq], 'triggering finding not resolvable'),
  };
}

/* --------------------------------------------------- reported vs recorded */

export type ItemStatus = 'corroborated' | 'not_observed' | 'unobservable' | 'count_mismatch';

export interface ClaimItem {
  claimSeq: number;
  subjectKind: 'path' | 'host' | 'process' | 'count' | 'none';
  /** a path / host / count — schema values only */
  subject: string;
  status: ItemStatus;
  recordSeqs: number[];
  claimed?: number;
  recorded?: number;
}

export interface ClaimRow {
  claim: AssistantClaim;
  items: ClaimItem[];
}

export interface RecordedAct {
  record: BundleRecord;
  lane: Lane;
  subject: string;
  covered: boolean;
  coveredBy: number[];
}

export interface ClaimAudit {
  rows: ClaimRow[];
  acts: RecordedAct[];
  unclaimed: RecordedAct[];
  corroborated: Traced;
  contradicted: Traced;
  unclaimedCount: Traced;
  unobservable: Traced;
  /** corroborated / (corroborated + contradicted + unclaimed); null when nothing comparable */
  agreement: Traced<number | null>;
  verdict: 'agree' | 'mismatch' | 'no_claims';
}

/** Files the assistant itself writes for the tailer are not "acts". */
const INTERNAL_PREFIXES = ['.session/'];
const SHELL_WINDOW_S = 2.5;

function hostOfDest(dest: string): string {
  return dest.split('/')[0] ?? dest;
}

function hostMatches(claimed: string, recorded: string): boolean {
  const c = claimed.toLowerCase().replace(/^https?:\/\//, '').split('/')[0] ?? '';
  const r = recorded.toLowerCase();
  if (!c) return false;
  return c === r || r.startsWith(`${c}:`) || c.startsWith(`${r}`);
}

/**
 * Compare every assistant_claim against the independently recorded acts.
 * Deterministic, local, no model involved — the analyst report (if any) is
 * shown alongside, never instead.
 */
export function claimAudit(b: LoadedBundle, upto: number = ALL): ClaimAudit {
  const rs = upTo(b, upto);
  const claims = rs.filter((r): r is AssistantClaim => r.kind === 'assistant_claim');
  const spawns = rs.filter((r) => r.kind === 'proc_event' && r.op === 'spawn');
  const rootPid = spawns[0]?.kind === 'proc_event' ? spawns[0].pid : null;

  const acts: RecordedAct[] = [];
  for (const r of rs) {
    if (r.kind === 'fs_event' && !INTERNAL_PREFIXES.some((p) => r.path.startsWith(p))) {
      acts.push({ record: r, lane: 'fs', subject: r.path, covered: false, coveredBy: [] });
    } else if (r.kind === 'outbound_post') {
      acts.push({ record: r, lane: 'net', subject: hostOfDest(r.dest), covered: false, coveredBy: [] });
    } else if (r.kind === 'marker_read') {
      acts.push({
        record: r,
        lane: 'net',
        subject: `127.0.0.1:${b.manifest.marker_port}`,
        covered: false,
        coveredBy: [],
      });
    } else if (r.kind === 'proc_event' && r.op === 'spawn' && r.pid !== rootPid) {
      acts.push({ record: r, lane: 'proc', subject: r.exe ?? `pid ${r.pid}`, covered: false, coveredBy: [] });
    }
  }

  const cover = (a: RecordedAct, claimSeq: number) => {
    a.covered = true;
    if (!a.coveredBy.includes(claimSeq)) a.coveredBy.push(claimSeq);
  };

  const rows: ClaimRow[] = claims.map((c) => {
    const items: ClaimItem[] = [];
    switch (c.tool) {
      case 'write':
      case 'edit': {
        for (const p of c.claimed_paths) {
          const hits = acts.filter((a) => a.lane === 'fs' && a.subject === p);
          hits.forEach((a) => cover(a, c.seq));
          items.push({
            claimSeq: c.seq,
            subjectKind: 'path',
            subject: p,
            status: hits.length ? 'corroborated' : 'not_observed',
            recordSeqs: hits.map((a) => a.record.seq),
          });
        }
        if (c.claimed_count !== null) {
          const writes = acts.filter(
            (a) => a.lane === 'fs' && a.record.kind === 'fs_event' && a.record.op !== 'write_denied',
          );
          const distinct = new Set(writes.map((a) => a.subject));
          items.push({
            claimSeq: c.seq,
            subjectKind: 'count',
            subject: 'files changed',
            status: distinct.size === c.claimed_count ? 'corroborated' : 'count_mismatch',
            recordSeqs: writes.map((a) => a.record.seq),
            claimed: c.claimed_count,
            recorded: distinct.size,
          });
        }
        break;
      }
      case 'http': {
        for (const h of c.claimed_hosts) {
          const hits = acts.filter((a) => a.lane === 'net' && hostMatches(h, a.subject));
          hits.forEach((a) => cover(a, c.seq));
          items.push({
            claimSeq: c.seq,
            subjectKind: 'host',
            subject: h,
            status: hits.length ? 'corroborated' : 'not_observed',
            recordSeqs: hits.map((a) => a.record.seq),
          });
        }
        break;
      }
      case 'shell': {
        const candidates = acts
          .filter((a) => a.lane === 'proc' && !a.covered && Math.abs(a.record.ts_mono - c.ts_mono) <= SHELL_WINDOW_S)
          .sort((x, y) => Math.abs(x.record.ts_mono - c.ts_mono) - Math.abs(y.record.ts_mono - c.ts_mono));
        const hit = candidates[0];
        if (hit) cover(hit, c.seq);
        items.push({
          claimSeq: c.seq,
          subjectKind: 'process',
          subject: hit ? hit.subject : 'a command',
          status: hit ? 'corroborated' : 'not_observed',
          recordSeqs: hit ? [hit.record.seq] : [],
        });
        break;
      }
      default: {
        // read / search / other: reads are not observable by an fs watcher.
        const subjects = c.claimed_paths.length ? c.claimed_paths : c.claimed_hosts;
        if (!subjects.length) {
          items.push({ claimSeq: c.seq, subjectKind: 'none', subject: c.tool, status: 'unobservable', recordSeqs: [] });
        }
        for (const s of subjects) {
          items.push({
            claimSeq: c.seq,
            subjectKind: c.claimed_paths.length ? 'path' : 'host',
            subject: s,
            status: 'unobservable',
            recordSeqs: [],
          });
        }
      }
    }
    return { claim: c, items };
  });

  const items = rows.flatMap((r) => r.items);
  const by = (s: ItemStatus) => items.filter((i) => i.status === s);
  const corr = by('corroborated');
  const contra = [...by('not_observed'), ...by('count_mismatch')];
  const unobs = by('unobservable');
  const unclaimed = acts.filter((a) => !a.covered);

  const seqsOf = (xs: ClaimItem[]) => xs.flatMap((i) => [i.claimSeq, ...i.recordSeqs]);
  const corroborated = traced(corr.length, seqsOf(corr), 'claim items matched by a recorded event');
  const contradicted = traced(
    contra.length,
    seqsOf(contra),
    'claim items with no matching record, or a claimed count ≠ recorded count',
  );
  const unclaimedCount = traced(
    unclaimed.length,
    unclaimed.map((a) => a.record.seq),
    'recorded file / process / decoy-network events no claim mentions',
  );
  const unobservable = traced(unobs.length, seqsOf(unobs), 'claim items a passive recorder cannot observe (e.g. reads)');
  const denom = corr.length + contra.length + unclaimed.length;
  const agreement = traced(
    denom ? corr.length / denom : null,
    [...corroborated.seqs, ...contradicted.seqs, ...unclaimedCount.seqs],
    'corroborated ÷ (corroborated + contradicted + unclaimed)',
  );
  const verdict: ClaimAudit['verdict'] = !claims.length
    ? 'no_claims'
    : contra.length || unclaimed.length
      ? 'mismatch'
      : 'agree';
  return { rows, acts, unclaimed, corroborated, contradicted, unclaimedCount, unobservable, agreement, verdict };
}

/* ---------------------------------------------------------------- drift */

export interface DriftReading {
  finding: Finding;
  score: Traced<number | null>;
}

export function driftReadings(b: LoadedBundle, upto: number = ALL): DriftReading[] {
  return b.findings
    .filter((f) => f.fkind === 'drift' && f.seq <= upto)
    .map((f) => ({
      finding: f,
      score: traced(f.score, [f.seq], `score field of drift finding seq ${f.seq} (robust z, median/MAD)`),
    }));
}

/* ---------------------------------------------------------------- misc */

/** Index of the last record with ts_mono <= t (records are seq-ordered, ts_mono monotonic). */
export function seqAtTime(b: LoadedBundle, t: number): number {
  let lo = 0;
  let hi = b.records.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const r = b.records[mid] as BundleRecord;
    if (r.ts_mono <= t) {
      ans = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return ans < 0 ? -1 : (b.records[ans] as BundleRecord).seq;
}

/** A finding is "loud" if it should paint a band across the timeline. */
export function findingBandSeverity(f: Finding): Severity {
  return f.severity;
}

/** The record that a finding most directly concerns (latest evidence). */
export function headlineEvidence(b: LoadedBundle, f: Finding): BundleRecord | null {
  const ev = f.evidence_seqs.map((s) => b.bySeq.get(s)).filter((r): r is BundleRecord => !!r);
  return ev[ev.length - 1] ?? null;
}
