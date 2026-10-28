import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { parseBundle } from '../src/lib/loadBundle';
import { blastRadius, isSceneRecord, loudestCitation, playheadX } from '../src/lib/blastRadius';

const dir = resolve(__dirname, '../public/bundles');
const load = (name: string) => parseBundle(readFileSync(resolve(dir, name), 'utf8'), name);
const ALL = readdirSync(dir).filter((f) => f.endsWith('.jsonl'));

describe('blastRadius view model (3D scene)', () => {
  it('runs against every committed bundle', () => {
    expect(ALL.length).toBeGreaterThan(0);
  });

  for (const name of ALL) {
    describe(name, () => {
      const b = load(name);
      const m = blastRadius(b);

      it('every node is a real record, once, in seq order, ranked along the time axis', () => {
        for (const n of m.nodes) expect(b.bySeq.get(n.seq)).toBe(n.record);
        const seqs = m.nodes.map((n) => n.seq);
        expect(new Set(seqs).size).toBe(seqs.length);
        expect(seqs).toEqual([...seqs].sort((x, y) => x - y));
        expect(m.nodes.map((n) => n.rank)).toEqual(m.nodes.map((_, i) => i));
        for (const n of m.nodes) expect(n.pos[0]).toBeCloseTo(m.xOfRank(n.rank));
        // and every scene-eligible record is drawn
        expect(seqs).toEqual(b.records.filter(isSceneRecord).map((r) => r.seq));
      });

      it('process lifelines and spawn edges match real proc_event pid / ppid pairs', () => {
        const procs = b.records.filter((r) => r.kind === 'proc_event');
        expect([...m.processes.keys()].sort()).toEqual([...new Set(procs.map((r) => (r.kind === 'proc_event' ? r.pid : -1)))].sort());
        for (const e of m.spawnEdges) {
          const r = b.bySeq.get(e.seq);
          expect(r?.kind).toBe('proc_event');
          if (r?.kind !== 'proc_event') continue;
          expect(r.pid).toBe(e.pid);
          expect(r.ppid).toBe(e.parentPid);
          // both ends are recorded processes
          expect(m.processes.has(e.parentPid)).toBe(true);
          expect(m.processes.has(e.pid)).toBe(true);
        }
        // every recorded (ppid → pid) pair whose parent is also recorded IS an edge
        const want = new Set<string>();
        for (const r of procs) if (r.kind === 'proc_event' && r.ppid !== null && r.ppid !== r.pid && m.processes.has(r.ppid)) want.add(`${r.ppid}>${r.pid}`);
        expect(new Set(m.spawnEdges.map((e) => `${e.parentPid}>${e.pid}`))).toEqual(want);
        // proc nodes sit on their own pid's lifeline
        for (const n of m.nodes) {
          if (n.record.kind !== 'proc_event') continue;
          const p = m.processes.get(n.record.pid)!;
          expect(n.pid).toBe(n.record.pid);
          expect([n.pos[1], n.pos[2]]).toEqual([p.yz[0], p.yz[1]]);
        }
      });

      it('network satellites attach only to their real peer_pid; fs events never get a pid', () => {
        for (const n of m.nodes) {
          const r = n.record;
          if (r.kind === 'marker_read' || r.kind === 'outbound_post') {
            expect(n.pid).toBe(r.peer_pid !== null && m.processes.has(r.peer_pid) ? r.peer_pid : null);
          }
          if (r.kind === 'fs_event' || r.kind === 'finding' || r.kind === 'action_result') expect(n.pid).toBeNull();
        }
        for (const e of m.peerEdges) {
          const r = b.bySeq.get(e.seq);
          expect(r && (r.kind === 'marker_read' || r.kind === 'outbound_post') ? r.peer_pid : undefined).toBe(e.pid);
        }
      });

      it('finding highlights are exactly the real evidence_seqs', () => {
        for (const n of m.nodes) {
          const want = b.findings
            .filter((f) => f.evidence_seqs.includes(n.seq))
            .map((f) => ({ findingSeq: f.seq, severity: f.severity, fkind: f.fkind }));
          expect(n.citedBy).toEqual(want);
        }
        // every evidence seq is either highlighted in-scene or accounted for as off-scene
        for (const f of b.findings) {
          for (const s of new Set(f.evidence_seqs)) {
            if (!b.bySeq.has(s)) continue;
            const inScene = m.evidenceEdges.some((e) => e.findingSeq === f.seq && e.seq === s);
            const off = m.offSceneEvidence.some((e) => e.findingSeq === f.seq && e.seq === s);
            expect(inScene !== off).toBe(true);
            expect(inScene).toBe(m.bySeq.has(s));
          }
        }
      });

      it('one blast per close_marker / stop_pgroup action, carrying its real fields', () => {
        const actions = b.records.filter((r) => r.kind === 'action_result' && r.action !== 'sign_receipt');
        expect(m.blasts.map((x) => x.seq)).toEqual(actions.map((r) => r.seq));
        for (const x of m.blasts) {
          const r = b.bySeq.get(x.seq);
          expect(r).toBe(x.record);
          expect(x.latencyMs).toBe(x.record.latency_ms);
          expect(x.findingSeq).toBe(x.record.finding_seq);
          const f = b.bySeq.get(x.findingSeq);
          expect(x.severity).toBe(f?.kind === 'finding' ? f.severity : null);
          expect(x.effective).toBe(x.record.ok && x.record.detail !== 'noop' && x.record.detail !== 'already_closed');
          for (const pid of x.reachedPids) expect(m.processes.has(pid)).toBe(true);
          if (x.record.action !== 'stop_pgroup') expect(x.reachedPids).toEqual([]);
        }
      });
    });
  }

  it('demo-red: the stop_pgroup blast is the real seq-10 action (3 ms, term) and reaches the python3.11 group', () => {
    const b = load('demo-red.jsonl');
    const m = blastRadius(b);
    const stops = m.blasts.filter((x) => x.record.action === 'stop_pgroup');
    expect(stops).toHaveLength(1);
    const s = stops[0]!;
    expect(s.seq).toBe(10);
    expect(s.findingSeq).toBe(8);
    expect(s.severity).toBe('stop');
    expect(s.latencyMs).toBe(3);
    expect(s.effective).toBe(true);
    expect(s.reachedPids).toEqual([84716]);
    // close_marker results were noop / already_closed → not shockwaves
    expect(m.blasts.filter((x) => x.record.action === 'close_marker').every((x) => !x.effective)).toBe(true);
    // the outbound_post (seq 7) is a satellite of pid 84716 and lit STOP by finding 8
    expect(m.bySeq.get(7)?.pid).toBe(84716);
    expect(loudestCitation(m.bySeq.get(7)!)).toBe('stop');
    expect(loudestCitation(m.bySeq.get(7)!, 7)).toBeNull();
  });

  it('demo: real multi-level tree (python3.11 → pytest ×2, curl) with the stop group alive at seq 21', () => {
    const b = load('demo.jsonl');
    const m = blastRadius(b);
    expect(m.processes.get(48211)?.parentPid).toBeNull();
    expect(m.processes.get(48211)?.children.sort()).toEqual([48230, 48236, 48244]);
    const stop = m.blasts.find((x) => x.record.action === 'stop_pgroup')!;
    // pytest children exited before the stop (seq 6, 12); curl (exit seq 22) was still alive at 21
    expect(stop.reachedPids).toEqual([48211, 48244]);
    // the curl outbound_post is attached to curl's lifeline, not the root
    expect(m.bySeq.get(19)?.pid).toBe(48244);
    // drift / mismatch cite assistant_claim seqs too — those are accounted for as off-scene
    expect(m.offSceneEvidence.length).toBeGreaterThan(0);
  });

  it('claude-real-agent: curl peer pid 28040 is not in the recorded tree → unattached, no invented owner', () => {
    const b = load('claude-real-agent-proof.jsonl');
    const m = blastRadius(b);
    expect(m.processes.has(28040)).toBe(false);
    expect(m.bySeq.get(5)?.pid).toBeNull();
    expect(m.peerEdges).toEqual([]);
  });

  it('playhead sits just past the last drawn record at or before the cursor', () => {
    const b = load('demo-red.jsonl');
    const m = blastRadius(b);
    const n7 = m.bySeq.get(7)!;
    expect(playheadX(m, 7)).toBeGreaterThan(n7.pos[0]);
    expect(playheadX(m, 7)).toBeLessThan(m.bySeq.get(8)!.pos[0]);
    expect(playheadX(m, 0)).toBeLessThan(m.nodes[0]!.pos[0]);
  });
});
