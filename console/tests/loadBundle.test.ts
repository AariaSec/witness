import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { BundleLoadError, parseBundle } from '../src/lib/loadBundle';
import { claimAudit, findingCounts, medianTimeToDetect, stopSummary, timeToDetect } from '../src/lib/derive';

const text = readFileSync(resolve(__dirname, '../public/bundles/demo.jsonl'), 'utf8');
const lines = () => text.trim().split('\n');

describe('loadBundle', () => {
  it('parses the demo bundle cleanly', () => {
    const b = parseBundle(text);
    expect(b.records).toHaveLength(30);
    expect(b.manifest.simulated).toBe(true);
    expect(b.schema.version).toBe('1.0');
    expect(b.chain).toMatchObject({ ok: true, links: 29, firstBadSeq: null });
    expect(b.issues).toEqual([]);
    expect(b.findings).toHaveLength(4);
    expect(b.receipt?.seq).toBe(28);
    expect(b.report?.seq).toBe(29);
  });
  it('rejects empty files and unsupported MAJOR schema', () => {
    expect(() => parseBundle('\n\n')).toThrow(BundleLoadError);
    const l = lines();
    l[0] = l[0]!.replace('"bundle_schema":"1.0"', '"bundle_schema":"2.0"');
    expect(() => parseBundle(l.join('\n'))).toThrow(/Unsupported bundle_schema/);
  });
  it('warns (but still loads) on a newer MINOR schema', () => {
    const l = lines();
    l[0] = l[0]!.replace('"bundle_schema":"1.0"', '"bundle_schema":"1.3"');
    const b = parseBundle(l.join('\n'));
    expect(b.schema.newerMinor).toBe(true);
    expect(b.issues.some((i) => i.code === 'schema_minor_newer')).toBe(true);
  });
  it('detects a broken hash-chain link and keeps replaying', () => {
    const l = lines();
    l[10] = l[10]!.replace(/"prev":"[0-9a-f]{64}"/, `"prev":"${'0'.repeat(64)}"`);
    const b = parseBundle(l.join('\n'));
    expect(b.chain.ok).toBe(false);
    expect(b.chain.firstBadSeq).toBe(10);
    expect(b.records).toHaveLength(30);
  });
  it('flags keys outside the frozen schema as a possible content leak', () => {
    const l = lines();
    l[3] = l[3]!.replace('{', '{"prompt":"x",');
    const b = parseBundle(l.join('\n'));
    expect(b.issues.some((i) => i.code === 'unexpected_key' && i.key === 'prompt')).toBe(true);
  });
  it('accepts peer_escaped on marker_read/outbound_post without warning, but never requires it', () => {
    // peer_escaped landed on MarkerRead/OutboundPost after every committed
    // frozen/demo bundle was written (found while auditing the repo with a
    // real large-context agent session, not by inspection): every bundle
    // generated since must not warn on it, and every bundle generated before
    // must keep parsing clean without it (demo.jsonl already covers the
    // latter — this covers the former plus the exact regression: it used to
    // fire 'unexpected_key' on a legitimate, always-present field).
    const l = lines();
    l[14] = l[14]!.replace('"path":"/v1/token"', '"path":"/v1/token","peer_escaped":true');
    const b = parseBundle(l.join('\n'));
    expect(b.issues.some((i) => i.code === 'unexpected_key' && i.key === 'peer_escaped')).toBe(false);
    const rec = b.records.find((r) => r.seq === 14);
    expect(rec).toMatchObject({ kind: 'marker_read', peer_escaped: true });
  });
  it('orders by seq even when lines are shuffled', () => {
    const l = lines();
    const b = parseBundle([...l].reverse().join('\n'));
    expect(b.records.map((r) => r.seq)).toEqual([...Array(30).keys()]);
  });
});

describe('derive — every number carries seqs', () => {
  const b = parseBundle(text);
  it('counts findings by severity', () => {
    const fc = findingCounts(b);
    expect(fc.total.value).toBe(4);
    expect(fc.total.seqs).toEqual([15, 20, 25, 26]);
    expect(fc.bySeverity.stop).toMatchObject({ value: 1, seqs: [20] });
    expect(fc.bySeverity.warn.value).toBe(2);
    expect(fc.bySeverity.info.value).toBe(1);
  });
  it('computes time-to-detect from the earliest evidence (ts_mono)', () => {
    const f = b.findings.find((x) => x.fkind === 'outbound_post')!;
    const t = timeToDetect(b, f);
    expect(t.value).toBeCloseTo(5, 6);
    expect(t.seqs).toEqual([19, 20]);
    expect(medianTimeToDetect(b).value).toBeCloseTo(7, 6);
  });
  it('summarises the stop action', () => {
    const s = stopSummary(b);
    expect(s.status).toBe('ok');
    expect(s.latency).toMatchObject({ value: 38, seqs: [21] });
    expect(s.evidenceToStop.value).toBeCloseTo(44, 6);
  });
  it('diffs reported vs recorded', () => {
    const a = claimAudit(b);
    expect(a.verdict).toBe('mismatch');
    expect(a.corroborated.value).toBe(4);
    expect(a.contradicted.value).toBe(1); // claimed 1 file, recorded 2
    expect(a.unclaimed.map((u) => u.record.seq)).toEqual([9, 14, 18, 19]);
    expect(a.unobservable.value).toBe(2);
    expect(a.agreement.value).toBeCloseTo(4 / 9, 9);
    expect(a.agreement.seqs.length).toBeGreaterThan(0);
  });
  it('respects the replay cursor', () => {
    expect(findingCounts(b, 13).total.value).toBe(0);
    expect(claimAudit(b, 7).unclaimed).toHaveLength(0);
    expect(stopSummary(b, 20).status).toBe('pending');
  });
});
