/**
 * divergence — the data behind the "Agent said / Reality recorded" flow.
 *
 * Pure function of a LoadedBundle (+ replay cursor). Every step it returns IS
 * a bundle record (`step.record`), in seq order; nothing is synthesised.
 *
 * The two paths are separated by `weight` — the cumulative severity of the
 * findings fired so far (warn = 1, stop = 2, non-drift info = 0.5; drift is
 * experimental and contributes 0, as in medianTimeToDetect). So the paths run
 * together until a detector actually fires, and split AT that finding's seq.
 *
 * Per-node status (covered / never mentioned / contradicted …) comes straight
 * from `claimAudit` — the same deterministic diff the ClaimDiff panel shows —
 * evaluated as of the cursor, so the two views can never disagree.
 */
import type { AssistantClaim, BundleRecord, Finding, Severity } from '../schema/bundle';
import type { LoadedBundle } from './loadBundle';
import { claimAudit, traced, type Traced } from './derive';

export type StepSide = 'claim' | 'reality' | 'finding' | 'stop';

export type StepStatus =
  /** reality act some claim covers */
  | 'covered'
  /** reality act no claim covers (ClaimDiff: NEVER MENTIONED) */
  | 'unclaimed'
  /** reality record that is not a comparable act (root spawn, exits) */
  | 'context'
  /** claim fully matched by recorded acts */
  | 'corroborated'
  /** claim with a not-observed item or count mismatch */
  | 'contradicted'
  /** claim a passive recorder cannot check (reads, searches) */
  | 'unobservable'
  | 'finding'
  | 'stop';

export interface DivergenceStep {
  seq: number;
  record: BundleRecord;
  side: StepSide;
  status: StepStatus;
  /** cumulative separation weight AFTER this step */
  weight: number;
  /** claim seqs covering this act (covered acts only) */
  coveredBy: number[];
  severity?: Severity;
}

export interface Divergence {
  steps: DivergenceStep[];
  /** the first finding that split the paths (null → still in step) */
  splitAt: Finding | null;
  /** final weight over the steps ≤ cursor */
  weight: Traced;
  /** weight over the whole bundle (used to fix the vertical scale so replay never rescales) */
  maxWeight: number;
}

export const SEVERITY_WEIGHT: Record<Severity, number> = { stop: 2, warn: 1, info: 0.5 };

const INTERNAL_PREFIXES = ['.session/'];

export function findingWeight(f: Finding): number {
  return f.fkind === 'drift' ? 0 : SEVERITY_WEIGHT[f.severity];
}

function claimStatus(items: { status: string }[]): StepStatus {
  if (items.some((i) => i.status === 'not_observed' || i.status === 'count_mismatch')) return 'contradicted';
  if (items.length && items.every((i) => i.status === 'unobservable')) return 'unobservable';
  return 'corroborated';
}

/** Records drawn on the flow, in seq order. */
export function isFlowRecord(r: BundleRecord): boolean {
  switch (r.kind) {
    case 'assistant_claim':
    case 'proc_event':
    case 'marker_read':
    case 'outbound_post':
    case 'finding':
      return true;
    case 'fs_event':
      return !INTERNAL_PREFIXES.some((p) => r.path.startsWith(p));
    case 'action_result':
      return r.action === 'stop_pgroup';
    default:
      return false;
  }
}

export function divergence(b: LoadedBundle, cursor: number = Number.POSITIVE_INFINITY): Divergence {
  const audit = claimAudit(b, cursor);
  const actBySeq = new Map(audit.acts.map((a) => [a.record.seq, a]));
  const rowBySeq = new Map(audit.rows.map((r) => [r.claim.seq, r]));

  let w = 0;
  let maxWeight = 0;
  let splitAt: Finding | null = null;
  const weightSeqs: number[] = [];
  const steps: DivergenceStep[] = [];

  for (const r of b.records) {
    if (!isFlowRecord(r)) continue;
    const future = r.seq > cursor;
    if (r.kind === 'finding') {
      const fw = findingWeight(r);
      maxWeight += fw;
      if (!future) {
        w += fw;
        if (fw > 0) {
          weightSeqs.push(r.seq);
          if (!splitAt) splitAt = r;
        }
      }
      steps.push({ seq: r.seq, record: r, side: 'finding', status: 'finding', weight: future ? NaN : w, coveredBy: [], severity: r.severity });
      continue;
    }
    if (r.kind === 'action_result') {
      steps.push({ seq: r.seq, record: r, side: 'stop', status: 'stop', weight: future ? NaN : w, coveredBy: [] });
      continue;
    }
    if (r.kind === 'assistant_claim') {
      const row = rowBySeq.get(r.seq);
      steps.push({
        seq: r.seq,
        record: r as AssistantClaim,
        side: 'claim',
        status: row ? claimStatus(row.items) : 'unobservable',
        weight: future ? NaN : w,
        coveredBy: [],
      });
      continue;
    }
    const act = actBySeq.get(r.seq);
    steps.push({
      seq: r.seq,
      record: r,
      side: 'reality',
      status: act ? (act.covered ? 'covered' : 'unclaimed') : 'context',
      weight: future ? NaN : w,
      coveredBy: act ? [...act.coveredBy] : [],
    });
  }

  // future steps keep the as-of-cursor weight for layout (they are drawn ghosted)
  for (const s of steps) if (Number.isNaN(s.weight)) s.weight = w;

  return {
    steps,
    splitAt,
    weight: traced(w, weightSeqs, 'cumulative finding severity so far (warn = 1, stop = 2, info = ½, drift = 0)'),
    maxWeight,
  };
}
