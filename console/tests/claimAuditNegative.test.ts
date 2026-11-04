import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { claimAudit } from '../src/lib/derive';
import type { LoadedBundle } from '../src/lib/loadBundle';

const load = (name: string) => parseBundle(readFileSync(resolve(__dirname, '../public/bundles', name), 'utf8'));
// shallow clone with extra records appended (the chain is not re-hashed: claimAudit only reads records)
const withRecords = (b: LoadedBundle, extra: unknown[]): LoadedBundle => {
  const records = [...b.records, ...(extra as LoadedBundle['records'])];
  return { ...b, records, bySeq: new Map(records.map((r) => [r.seq, r])) } as LoadedBundle;
};

// The point of these tests: loosening the audit for recorder limits must not make REAL contradictions or unmentioned
// activity undetectable.
describe('claim audit: real contradictions and unmentioned activity still fire', () => {
  const muse = load('muse-real-agent-proof.jsonl');
  it('an unmentioned process spawn is still reported as never mentioned', () => {
    const base = claimAudit(muse).unclaimedCount.value;
    const maxSeq = Math.max(...muse.records.map((r) => r.seq));
    const spawn = { seq: maxSeq + 1, kind: 'proc_event', op: 'spawn', pid: 99999, ppid: 1, exe: 'nc', ts_wall: 0, ts_mono: 60.0 };
    expect(claimAudit(withRecords(muse, [spawn])).unclaimedCount.value).toBe(base + 1);
  });
  it('a claimed in-workspace write with no recorded file event is still contradicted', () => {
    const maxSeq = Math.max(...muse.records.map((r) => r.seq));
    const claim = { seq: maxSeq + 1, kind: 'assistant_claim', source: 'session_log', tool: 'write', claimed_paths: ['src/never_written.py'], claimed_hosts: [], claimed_count: null, line_digest: '0'.repeat(64), ts_wall: 0, ts_mono: 6.0 };
    const a = claimAudit(withRecords(muse, [claim]));
    expect(a.contradicted.value).toBe(1);
    expect(a.verdict).toBe('mismatch');
  });
  it('a claimed loopback fetch the recorder did not see is still contradicted (external hosts are not)', () => {
    const maxSeq = Math.max(...muse.records.map((r) => r.seq));
    const mk = (n: number, host: string) => ({ seq: maxSeq + n, kind: 'assistant_claim', source: 'session_log', tool: 'http', claimed_paths: [], claimed_hosts: [host], claimed_count: null, line_digest: '0'.repeat(64), ts_wall: 0, ts_mono: 7.0 });
    const loop = claimAudit(withRecords(muse, [mk(1, '127.0.0.1:59999')]));
    expect(loop.contradicted.value).toBe(1);
    const ext = claimAudit(withRecords(muse, [mk(1, 'example.com')]));
    expect(ext.contradicted.value).toBe(0);
  });
  it('the green demo bundle audit is unchanged by the recorder-limit rules', () => {
    // pinned so a future change to the audit rules is a visible, deliberate decision
    expect(claimAudit(load('demo-green.jsonl')).contradicted.value).toBe(2);
  });
});
