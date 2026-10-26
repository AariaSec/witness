/**
 * verifyReceipt — proves the Ed25519 check is real, in isolation:
 *  1. the noble primitive is wired correctly (RFC 8032 §7.1 TEST 1 vector),
 *  2. a hand-constructed receipt signed here verifies, and every tamper fails,
 *  3. Python-style canonicalisation (float repr, lossless lexemes) is right,
 *  4. the committed demo fixture's REAL signature verifies, and fails if edited.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import * as ed from '@noble/ed25519';
import {
  auditReceipt,
  b64ToBytes,
  bytesToB64,
  canonicalJson,
  parseLossless,
  canonicalFromNode,
  pyFloatRepr,
  verifyReceipt,
} from '../src/lib/verifyReceipt';
import { parseBundle } from '../src/lib/loadBundle';
import type { Receipt, ReceiptBody } from '../src/schema/bundle';

const hex = (h: string) => Uint8Array.from(h.match(/../g)!.map((b) => parseInt(b, 16)));
const enc = (s: string) => new TextEncoder().encode(s);
const DIGEST = 'a'.repeat(64);
const POLICY = 'b'.repeat(64);

function makeReceipt(body: ReceiptBody, sig: string): Receipt {
  return { seq: 28, kind: 'receipt', ts_wall: 1, ts_mono: 1, prev: DIGEST, digest: DIGEST, body, sig };
}

describe('Ed25519 primitive (RFC 8032 §7.1 TEST 1)', () => {
  const pub = hex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a');
  const sig = hex(
    'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b',
  );
  it('accepts the published vector', () => {
    // importing verifyReceipt configured ed.hashes.sha512 for sync verify
    expect(ed.verify(sig, new Uint8Array(0), pub)).toBe(true);
  });
  it('rejects the vector with one flipped signature bit', () => {
    const bad = sig.slice();
    bad[0] = (bad[0] as number) ^ 1;
    expect(ed.verify(bad, new Uint8Array(0), pub)).toBe(false);
  });
});

describe('canonical JSON (Python canon.py semantics)', () => {
  it('matches the architecture doc known vector shape', () => {
    expect(canonicalJson({ b: 1, a: [1.5] })).toBe('{"a":[1.5],"b":1}');
  });
  it('renders floats like Python repr()', () => {
    expect(pyFloatRepr(1e-5)).toBe('1e-05');
    expect(pyFloatRepr(0.0001)).toBe('0.0001');
    expect(pyFloatRepr(1e16)).toBe('1e+16');
    expect(pyFloatRepr(123)).toBe('123.0');
    expect(pyFloatRepr(0.1)).toBe('0.1');
    expect(pyFloatRepr(1793023341.137)).toBe('1793023341.137');
    expect(pyFloatRepr(-2.5)).toBe('-2.5');
    expect(pyFloatRepr(1.5e300)).toBe('1.5e+300');
  });
  it('lossless parse keeps number lexemes and sorts keys', () => {
    const n = parseLossless('{"z": 1.0, "a": {"y": [1, 2.50], "b": "x\\u00e9"}}');
    expect(canonicalFromNode(n)).toBe('{"a":{"b":"xé","y":[1,2.50]},"z":1.0}');
  });
});

describe('verifyReceipt — hand-constructed receipt', () => {
  const { secretKey, publicKey } = ed.keygen();
  const pubB64 = bytesToB64(publicKey);
  const body: ReceiptBody = {
    run_id: '20261026-140211-test',
    final_digest: DIGEST,
    records: 28,
    findings: { outbound_post: 1, marker_read: 1 },
    stop_status: 'ok',
    policy_hash: POLICY,
    signed_at: 1793023341.25,
    pubkey: pubB64,
  };
  const sig = bytesToB64(ed.sign(enc(canonicalJson(body)), secretKey));
  const good = makeReceipt(body, sig);

  it('passes for the genuine body + signature', () => {
    const r = verifyReceipt(good, pubB64);
    expect(r.ok).toBe(true);
  });
  it('fails when any body field is changed', () => {
    for (const tampered of [
      { ...body, records: 29 },
      { ...body, stop_status: 'not_needed' as const },
      { ...body, findings: { outbound_post: 0, marker_read: 1 } },
      { ...body, final_digest: 'c'.repeat(64) },
      { ...body, signed_at: 1793023341.26 },
    ]) {
      const r = verifyReceipt(makeReceipt(tampered, sig), pubB64);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toBe('bad_signature');
    }
  });
  it('fails when the signature is altered', () => {
    const s = b64ToBytes(sig);
    s[10] = (s[10] as number) ^ 0x40;
    expect(verifyReceipt(makeReceipt(body, bytesToB64(s)), pubB64).ok).toBe(false);
  });
  it('fails against a different public key', () => {
    const other = bytesToB64(ed.getPublicKey(ed.utils.randomSecretKey()));
    expect(verifyReceipt(good, other).ok).toBe(false);
  });
  it('reports malformed key / signature encodings distinctly', () => {
    const a = verifyReceipt(good, 'not-a-key');
    expect(a.ok === false && a.reason).toBe('bad_pubkey');
    const b = verifyReceipt(makeReceipt(body, 'AAAA'), pubB64);
    expect(b.ok === false && b.reason).toBe('bad_sig_encoding');
  });
  it('verifies an integral float (Python "1.0") via the raw line, losslessly', () => {
    const pyText = canonicalJson({ ...body, signed_at: 1793023341 }, new Set(['signed_at']));
    expect(pyText).toContain('"signed_at":1793023341.0');
    const s2 = bytesToB64(ed.sign(enc(pyText), secretKey));
    const rec = makeReceipt({ ...body, signed_at: 1793023341 }, s2);
    const raw = `{"kind":"receipt","seq":28,"body":${pyText},"sig":"${s2}"}`;
    const withRaw = verifyReceipt(rec, pubB64, raw);
    expect(withRaw.ok && withRaw.encoding).toBe('lossless');
    // without the raw line the python-repr fallback for signed_at still finds it
    const noRaw = verifyReceipt(rec, pubB64);
    expect(noRaw.ok && noRaw.encoding).toBe('py_repr_float_ts');
  });
});

describe('demo fixture (public/bundles/demo.jsonl)', () => {
  const text = readFileSync(resolve(__dirname, '../public/bundles/demo.jsonl'), 'utf8');

  it('carries a REAL Ed25519 signature that verifies with all bindings', () => {
    const b = parseBundle(text, 'demo.jsonl');
    const a = auditReceipt(b);
    expect(a.sig?.ok).toBe(true);
    expect(a.checks.filter((c) => !c.ok).map((c) => c.id)).toEqual([]);
    expect(a.verdict).toBe('verified');
  });

  it('fails if one byte of the signed body is edited on disk', () => {
    const lines = text.trim().split('\n');
    const i = lines.findIndex((l) => l.includes('"kind":"receipt"'));
    lines[i] = lines[i]!.replace('"records":28', '"records":27');
    const a = auditReceipt(parseBundle(lines.join('\n')));
    expect(a.sig?.ok).toBe(false);
    expect(a.verdict).toBe('invalid');
  });
});
