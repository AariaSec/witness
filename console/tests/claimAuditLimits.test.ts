import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { claimAudit } from '../src/lib/derive';

const load = (name: string) => parseBundle(readFileSync(resolve(__dirname, '../public/bundles', name), 'utf8'));

// A passive recorder's limits (short-lived shell commands, paths outside the workspace, reads) must never be counted
// as the agent contradicting itself.
describe('claim audit: recorder limits are not contradictions', () => {
  it('real Muse Code run: unmatched shell claims are unobservable, not contradicted', () => {
    const a = claimAudit(load('muse-real-agent-proof.jsonl'));
    expect(a.contradicted.value).toBe(0);
    expect(a.unobservable.value).toBeGreaterThan(0);
    const shell = a.rows.filter((r) => r.claim.tool === 'shell').flatMap((r) => r.items);
    expect(shell.every((i) => i.status !== 'not_observed')).toBe(true);
  });
  it('a claimed write outside the workspace is unobservable; a claimed in-workspace write that is recorded is corroborated', () => {
    const a = claimAudit(load('unprompted-readme-injection.jsonl'));
    const items = a.rows.flatMap((r) => r.items);
    const outside = items.find((i) => i.subject === '/private/tmp/fetch_token.py');
    expect(outside?.status).toBe('unobservable');
    expect(outside?.why).toBe('outside_workspace');
    expect(items.find((i) => i.subject === '.env')?.status).toBe('corroborated');
    expect(a.contradicted.value).toBe(0);
  });
  it('the scripted demo still shows its real count mismatch', () => {
    const a = claimAudit(load('demo.jsonl'));
    expect(a.contradicted.value).toBe(1);
  });
});
