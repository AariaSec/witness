/**
 * Integration check: does the console's receipt verification work against a
 * REAL Receipt v0.2 bundle — one where git_commit_sha is null (its default,
 * the common case since no lab directory is a real git repo) but
 * coverage/changed_file_digests/git_tree_digest are genuinely populated?
 *
 * Found 2026-10-27, not by inspection: BOTH flagship real-agent bundles
 * showed "RECEIPT INVALID" in the live, deployed full console (the share
 * view never hit this, since it doesn't render ReceiptPanel at all) despite
 * `witness verify` confirming `receipt_ok=True` for both. Root cause: the
 * backend strips an at-default v0.2 field before signing
 * (`ReceiptBody.canonical_payload()`, models.py) so pre-v0.2 bundles stay
 * byte-identical; the console's canonicalisation never mirrored that
 * stripping, so it included `git_commit_sha: null` (genuinely present in
 * the raw JSON) in its own canonical form — a byte-level divergence from
 * what was actually signed. Fixed in verifyReceipt.ts
 * (stripV02FromNode/stripV02FromPlain). This test is the regression guard:
 * if that stripping logic and the backend's ever diverge again, THIS test
 * fails against real data, not a synthetic fixture that can't catch it.
 *
 * Fixtures: byte-identical copies of
 * runs/frozen/muse-real-agent-proof-20261027-011548-7dca/bundle.jsonl and
 * runs/frozen/claude-real-agent-proof-20261027-012001-c976/bundle.jsonl in
 * the parent repo — both already leak-scanned clean there.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { auditReceipt } from '../src/lib/verifyReceipt';

const FIXTURES = [
  { name: 'Muse Code flagship (has a real mismatch finding)', file: 'muse-v02-bundle.jsonl' },
  { name: 'Claude Code flagship (second agent, generalization proof)', file: 'claude-v02-bundle.jsonl' },
];

describe('Receipt v0.2 real backend interop', () => {
  for (const { name, file } of FIXTURES) {
    it(`VERIFIES ${name}, including when git_commit_sha is null`, () => {
      const text = readFileSync(join(__dirname, 'fixtures', file), 'utf-8');
      const bundle = parseBundle(text, file);
      const errors = bundle.issues.filter((i) => i.level === 'error');
      expect(errors, JSON.stringify(errors, null, 2)).toHaveLength(0);

      const receipt = bundle.byKind.receipt[0];
      expect(receipt, 'fixture must contain a receipt record').toBeTruthy();
      expect(receipt!.body.git_commit_sha ?? null, 'fixture must exercise the null case this bug hid behind').toBeNull();
      expect(receipt!.body.coverage?.length ?? 0, 'fixture must have a genuinely non-default coverage').toBeGreaterThan(0);

      const audit = auditReceipt(bundle);
      expect(audit.verdict, JSON.stringify(audit, null, 2)).toBe('verified');
    });
  }
});
