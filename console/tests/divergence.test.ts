import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { divergence, findingWeight } from '../src/lib/divergence';

const load = (name: string) => parseBundle(readFileSync(resolve(__dirname, `../public/bundles/${name}`), 'utf8'), name);

describe('divergence (Agent said vs reality recorded)', () => {
  for (const name of ['credential-persist-real-proof.jsonl', 'muse-real-agent-proof.jsonl', 'demo.jsonl']) {
    it(`${name}: every step is a real record, in seq order`, () => {
      const b = load(name);
      const d = divergence(b);
      expect(d.steps.length).toBeGreaterThan(0);
      for (const s of d.steps) expect(b.bySeq.get(s.seq)).toBe(s.record);
      const seqs = d.steps.map((s) => s.seq);
      expect(seqs).toEqual([...seqs].sort((x, y) => x - y));
    });
  }

  it('paths are in step until the first finding, then split at that exact seq', () => {
    const b = load('credential-persist-real-proof.jsonl');
    const d = divergence(b);
    const first = b.findings.find((f) => findingWeight(f) > 0)!;
    expect(d.splitAt?.seq).toBe(first.seq);
    for (const s of d.steps) expect(s.weight > 0).toBe(s.seq >= first.seq);
    // warn marker_read (1) + two stop credential_persist (2 + 2)
    expect(d.weight.value).toBe(5);
    expect(d.weight.seqs).toEqual(b.findings.map((f) => f.seq));
  });

  it('as of a cursor before any finding, nothing has split', () => {
    const b = load('credential-persist-real-proof.jsonl');
    const d = divergence(b, 8);
    expect(d.splitAt).toBeNull();
    expect(d.weight.value).toBe(0);
    expect(d.steps.every((s) => s.weight === 0)).toBe(true);
  });
});
