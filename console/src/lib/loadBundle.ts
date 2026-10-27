/**
 * loadBundle — parse a witness `bundle.jsonl`, validate it against the frozen
 * schema, and build the in-memory index every view reads from.
 *
 * Honesty over polish: structural problems that do not make the bundle
 * unreadable (gaps, broken chain links, unexpected keys) are collected as
 * `issues` and surfaced in the UI — the bundle still replays. Only problems
 * that make the bundle meaningless (no manifest, unsupported MAJOR schema,
 * nothing parseable) throw a BundleLoadError.
 */
import {
  BASE_FIELDS,
  KINDS,
  KNOWN_SCHEMA_MINOR,
  OPTIONAL_FIELDS,
  REQUIRED_FIELDS,
  SUPPORTED_SCHEMA_MAJOR,
  isKind,
  type ActionResult,
  type BundleRecord,
  type Finding,
  type Kind,
  type Manifest,
  type Receipt,
  type RecordOfKind,
  type Report,
  type RunEnd,
} from '../schema/bundle';

export type IssueLevel = 'error' | 'warn';

export type IssueCode =
  | 'json_parse'
  | 'not_object'
  | 'bad_kind'
  | 'missing_field'
  | 'bad_base_field'
  | 'unexpected_key'
  | 'long_string'
  | 'duplicate_seq'
  | 'seq_gap'
  | 'manifest_not_first'
  | 'chain_link'
  | 'evidence_forward_ref'
  | 'evidence_missing'
  | 'schema_minor_newer'
  | 'last_record'
  | 'ts_mono_regress';

/** Every issue message is console-authored English; nothing is copied from the bundle. */
export interface Issue {
  level: IssueLevel;
  code: IssueCode;
  /** 1-based line number in the file, when the issue is line-scoped */
  line?: number;
  seq?: number;
  /** key name or kind involved — schema identifiers only, never values */
  key?: string;
}

export class BundleLoadError extends Error {
  constructor(
    public readonly code: 'empty' | 'no_manifest' | 'schema_major' | 'unparseable',
    message: string,
  ) {
    super(message);
    this.name = 'BundleLoadError';
  }
}

export interface ChainCheck {
  /** true iff seq 0 has prev=null and every record's prev equals the previous record's digest */
  ok: boolean;
  /** number of prev→digest links checked */
  links: number;
  /** seq of the first record whose `prev` does not match, or null */
  firstBadSeq: number | null;
  /** seqs that participate in the check (all of them) */
  seqs: number[];
}

export interface SchemaInfo {
  version: string;
  major: number;
  minor: number;
  newerMinor: boolean;
}

export type ByKind = { [K in Kind]: RecordOfKind<K>[] };

export interface LoadedBundle {
  sourceName: string;
  manifest: Manifest;
  /** sorted by seq — the ONLY ordering the console uses */
  records: BundleRecord[];
  bySeq: Map<number, BundleRecord>;
  byKind: ByKind;
  findings: Finding[];
  actionsByFinding: Map<number, ActionResult[]>;
  receipt: Receipt | null;
  report: Report | null;
  runEnd: RunEnd | null;
  /** raw JSON text per seq — lets verifyReceipt canonicalise numbers losslessly */
  rawLineBySeq: Map<number, string>;
  schema: SchemaInfo;
  chain: ChainCheck;
  issues: Issue[];
  /** ts_mono span of the run (seconds) */
  span: { t0: number; t1: number };
  /** bytes of the source file */
  bytes: number;
}

/** Strings longer than this in a record are flagged — bundles hold identifiers, not prose. */
export const MAX_STRING_LEN = 256;

const HEX64 = /^[0-9a-f]{64}$/;

function emptyByKind(): ByKind {
  const o = {} as Record<Kind, BundleRecord[]>;
  for (const k of KINDS) o[k] = [];
  return o as ByKind;
}

function scanLongStrings(v: unknown, depth = 0): boolean {
  if (depth > 6) return false;
  if (typeof v === 'string') return v.length > MAX_STRING_LEN;
  if (Array.isArray(v)) return v.some((x) => scanLongStrings(x, depth + 1));
  if (v && typeof v === 'object') return Object.values(v).some((x) => scanLongStrings(x, depth + 1));
  return false;
}

export function parseSchemaVersion(v: string): { major: number; minor: number } | null {
  const m = /^(\d+)\.(\d+)$/.exec(v.trim());
  if (!m) return null;
  return { major: Number(m[1]), minor: Number(m[2]) };
}

/**
 * Parse and index a bundle. Pure (no I/O) — `text` is the full file contents.
 */
export function parseBundle(text: string, sourceName = 'bundle.jsonl'): LoadedBundle {
  const issues: Issue[] = [];
  const lines = text.split(/\r?\n/);
  const parsed: { rec: BundleRecord; raw: string; line: number }[] = [];

  lines.forEach((raw, i) => {
    const lineNo = i + 1;
    const trimmed = raw.trim();
    if (!trimmed) return;
    let obj: unknown;
    try {
      obj = JSON.parse(trimmed);
    } catch {
      issues.push({ level: 'error', code: 'json_parse', line: lineNo });
      return;
    }
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      issues.push({ level: 'error', code: 'not_object', line: lineNo });
      return;
    }
    const o = obj as Record<string, unknown>;
    if (!isKind(o.kind)) {
      issues.push({ level: 'error', code: 'bad_kind', line: lineNo });
      return;
    }
    const kind = o.kind;
    if (
      typeof o.seq !== 'number' ||
      !Number.isInteger(o.seq) ||
      o.seq < 0 ||
      typeof o.ts_wall !== 'number' ||
      typeof o.ts_mono !== 'number' ||
      !(o.prev === null || (typeof o.prev === 'string' && HEX64.test(o.prev))) ||
      !(o.digest === null || (typeof o.digest === 'string' && HEX64.test(o.digest)))
    ) {
      issues.push({ level: 'error', code: 'bad_base_field', line: lineNo, key: kind });
      return;
    }
    const required = REQUIRED_FIELDS[kind];
    const missing = required.filter((f) => !(f in o));
    if (missing.length) {
      for (const f of missing) issues.push({ level: 'error', code: 'missing_field', line: lineNo, seq: o.seq, key: f });
      return;
    }
    const allowed = new Set<string>([...BASE_FIELDS, ...required, ...(OPTIONAL_FIELDS[kind] ?? [])]);
    for (const k of Object.keys(o)) {
      // extra="forbid" on the backend: an unknown key is a content-leak smell.
      if (!allowed.has(k)) issues.push({ level: 'warn', code: 'unexpected_key', line: lineNo, seq: o.seq, key: k });
    }
    if (scanLongStrings(o)) issues.push({ level: 'warn', code: 'long_string', line: lineNo, seq: o.seq, key: kind });
    parsed.push({ rec: o as unknown as BundleRecord, raw: trimmed, line: lineNo });
  });

  if (parsed.length === 0) {
    if (lines.every((l) => !l.trim())) throw new BundleLoadError('empty', 'The bundle file is empty.');
    throw new BundleLoadError('unparseable', 'No line of this file is a valid witness record.');
  }

  // Order strictly by seq. Never by wall clock.
  parsed.sort((a, b) => a.rec.seq - b.rec.seq);

  const bySeq = new Map<number, BundleRecord>();
  const rawLineBySeq = new Map<number, string>();
  const records: BundleRecord[] = [];
  for (const p of parsed) {
    if (bySeq.has(p.rec.seq)) {
      issues.push({ level: 'error', code: 'duplicate_seq', line: p.line, seq: p.rec.seq });
      continue;
    }
    bySeq.set(p.rec.seq, p.rec);
    rawLineBySeq.set(p.rec.seq, p.raw);
    records.push(p.rec);
  }

  const first = records[0];
  if (!first || first.kind !== 'manifest') {
    const m = records.find((r) => r.kind === 'manifest');
    if (!m) throw new BundleLoadError('no_manifest', 'This file has no manifest record, so it is not a witness bundle.');
    issues.push({ level: 'error', code: 'manifest_not_first', seq: m.seq });
  }
  const manifest = (first?.kind === 'manifest' ? first : records.find((r) => r.kind === 'manifest')) as Manifest;

  const ver = parseSchemaVersion(String(manifest.bundle_schema));
  if (!ver || ver.major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new BundleLoadError(
      'schema_major',
      `Unsupported bundle_schema "${String(manifest.bundle_schema).slice(0, 16)}" — this console reads ${SUPPORTED_SCHEMA_MAJOR}.x bundles.`,
    );
  }
  const schema: SchemaInfo = {
    version: `${ver.major}.${ver.minor}`,
    major: ver.major,
    minor: ver.minor,
    newerMinor: ver.minor > KNOWN_SCHEMA_MINOR,
  };
  if (schema.newerMinor) issues.push({ level: 'warn', code: 'schema_minor_newer', seq: manifest.seq });

  // Contiguity from 0.
  records.forEach((r, i) => {
    if (r.seq !== i) {
      const expected = i === 0 ? 0 : (records[i - 1]?.seq ?? -1) + 1;
      if (r.seq !== expected) issues.push({ level: 'error', code: 'seq_gap', seq: r.seq });
    }
  });

  // Hash-chain linkage: prev(i) == digest(i-1). (Digest recomputation is the
  // recorder's `witness verify`; the console checks the links it can check
  // without assuming the byte-level construction.)
  let firstBadSeq: number | null = null;
  let links = 0;
  records.forEach((r, i) => {
    if (i === 0) {
      if (r.prev !== null && firstBadSeq === null) firstBadSeq = r.seq;
      return;
    }
    links++;
    const prevRec = records[i - 1];
    if (!prevRec || r.prev === null || r.prev !== prevRec.digest || prevRec.digest === null) {
      if (firstBadSeq === null) firstBadSeq = r.seq;
    }
  });
  if (firstBadSeq !== null) issues.push({ level: 'error', code: 'chain_link', seq: firstBadSeq });
  const chain: ChainCheck = { ok: firstBadSeq === null, links, firstBadSeq, seqs: records.map((r) => r.seq) };

  // Monotonic clock must not regress.
  records.forEach((r, i) => {
    const p = records[i - 1];
    if (p && r.ts_mono < p.ts_mono) issues.push({ level: 'warn', code: 'ts_mono_regress', seq: r.seq });
  });

  const byKind = emptyByKind();
  for (const r of records) (byKind[r.kind] as BundleRecord[]).push(r);

  const findings = byKind.finding;
  for (const f of findings) {
    for (const e of f.evidence_seqs) {
      if (e >= f.seq) issues.push({ level: 'error', code: 'evidence_forward_ref', seq: f.seq });
      else if (!bySeq.has(e)) issues.push({ level: 'warn', code: 'evidence_missing', seq: f.seq });
    }
  }

  const actionsByFinding = new Map<number, ActionResult[]>();
  for (const a of byKind.action_result) {
    const list = actionsByFinding.get(a.finding_seq) ?? [];
    list.push(a);
    actionsByFinding.set(a.finding_seq, list);
  }

  const last = records[records.length - 1];
  if (last && last.kind !== 'receipt' && last.kind !== 'report') {
    issues.push({ level: 'warn', code: 'last_record', seq: last.seq });
  }

  const monos = records.map((r) => r.ts_mono);
  const span = { t0: Math.min(...monos), t1: Math.max(...monos) };

  return {
    sourceName,
    manifest,
    records,
    bySeq,
    byKind,
    findings,
    actionsByFinding,
    receipt: byKind.receipt[byKind.receipt.length - 1] ?? null,
    report: byKind.report[byKind.report.length - 1] ?? null,
    runEnd: byKind.run_end[byKind.run_end.length - 1] ?? null,
    rawLineBySeq,
    schema,
    chain,
    issues,
    span,
    bytes: new TextEncoder().encode(text).length,
  };
}

/** Fixed English for each issue code (console-authored). */
export const ISSUE_TEXT: Record<IssueCode, string> = {
  json_parse: 'Line is not valid JSON',
  not_object: 'Line is not a JSON object',
  bad_kind: 'Unknown record kind',
  missing_field: 'Required field missing',
  bad_base_field: 'Malformed seq / timestamp / digest field',
  unexpected_key: 'Key not in the frozen schema (possible content leak)',
  long_string: 'Unusually long string value in a metadata record',
  duplicate_seq: 'Duplicate seq — second copy ignored',
  seq_gap: 'Gap in seq numbering',
  manifest_not_first: 'Manifest is not record 0',
  chain_link: 'Hash-chain link broken (prev ≠ previous digest)',
  evidence_forward_ref: 'Finding cites evidence from the future',
  evidence_missing: 'Finding cites a seq not present in this bundle',
  schema_minor_newer: 'Bundle schema is newer than this console — rendering known fields only',
  last_record: 'Bundle does not end with a receipt or report (run may be incomplete)',
  ts_mono_regress: 'Monotonic timestamp went backwards',
};

/** Fetch + parse a same-origin bundle (e.g. public/bundles/demo.jsonl). */
export async function fetchBundle(url: string): Promise<LoadedBundle> {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new BundleLoadError('unparseable', `Could not load ${url.slice(0, 80)} (HTTP ${res.status}).`);
  const text = await res.text();
  return parseBundle(text, url.split('/').pop() ?? url);
}

/** Read a user-picked / dropped File. Nothing leaves the browser. */
export async function readBundleFile(file: File): Promise<LoadedBundle> {
  const text = await file.text();
  return parseBundle(text, file.name);
}
