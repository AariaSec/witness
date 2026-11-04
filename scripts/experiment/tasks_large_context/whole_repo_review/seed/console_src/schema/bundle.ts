/**
 * witness bundle schema — TypeScript mirror of the frozen pydantic models
 * (14_fable_architecture_phases.md §3.2, bundle_schema "1.0").
 *
 * A bundle is `bundle.jsonl`: one record per line, discriminated on `kind`.
 * No record carries prompt/response text, file contents or secrets — every
 * value is a digest, enum, count, path, timestamp or small structured field.
 * Nothing in the console may ever imply otherwise.
 *
 * NOTE: the architecture plan calls for this file to be generated from
 * schemas/bundle.schema.json by scripts/gen_schemas.py. Until that generator
 * lands it is hand-written against the frozen field list; keep the two in
 * lock-step (the runtime guard in loadBundle.ts checks required fields).
 */

export const SUPPORTED_SCHEMA_MAJOR = 1;
/** Highest MINOR this console was written against. Newer MINOR → warn, still render. */
export const KNOWN_SCHEMA_MINOR = 0;

export const KINDS = [
  'manifest',
  'marker_read',
  'outbound_post',
  'fs_event',
  'proc_event',
  'assistant_claim',
  'tail_meta',
  'finding',
  'action_result',
  'clock_warning',
  'run_end',
  'receipt',
  'report',
] as const;
export type Kind = (typeof KINDS)[number];

/** sha256 hex (64 lowercase hex chars). */
export type Digest = string;
/** Path relative to the lab root; never prose. */
export type RelPath = string;

export type FsOp = 'create' | 'modify' | 'delete' | 'move' | 'write_denied';
export type ProcOp = 'spawn' | 'exit' | 'exec' | 'opaque' | 'escape';
export type ClaimTool = 'read' | 'write' | 'edit' | 'shell' | 'http' | 'search' | 'other';
export type FindingKind =
  | 'marker_read'
  | 'outbound_post'
  | 'mismatch'
  | 'protected_write'
  | 'pgroup_escape'
  | 'drift';
export type Severity = 'info' | 'warn' | 'stop';
/** Loudest first. */
export const SEVERITIES: readonly Severity[] = ['stop', 'warn', 'info'];
export type ContentType = 'json' | 'form' | 'text' | 'binary' | 'other';

export interface Base<K extends Kind> {
  seq: number;
  kind: K;
  /** unix seconds — display only; NEVER used for ordering (the wall clock can jump). */
  ts_wall: number;
  /** monotonic seconds since run start — the console's time axis. */
  ts_mono: number;
  prev: Digest | null;
  digest: Digest | null;
}

export interface Manifest extends Base<'manifest'> {
  bundle_schema: string;
  witness_version: string;
  run_id: string;
  platform: 'darwin' | 'linux';
  marker_port: number;
  sink_port: number;
  lab_root_digest: Digest;
  protected_paths: RelPath[];
  policy_hash: Digest;
  assistant_argv_digest: Digest;
  degraded: string[];
  simulated: boolean;
  /** base64 Ed25519 public key (raw 32 bytes) */
  pubkey: string;
}

export interface MarkerRead extends Base<'marker_read'> {
  peer_pid: number | null;
  peer_exe: string | null;
  path: '/v1/token';
  ua_digest: Digest | null;
}

export interface OutboundPost extends Base<'outbound_post'> {
  peer_pid: number | null;
  peer_exe: string | null;
  /** "127.0.0.1:<port>/<path>" — the decoy sink, never a real destination */
  dest: string;
  bytes: number;
  body_sha256: Digest;
  content_type: ContentType;
  /** the sink saw the decoy value while streaming; the body itself is discarded */
  contains_marker: boolean;
}

export interface FsEvent extends Base<'fs_event'> {
  op: FsOp;
  path: RelPath;
  bytes: number | null;
  sha256: Digest | null;
  protected: boolean;
}

export interface ProcEvent extends Base<'proc_event'> {
  op: ProcOp;
  pid: number;
  ppid: number | null;
  exe: string | null;
  cmdline_digest: Digest | null;
}

export interface AssistantClaim extends Base<'assistant_claim'> {
  source: 'session_log' | 'json_output';
  tool: ClaimTool;
  claimed_paths: RelPath[];
  claimed_hosts: string[];
  claimed_count: number | null;
  /** digest of the raw narration line — the line itself is never stored */
  line_digest: Digest;
}

export interface TailMeta extends Base<'tail_meta'> {
  event: 'open' | 'reopen' | 'rotate' | 'parse_error' | 'truncate';
  file: RelPath;
  bytes_skipped: number;
}

export interface Finding extends Base<'finding'> {
  fkind: FindingKind;
  severity: Severity;
  /** references to EARLIER records' seq */
  evidence_seqs: number[];
  /** drift only */
  score: number | null;
  detector_version: string;
}

export type ActionKind = 'close_marker' | 'stop_pgroup' | 'sign_receipt';

export interface ActionResult extends Base<'action_result'> {
  action: ActionKind;
  finding_seq: number;
  ok: boolean;
  latency_ms: number;
  /** small enum on the backend: term | kill | failed | noop | already_closed */
  detail: string | null;
}

export interface ClockWarning extends Base<'clock_warning'> {
  delta_s: number;
}

export interface RunEnd extends Base<'run_end'> {
  reason: 'assistant_exit' | 'stopped' | 'interrupted' | 'timeout' | 'ledger_error';
  exit_code: number | null;
  records: number;
}

export interface ReceiptBody {
  run_id: string;
  final_digest: Digest;
  records: number;
  findings: Record<string, number>;
  stop_status: 'not_needed' | 'ok' | 'failed';
  policy_hash: Digest;
  signed_at: number;
  pubkey: string;
  /** Receipt v0.2, additive — absent on pre-v0.2 receipts. */
  git_commit_sha?: string | null;
  git_tree_digest?: string | null;
  changed_file_digests?: Record<string, string>;
  coverage?: string[];
}

export interface Receipt extends Base<'receipt'> {
  body: ReceiptBody;
  /** base64 Ed25519 signature over canonical JSON of `body` */
  sig: string;
}

export interface ReportStep {
  seq_refs: number[];
  code: string;
  severity: string;
}

export interface Discrepancy {
  claim_seq: number;
  record_seqs: number[];
  code: string;
}

export interface Report extends Base<'report'> {
  model_id: string;
  prompt_version: Digest;
  analyst_status: 'ok' | 'offline' | 'schema_fail';
  tool_calls: number;
  /** enum codes only — rendered through a fixed code→English table, never free text */
  summary_codes: string[];
  timeline: ReportStep[];
  reported_vs_recorded: Discrepancy[];
  confidence: number;
}

export type BundleRecord =
  | Manifest
  | MarkerRead
  | OutboundPost
  | FsEvent
  | ProcEvent
  | AssistantClaim
  | TailMeta
  | Finding
  | ActionResult
  | ClockWarning
  | RunEnd
  | Receipt
  | Report;

export type RecordOfKind<K extends Kind> = Extract<BundleRecord, { kind: K }>;

/** Required (non-Base) fields per kind — used by the runtime guard in loadBundle. */
export const REQUIRED_FIELDS: { readonly [K in Kind]: readonly string[] } = {
  manifest: [
    'bundle_schema',
    'witness_version',
    'run_id',
    'platform',
    'marker_port',
    'sink_port',
    'lab_root_digest',
    'protected_paths',
    'policy_hash',
    'assistant_argv_digest',
    'degraded',
    'simulated',
    'pubkey',
  ],
  marker_read: ['peer_pid', 'peer_exe', 'path', 'ua_digest'],
  outbound_post: ['peer_pid', 'peer_exe', 'dest', 'bytes', 'body_sha256', 'content_type', 'contains_marker'],
  fs_event: ['op', 'path', 'bytes', 'sha256', 'protected'],
  proc_event: ['op', 'pid', 'ppid', 'exe', 'cmdline_digest'],
  assistant_claim: ['source', 'tool', 'claimed_paths', 'claimed_hosts', 'claimed_count', 'line_digest'],
  tail_meta: ['event', 'file', 'bytes_skipped'],
  finding: ['fkind', 'severity', 'evidence_seqs', 'score', 'detector_version'],
  action_result: ['action', 'finding_seq', 'ok', 'latency_ms', 'detail'],
  clock_warning: ['delta_s'],
  run_end: ['reason', 'exit_code', 'records'],
  receipt: ['body', 'sig'],
  report: [
    'model_id',
    'prompt_version',
    'analyst_status',
    'tool_calls',
    'summary_codes',
    'timeline',
    'reported_vs_recorded',
    'confidence',
  ],
};

export const BASE_FIELDS = ['seq', 'kind', 'ts_wall', 'ts_mono', 'prev', 'digest'] as const;

export function isKind(v: unknown): v is Kind {
  return typeof v === 'string' && (KINDS as readonly string[]).includes(v);
}
