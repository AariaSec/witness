/**
 * Integration check: does the console's receipt verification actually work
 * against a REAL receipt signed by the Python backend (not just a hand-
 * signed TS fixture)? Both halves were built by separate agents against a
 * shared spec — this is the test that proves they actually interoperate.
 *
 * Fixture: `tests/fixtures/real-backend-bundle.jsonl`, copied verbatim from
 * a real `witness demo --scenario exfil` recording
 * (runs/frozen/analyst-live-proof-20261026-145221-6150/bundle.jsonl in the
 * parent repo) — a genuine Ed25519-signed receipt from `witness/actions/receipt.py`.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { auditReceipt } from '../src/lib/verifyReceipt';

const FIXTURE_PATH = join(__dirname, 'fixtures', 'real-backend-bundle.jsonl');

describe('real backend bundle interop', () => {
  it('parses without schema errors', () => {
    const text = readFileSync(FIXTURE_PATH, 'utf-8');
    const bundle = parseBundle(text, 'real-backend-bundle.jsonl');
    const errors = bundle.issues.filter((i) => i.level === 'error');
    expect(errors, JSON.stringify(errors, null, 2)).toHaveLength(0);
    expect(bundle.manifest?.simulated).toBe(true);
    expect(bundle.manifest?.run_id).toBe('20261026-145221-6150');
  });

  it('finds the expected real findings (marker_read + outbound_post)', () => {
    const text = readFileSync(FIXTURE_PATH, 'utf-8');
    const bundle = parseBundle(text, 'real-backend-bundle.jsonl');
    const kinds = bundle.byKind.finding.map((f) => f.fkind).sort();
    expect(kinds).toEqual(['marker_read', 'outbound_post']);
  });

  it('VERIFIES a real Ed25519 receipt signed by the Python backend', () => {
    const text = readFileSync(FIXTURE_PATH, 'utf-8');
    const bundle = parseBundle(text, 'real-backend-bundle.jsonl');
    const audit = auditReceipt(bundle);

    // This is the one assertion that matters: if the backend's canon.py and
    // the console's canonicalJson() ever disagree on encoding, this fails
    // here — against real data — instead of silently passing two separate
    // unit-tested-in-isolation implementations that never actually talk.
    expect(audit.verdict, JSON.stringify(audit, null, 2)).toBe('verified');
  });

  it('tamper-detects: flipping one byte of the real signed body invalidates it', () => {
    const text = readFileSync(FIXTURE_PATH, 'utf-8');
    const lines = text.split('\n');
    const receiptLineIdx = lines.findIndex((l) => l.includes('"kind":"receipt"'));
    expect(receiptLineIdx).toBeGreaterThanOrEqual(0);

    // Tamper the RAW TEXT line (not a parsed-object copy) — auditReceipt
    // re-derives its canonical encoding from the raw line via rawLineBySeq,
    // so only a text-level edit exercises the real verification path.
    const tamperedLine = lines[receiptLineIdx]!.replace(
      /"records":(\d+)/,
      (_m, n: string) => `"records":${Number(n) + 1}`,
    );
    expect(tamperedLine).not.toBe(lines[receiptLineIdx]);
    lines[receiptLineIdx] = tamperedLine;

    const tamperedBundle = parseBundle(lines.join('\n'), 'real-backend-bundle-tampered.jsonl');
    const auditTampered = auditReceipt(tamperedBundle);
    expect(auditTampered.verdict, JSON.stringify(auditTampered, null, 2)).not.toBe('verified');
  });
});
