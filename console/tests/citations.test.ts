import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { auditReadout, checkCites, type Sidecar } from '../src/lib/citations';

const dir = resolve(__dirname, '../public/bundles');
const load = (name: string) => parseBundle(readFileSync(resolve(dir, name), 'utf8'), name);

describe('citation checker', () => {
  const b = load('muse-real-agent-proof.jsonl');
  it('a cite to a record that does not exist is rejected', () => {
    const [c] = checkCites('MARKER_READ', [9999], b.bySeq);
    expect(c!.exists).toBe(false);
    expect(c!.fits).toBe(false);
  });
  it('a cite to a record of the wrong kind exists but does not fit', () => {
    // seq 12 is the marker_read; a FS_CREATE_MODIFY step cannot rest on it
    const [c] = checkCites('FS_CREATE_MODIFY', [12], b.bySeq);
    expect(c!.exists).toBe(true);
    expect(c!.fits).toBe(false);
  });
  it('a cite to a record of the right kind holds', () => {
    const [c] = checkCites('MARKER_READ', [12], b.bySeq);
    expect(c).toMatchObject({ exists: true, fits: true, kind: 'marker_read' });
  });
  it('an unknown code supports nothing', () => {
    expect(checkCites('NOT_A_CODE', [12], b.bySeq)[0]!.fits).toBe(false);
  });
  it('a fabricated report is audited as failing, not trusted', () => {
    const a = auditReadout(
      { model_id: 'x', analyst_status: 'ok', confidence: 1, summary_codes: [], reported_vs_recorded: [],
        timeline: [{ seq_refs: [12, 8000], code: 'MARKER_READ', severity: 'warn' }, { seq_refs: [12], code: 'PROC_SPAWN', severity: 'info' }] },
      b.bySeq,
    );
    expect(a.total).toBe(3);
    expect(a.exist).toBe(2);
    expect(a.fit).toBe(1);
  });
});

// The browser's counts must equal the Python scorer's counts (meta_bench.score) stored with each real read-out.
describe('browser checker agrees with the Python scorer on stored real read-outs', () => {
  for (const name of ['unprompted-readme-injection', 'muse-real-agent-proof']) {
    const file = resolve(dir, `${name}.explain.json`);
    it.skipIf(!existsSync(file))(`${name}`, () => {
      const side = JSON.parse(readFileSync(file, 'utf8')) as Sidecar;
      const bundle = load(`${name}.jsonl`);
      expect(side.readouts.length).toBeGreaterThan(0);
      for (const r of side.readouts) {
        const a = auditReadout(r.report, bundle.bySeq);
        expect({ cites: a.total, exist: a.exist, fit: a.fit }).toEqual(r.python_check);
      }
    });
  }
});
