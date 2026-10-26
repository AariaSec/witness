/**
 * describe — one-line, console-authored summaries of a record, built ONLY
 * from schema fields (enums, paths, counts, short digests). Never prose from
 * the bundle, because the bundle has none.
 */
import type { BundleRecord } from '../schema/bundle';
import { ACTION_LABEL, FINDING_TITLE, RUN_END_TEXT } from './codes';
import { fmtBytes, shortHash } from './format';

export interface Summary {
  /** short verb-ish headline */
  title: string;
  /** secondary mono fragments */
  parts: string[];
  /** paint red: decoy value seen / protected path / failed action */
  alarm?: boolean;
}

export function describe(r: BundleRecord): Summary {
  switch (r.kind) {
    case 'manifest':
      return {
        title: `run ${r.run_id}`,
        parts: [`schema ${r.bundle_schema}`, r.platform, `witness ${r.witness_version}`, r.simulated ? 'SIMULATED' : 'live'],
      };
    case 'marker_read':
      return {
        title: 'decoy key fetched',
        parts: [`GET ${r.path}`, r.peer_exe ? `${r.peer_exe} · pid ${r.peer_pid ?? '?'}` : `pid ${r.peer_pid ?? '?'}`],
        alarm: true,
      };
    case 'outbound_post':
      return {
        title: r.contains_marker ? 'POST carrying decoy value' : 'POST to decoy sink',
        parts: [
          r.dest,
          fmtBytes(r.bytes),
          r.content_type,
          `body ${shortHash(r.body_sha256)}`,
          r.peer_exe ? `${r.peer_exe} · pid ${r.peer_pid ?? '?'}` : `pid ${r.peer_pid ?? '?'}`,
        ],
        alarm: r.contains_marker,
      };
    case 'fs_event':
      return {
        title: `${r.op} ${r.path}`,
        parts: [fmtBytes(r.bytes), r.sha256 ? `sha ${shortHash(r.sha256)}` : 'no digest', ...(r.protected ? ['PROTECTED'] : [])],
        alarm: r.protected || r.op === 'write_denied',
      };
    case 'proc_event':
      return {
        title: `${r.op} ${r.exe ?? '(opaque)'}`,
        parts: [`pid ${r.pid}`, r.ppid !== null ? `ppid ${r.ppid}` : 'ppid ?', r.cmdline_digest ? `argv ${shortHash(r.cmdline_digest)}` : 'argv —'],
        alarm: r.op === 'escape',
      };
    case 'assistant_claim': {
      const subj = [...r.claimed_paths, ...r.claimed_hosts];
      return {
        title: `claims ${r.tool}${subj.length ? ` ${subj.join(', ')}` : ''}`,
        parts: [
          r.source,
          ...(r.claimed_count !== null ? [`count ${r.claimed_count}`] : []),
          `line ${shortHash(r.line_digest)}`,
        ],
      };
    }
    case 'tail_meta':
      return {
        title: `tailer ${r.event}`,
        parts: [r.file, ...(r.bytes_skipped ? [`${r.bytes_skipped} B skipped`] : [])],
      };
    case 'finding':
      return {
        title: FINDING_TITLE[r.fkind],
        parts: [
          r.severity.toUpperCase(),
          `evidence ${r.evidence_seqs.map((s) => `#${s}`).join(' ')}`,
          ...(r.score !== null ? [`score ${r.score}`] : []),
          `detector ${r.detector_version}`,
        ],
        alarm: r.severity === 'stop',
      };
    case 'action_result':
      return {
        title: `${ACTION_LABEL[r.action] ?? r.action} ${r.ok ? '✓' : '✗ FAILED'}`,
        parts: [`for finding #${r.finding_seq}`, `${r.latency_ms} ms`, ...(r.detail ? [r.detail] : [])],
        alarm: !r.ok,
      };
    case 'clock_warning':
      return { title: 'wall clock jumped', parts: [`Δ ${r.delta_s > 0 ? '+' : ''}${r.delta_s}s`, 'ordering by seq'] };
    case 'run_end':
      return {
        title: `run ended — ${RUN_END_TEXT[r.reason] ?? r.reason}`,
        parts: [`exit ${r.exit_code ?? '—'}`, `${r.records} records`],
      };
    case 'receipt':
      return {
        title: 'receipt signed',
        parts: [`final ${shortHash(r.body.final_digest)}`, `${r.body.records} records`, `stop ${r.body.stop_status}`],
      };
    case 'report':
      return {
        title: `analyst report · ${r.analyst_status}`,
        parts: [r.model_id, `${r.tool_calls} tool calls`, `${r.summary_codes.length} codes`],
      };
  }
}

/** All fields of a record except Base, for the inspector (values are schema metadata). */
export function fieldsOf(r: BundleRecord): [string, unknown][] {
  const skip = new Set(['seq', 'kind', 'ts_wall', 'ts_mono', 'prev', 'digest']);
  return Object.entries(r).filter(([k]) => !skip.has(k));
}
