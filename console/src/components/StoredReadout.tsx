import { useEffect, useState } from 'react';
import type { LoadedBundle } from '../lib/loadBundle';
import { auditReadout, type Readout, type Sidecar } from '../lib/citations';
import { reportCodeText } from '../lib/codes';
import { SeqChip } from './TraceTooltip';

const SEV: Record<string, string> = { stop: 'text-stop', warn: 'text-warn', info: 'text-info' };

/**
 * A stored read-out from a real Meta-model call, shown next to the signed record. The read-out is NOT part of the signed
 * chain (it is a sidecar file); the model is not trusted: every sequence number it cites is checked here, in the browser,
 * against the signed records.
 */
export function StoredReadout({ bundle }: { bundle: LoadedBundle }) {
  const [side, setSide] = useState<Sidecar | null>(null);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    let live = true;
    setSide(null);
    setIdx(0);
    const name = bundle.sourceName.replace(/\.jsonl$/, '');
    if (!/^[A-Za-z0-9._-]+$/.test(name)) return;
    fetch(`bundles/${name}.explain.json`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: Sidecar | null) => {
        if (live && j && Array.isArray(j.readouts) && j.readouts.length && (!j.run_id || j.run_id === bundle.manifest.run_id)) setSide(j);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [bundle]);

  if (!side) return null;
  const ro: Readout = side.readouts[Math.min(idx, side.readouts.length - 1)]!;
  const audit = auditReadout(ro.report, bundle.bySeq);
  const pct = (n: number) => (audit.total ? Math.round((100 * n) / audit.total) : 100);

  return (
    <section className="card overflow-hidden" aria-label="Meta-model read-out, citations checked in your browser">
      <div className="card-hd">
        <div className="flex flex-wrap items-center gap-2">
          <span className="eyebrow">Meta-model read-out</span>
          <span className="rounded-sm border border-info/40 bg-info/10 px-1.5 py-[2px] font-mono text-[9.5px] font-bold tracking-[0.12em] text-info">STORED OUTPUT OF A REAL CALL · NOT IN THE SIGNED CHAIN</span>
        </div>
        <div className="flex gap-1.5">
          {side.readouts.map((r, i) => (
            <button key={r.provider} type="button" className={`btn ${i === idx ? 'border-accent text-accent' : ''}`} onClick={() => setIdx(i)}>
              {r.label.split(' (')[0]}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div className="space-y-3">
          <div className="font-mono text-[11px] text-fg-3">
            {ro.label} · {ro.model_id.split('/').pop()} · {ro.wall_s.toFixed(1)} s{ro.attempts > 1 ? ` · attempt ${ro.attempts}` : ''} · {ro.generated_at.slice(0, 10)}
            <br />
            response sha256 {ro.response_sha256.slice(0, 16)}…
          </div>
          <div className="rounded-md border border-line bg-bg-well/50 p-3">
            <div className="eyebrow text-fg-4">Checked against the signed record, here, now</div>
            <div className="mt-1 text-[22px] font-semibold tracking-[-0.02em] text-fg">
              <span className={audit.exist === audit.total ? 'text-ok' : 'text-warn'}>{audit.exist}</span> of {audit.total} cited records exist
            </div>
            <div className="text-[13px] text-fg-3">
              <span className={audit.fit === audit.total ? 'text-ok' : 'text-warn'}>{audit.fit}</span> of {audit.total} are the right kind of record for the code ({pct(audit.fit)}%). The model is not trusted: a ✗ means this bundle does not support what it said.
            </div>
          </div>
          <div className="text-[12px] text-fg-4">Advisory only. The deterministic chain, signature and policy checks decide pass or fail; this read-out can be removed without changing any verdict.</div>
        </div>
        <ul className="space-y-1.5">
          {audit.steps.map(({ step, checks }, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 text-[12.5px]">
              <span className={`w-12 font-mono text-[10px] font-bold uppercase ${SEV[step.severity] ?? 'text-fg-3'}`}>{step.severity}</span>
              <span className="min-w-[150px] text-fg-2">{reportCodeText(step.code) ?? step.code}</span>
              <span className="font-mono text-[10px] text-fg-4">{step.code}</span>
              {checks.map((c) => (
                <span key={c.seq} className="inline-flex items-center gap-1" title={c.exists ? `record #${c.seq} is a ${c.kind}${c.fits ? '' : ' (not a kind that supports this code)'}` : `no record #${c.seq} in this bundle`}>
                  <SeqChip seq={c.seq} />
                  <span className={`font-mono text-[11px] font-bold ${c.exists && c.fits ? 'text-ok' : 'text-stop'}`}>{c.exists && c.fits ? '✓' : '✗'}</span>
                </span>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
