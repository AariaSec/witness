/**
 * verifyReceipt — real, client-side Ed25519 verification of a witness receipt.
 *
 * The recorder signs canonical JSON of the receipt `body`
 * (14_fable_architecture_phases.md §3.3 canon.py: sorted keys, no spaces,
 * UTF-8, floats via Python repr()). JavaScript's JSON.parse loses number
 * lexemes (`1.0` → `1`), so when the raw bundle line is available we parse it
 * with a small lossless parser and re-emit each number exactly as written.
 * If that does not verify we try Python-repr re-encodings of the parsed
 * values. Every candidate encodes the SAME values, so trying them does not
 * weaken the check: a forged or edited body still fails.
 *
 * Uses @noble/ed25519 with @noble/hashes' sha512 so verification is
 * synchronous and works without WebCrypto (e.g. on non-secure origins).
 */
import * as ed from '@noble/ed25519';
import { sha512 } from '@noble/hashes/sha2.js';
import type { Receipt, ReceiptBody } from '../schema/bundle';
import type { LoadedBundle } from './loadBundle';

ed.hashes.sha512 = sha512;

/* ------------------------------------------------------------------ base64 */

export function b64ToBytes(b64: string): Uint8Array {
  const clean = b64.trim().replace(/-/g, '+').replace(/_/g, '/');
  const padded = clean + '='.repeat((4 - (clean.length % 4)) % 4);
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(padded)) throw new Error('invalid base64');
  const bin = atob(padded);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function bytesToB64(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/* --------------------------------------------------------- canonical JSON */

/** Lossless JSON AST: numbers keep their source lexeme. */
export type JNode =
  | { t: 'obj'; entries: [string, JNode][] }
  | { t: 'arr'; items: JNode[] }
  | { t: 'str'; v: string }
  | { t: 'num'; raw: string }
  | { t: 'lit'; raw: 'true' | 'false' | 'null' };

/** Minimal lossless JSON parser (RFC 8259). Throws on malformed input. */
export function parseLossless(text: string): JNode {
  let i = 0;
  const ws = () => {
    while (i < text.length && ' \t\n\r'.includes(text[i] as string)) i++;
  };
  const fail = (): never => {
    throw new Error(`lossless JSON parse error at ${i}`);
  };
  const str = (): string => {
    // Delegate escape handling to JSON.parse on the exact string token.
    const start = i;
    i++;
    while (i < text.length) {
      const ch = text[i];
      if (ch === '\\') i += 2;
      else if (ch === '"') {
        i++;
        return JSON.parse(text.slice(start, i)) as string;
      } else i++;
    }
    return fail();
  };
  const value = (): JNode => {
    ws();
    const c = text[i];
    if (c === '{') {
      i++;
      const entries: [string, JNode][] = [];
      ws();
      if (text[i] === '}') {
        i++;
        return { t: 'obj', entries };
      }
      for (;;) {
        ws();
        if (text[i] !== '"') fail();
        const k = str();
        ws();
        if (text[i] !== ':') fail();
        i++;
        entries.push([k, value()]);
        ws();
        if (text[i] === ',') {
          i++;
          continue;
        }
        if (text[i] === '}') {
          i++;
          return { t: 'obj', entries };
        }
        fail();
      }
    }
    if (c === '[') {
      i++;
      const items: JNode[] = [];
      ws();
      if (text[i] === ']') {
        i++;
        return { t: 'arr', items };
      }
      for (;;) {
        items.push(value());
        ws();
        if (text[i] === ',') {
          i++;
          continue;
        }
        if (text[i] === ']') {
          i++;
          return { t: 'arr', items };
        }
        fail();
      }
    }
    if (c === '"') return { t: 'str', v: str() };
    for (const lit of ['true', 'false', 'null'] as const) {
      if (text.startsWith(lit, i)) {
        i += lit.length;
        return { t: 'lit', raw: lit };
      }
    }
    const m = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(i));
    if (!m) return fail();
    i += m[0].length;
    return { t: 'num', raw: m[0] };
  };
  const v = value();
  ws();
  if (i !== text.length) fail();
  return v;
}

/** Python json.dumps(ensure_ascii=False) string escaping matches JSON.stringify for strings. */
const encStr = (s: string) => JSON.stringify(s);

/** Python float repr() for a finite JS number (shortest round-trip digits). */
export function pyFloatRepr(n: number): string {
  if (!Number.isFinite(n)) throw new Error('non-finite float');
  if (Object.is(n, -0)) return '-0.0';
  const [mant, expS] = n.toExponential().split('e') as [string, string];
  const exp = Number(expS);
  const neg = mant.startsWith('-');
  const digits = mant.replace('-', '').replace('.', '');
  let out: string;
  if (exp >= -4 && exp < 16) {
    if (exp >= 0) {
      const intPart = digits.length > exp + 1 ? digits.slice(0, exp + 1) : digits.padEnd(exp + 1, '0');
      const frac = digits.length > exp + 1 ? digits.slice(exp + 1) : '0';
      out = `${intPart}.${frac}`;
    } else {
      out = `0.${'0'.repeat(-exp - 1)}${digits}`;
    }
  } else {
    const m = digits.length > 1 ? `${digits[0]}.${digits.slice(1)}` : digits;
    out = `${m}e${exp < 0 ? '-' : '+'}${String(Math.abs(exp)).padStart(2, '0')}`;
  }
  return neg ? `-${out}` : out;
}

/** Canonical text from a lossless AST (numbers verbatim, keys sorted, no spaces). */
export function canonicalFromNode(n: JNode): string {
  switch (n.t) {
    case 'obj': {
      const sorted = [...n.entries].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
      return `{${sorted.map(([k, v]) => `${encStr(k)}:${canonicalFromNode(v)}`).join(',')}}`;
    }
    case 'arr':
      return `[${n.items.map(canonicalFromNode).join(',')}]`;
    case 'str':
      return encStr(n.v);
    case 'num':
    case 'lit':
      return n.raw;
  }
}

/**
 * Canonical JSON of plain JS values, Python-style.
 * `floatKeys` names keys whose integral values must still render as floats
 * (Python `1.0`), since JS cannot tell 1 from 1.0 after parsing.
 */
export function canonicalJson(v: unknown, floatKeys: ReadonlySet<string> = new Set(), key?: string): string {
  if (v === null) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') {
    if (Number.isInteger(v) && !(key !== undefined && floatKeys.has(key))) return String(v);
    return pyFloatRepr(v);
  }
  if (typeof v === 'string') return encStr(v);
  if (Array.isArray(v)) return `[${v.map((x) => canonicalJson(x, floatKeys)).join(',')}]`;
  if (typeof v === 'object') {
    const keys = Object.keys(v as object).sort();
    return `{${keys
      .map((k) => `${encStr(k)}:${canonicalJson((v as Record<string, unknown>)[k], floatKeys, k)}`)
      .join(',')}}`;
  }
  throw new Error(`cannot canonicalise ${typeof v}`);
}

/**
 * Receipt v0.2 added four OPTIONAL fields to `ReceiptBody`
 * (`witness/models.py`). A receipt that genuinely sets one keeps it in the
 * signed payload; one that's still at its just-added default does NOT —
 * `ReceiptBody.canonical_payload()` strips it before signing, so a v0.1-era
 * receipt's bytes stay byte-identical. This MUST mirror that exact stripping
 * here, or the console's own canonicalisation diverges from what was
 * actually signed the moment a real receipt has `git_commit_sha: null`
 * (the common case — none of the lab directories so far are real git repos)
 * even though `coverage`/`changed_file_digests`/`git_tree_digest` are
 * genuinely populated. Caught 2026-10-27: this exact gap made BOTH
 * flagship real-agent bundles show "RECEIPT INVALID" in the full console
 * (the share view never hit this, since it doesn't render ReceiptPanel at
 * all) despite `witness verify` confirming `receipt_ok=True` for both.
 */
const RECEIPT_BODY_V02_DEFAULTS: Record<string, 'null' | 'empty_obj' | 'empty_arr'> = {
  git_commit_sha: 'null',
  git_tree_digest: 'null',
  changed_file_digests: 'empty_obj',
  coverage: 'empty_arr',
};

/** Strip a v0.2 field from a lossless `obj` node's entries when its value
 * matches the field's just-added default exactly — mirrors
 * `strip_receipt_body_v02_defaults` (models.py) at the byte level. */
function stripV02FromNode(node: JNode): JNode {
  if (node.t !== 'obj') return node;
  const kept = node.entries.filter(([k, v]) => {
    const kind = RECEIPT_BODY_V02_DEFAULTS[k];
    if (!kind) return true;
    if (kind === 'null') return !(v.t === 'lit' && v.raw === 'null');
    if (kind === 'empty_obj') return !(v.t === 'obj' && v.entries.length === 0);
    if (kind === 'empty_arr') return !(v.t === 'arr' && v.items.length === 0);
    return true;
  });
  return { t: 'obj', entries: kept };
}

/** Same stripping, for a plain parsed JS object (the py_repr candidates). */
function stripV02FromPlain(body: ReceiptBody): ReceiptBody {
  const out = { ...(body as unknown as Record<string, unknown>) };
  for (const [k, kind] of Object.entries(RECEIPT_BODY_V02_DEFAULTS)) {
    const v = out[k];
    const isDefault =
      (kind === 'null' && v === null) ||
      (kind === 'empty_obj' && v !== null && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length === 0) ||
      (kind === 'empty_arr' && Array.isArray(v) && v.length === 0);
    if (isDefault) delete out[k];
  }
  return out as unknown as ReceiptBody;
}

/** Extract the `body` sub-tree of a raw receipt line, losslessly. */
function bodyNodeFromRaw(rawLine: string): JNode | null {
  try {
    const root = parseLossless(rawLine);
    if (root.t !== 'obj') return null;
    const node = root.entries.find(([k]) => k === 'body')?.[1] ?? null;
    return node ? stripV02FromNode(node) : null;
  } catch {
    return null;
  }
}

export type CanonEncoding = 'lossless' | 'py_repr' | 'py_repr_float_ts';

export interface CanonCandidate {
  encoding: CanonEncoding;
  text: string;
}

/** Candidate canonical encodings of the body, most faithful first (deduplicated). */
export function canonicalCandidates(body: ReceiptBody, rawLine?: string | null): CanonCandidate[] {
  const out: CanonCandidate[] = [];
  const push = (encoding: CanonEncoding, text: string) => {
    if (!out.some((c) => c.text === text)) out.push({ encoding, text });
  };
  if (rawLine) {
    const node = bodyNodeFromRaw(rawLine);
    if (node) push('lossless', canonicalFromNode(node));
  }
  const strippedBody = stripV02FromPlain(body);
  push('py_repr', canonicalJson(strippedBody));
  // Only reached when the 'lossless' candidate above was skipped (no raw
  // line) — this fallback can't tell 1 from 1.0 on its own, so it needs an
  // explicit list of ReceiptBody's float fields. Keep this set in sync with
  // Python's ReceiptBody: guarded by
  // tests/unit/test_models.py::test_receipt_body_float_fields_match_console_float_keys_allowlist,
  // which fails loudly if a new float field is added there without this
  // set being updated too.
  push('py_repr_float_ts', canonicalJson(strippedBody, new Set(['signed_at'])));
  return out;
}

/* --------------------------------------------------------- verification */

export type SigFailReason = 'bad_signature' | 'bad_pubkey' | 'bad_sig_encoding' | 'malformed_body';

export type SigResult =
  | { ok: true; encoding: CanonEncoding; message: string; ms: number }
  | { ok: false; reason: SigFailReason; ms: number; tried: number };

/**
 * Verify `receipt.sig` over canonical JSON of `receipt.body` with the given
 * base64 Ed25519 public key (normally the manifest's `pubkey`).
 */
export function verifyReceipt(receipt: Receipt, pubkeyB64: string, rawLine?: string | null): SigResult {
  const t0 = performance.now();
  const ms = () => Math.round((performance.now() - t0) * 100) / 100;
  let pub: Uint8Array;
  let sig: Uint8Array;
  try {
    pub = b64ToBytes(pubkeyB64);
    if (pub.length !== 32) throw new Error('len');
  } catch {
    return { ok: false, reason: 'bad_pubkey', ms: ms(), tried: 0 };
  }
  try {
    sig = b64ToBytes(receipt.sig);
    if (sig.length !== 64) throw new Error('len');
  } catch {
    return { ok: false, reason: 'bad_sig_encoding', ms: ms(), tried: 0 };
  }
  let candidates: CanonCandidate[];
  try {
    candidates = canonicalCandidates(receipt.body, rawLine);
  } catch {
    return { ok: false, reason: 'malformed_body', ms: ms(), tried: 0 };
  }
  const enc = new TextEncoder();
  for (const c of candidates) {
    let valid = false;
    try {
      valid = ed.verify(sig, enc.encode(c.text), pub);
    } catch {
      return { ok: false, reason: 'bad_pubkey', ms: ms(), tried: candidates.length };
    }
    if (valid) return { ok: true, encoding: c.encoding, message: c.text, ms: ms() };
  }
  return { ok: false, reason: 'bad_signature', ms: ms(), tried: candidates.length };
}

/* ------------------------------------------------------- full receipt audit */

export type CheckId =
  | 'signature'
  | 'pubkey_match'
  | 'run_id'
  | 'final_digest'
  | 'record_count'
  | 'finding_counts'
  | 'stop_status'
  | 'chain';

export interface ReceiptCheck {
  id: CheckId;
  ok: boolean;
  /** fixed console-authored label */
  label: string;
  /** short console-authored detail; may include counts/seqs, never bundle prose */
  detail: string;
  /** seqs this check reads */
  seqs: number[];
  /** signature is the only check whose failure makes the receipt INVALID */
  critical: boolean;
}

export type ReceiptVerdict = 'verified' | 'signature_only' | 'invalid' | 'absent';

export interface ReceiptAudit {
  verdict: ReceiptVerdict;
  sig: SigResult | null;
  checks: ReceiptCheck[];
  receiptSeq: number | null;
}

const SIG_FAIL_TEXT: Record<SigFailReason, string> = {
  bad_signature: 'does not verify against the manifest public key',
  bad_pubkey: 'manifest public key is not a 32-byte Ed25519 key',
  bad_sig_encoding: 'signature is not 64 bytes of base64',
  malformed_body: 'receipt body could not be canonicalised',
};

/** Signature check plus every binding check between the receipt and the bundle. */
export function auditReceipt(b: LoadedBundle): ReceiptAudit {
  const r = b.receipt;
  if (!r) return { verdict: 'absent', sig: null, checks: [], receiptSeq: null };
  const m = b.manifest;
  const body = r.body;
  const sig = verifyReceipt(r, m.pubkey, b.rawLineBySeq.get(r.seq));
  const checks: ReceiptCheck[] = [];

  checks.push({
    id: 'signature',
    ok: sig.ok,
    critical: true,
    label: 'Ed25519 signature',
    detail: sig.ok
      ? `valid over canonical body (${sig.encoding === 'lossless' ? 'bytes as recorded' : 'python-repr re-encoding'}) · ${sig.ms} ms`
      : SIG_FAIL_TEXT[sig.reason],
    seqs: [m.seq, r.seq],
  });

  checks.push({
    id: 'pubkey_match',
    ok: body.pubkey === m.pubkey,
    critical: false,
    label: 'Signing key = manifest key',
    detail: body.pubkey === m.pubkey ? 'receipt names the key pinned at seq 0' : 'receipt names a different key than the manifest',
    seqs: [m.seq, r.seq],
  });

  checks.push({
    id: 'run_id',
    ok: body.run_id === m.run_id,
    critical: false,
    label: 'Run id matches manifest',
    detail: body.run_id === m.run_id ? 'receipt and manifest name the same run' : 'receipt run_id differs from manifest',
    seqs: [m.seq, r.seq],
  });

  const bound = b.records.find((x) => x.digest === body.final_digest && x.seq < r.seq) ?? null;
  checks.push({
    id: 'final_digest',
    ok: bound !== null,
    critical: false,
    label: 'Final digest binds to chain',
    detail: bound ? `= digest of seq ${bound.seq} (${bound.kind})` : 'final_digest matches no record before the receipt',
    seqs: bound ? [bound.seq, r.seq] : [r.seq],
  });

  const expectedRecords = bound ? bound.seq + 1 : r.seq;
  checks.push({
    id: 'record_count',
    ok: body.records === expectedRecords,
    critical: false,
    label: 'Signed record count',
    detail: `receipt says ${body.records}, chain up to the bound digest has ${expectedRecords}`,
    seqs: bound ? [bound.seq, r.seq] : [r.seq],
  });

  const actual: Record<string, number> = {};
  const signedFindings = b.findings.filter((f) => f.seq < r.seq);
  for (const f of signedFindings) actual[f.fkind] = (actual[f.fkind] ?? 0) + 1;
  const keys = new Set([...Object.keys(actual), ...Object.keys(body.findings)]);
  const countsOk = [...keys].every((k) => (actual[k] ?? 0) === (body.findings[k] ?? 0));
  checks.push({
    id: 'finding_counts',
    ok: countsOk,
    critical: false,
    label: 'Finding tally',
    detail: countsOk
      ? `${signedFindings.length} finding record${signedFindings.length === 1 ? '' : 's'} match the signed tally`
      : 'signed tally differs from the finding records in this bundle',
    seqs: [...signedFindings.map((f) => f.seq), r.seq],
  });

  const stops = b.byKind.action_result.filter((a) => a.action === 'stop_pgroup' && a.seq < r.seq);
  const derived = stops.length === 0 ? 'not_needed' : stops.some((a) => !a.ok) ? 'failed' : 'ok';
  checks.push({
    id: 'stop_status',
    ok: derived === body.stop_status,
    critical: false,
    label: 'Stop status',
    detail: `signed "${body.stop_status}" · stop actions imply "${derived}"`,
    seqs: [...stops.map((a) => a.seq), r.seq],
  });

  checks.push({
    id: 'chain',
    ok: b.chain.ok,
    critical: false,
    label: 'Hash-chain links',
    detail: b.chain.ok ? `${b.chain.links} prev→digest links intact` : `link broken at seq ${b.chain.firstBadSeq}`,
    seqs: b.chain.firstBadSeq !== null ? [b.chain.firstBadSeq] : [0, r.seq],
  });

  const verdict: ReceiptVerdict = !sig.ok ? 'invalid' : checks.every((c) => c.ok) ? 'verified' : 'signature_only';
  return { verdict, sig, checks, receiptSeq: r.seq };
}
