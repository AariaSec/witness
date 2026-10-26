/**
 * DriftPanel — EXPERIMENTAL behavioural-drift signal.
 *
 * A robust z-score (median/MAD) of session shape vs a benign baseline. It is
 * deliberately demoted: excluded from the headline numbers and from the
 * agreement rate, and never styled as a corroborated alarm. No threshold is
 * drawn because the bundle carries none — the console does not invent one.
 */
import type { LoadedBundle } from '../lib/loadBundle';
import { driftReadings } from '../lib/derive';
import { C } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

export interface DriftPanelProps {
  bundle: LoadedBundle;
  cursor: number;
}

export function DriftPanel({ bundle, cursor }: DriftPanelProps) {
  const readings = driftReadings(bundle, cursor);
  const maxScore = Math.max(5, ...readings.map((r) => Math.abs(r.score.value ?? 0)));

  return (
    <section className="card overflow-hidden" aria-label="Experimental drift signal">
      <div className="stripes-experimental h-1.5 border-b border-info/30" aria-hidden />
      <div className="card-hd">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Behavioural drift</span>
          <span className="rounded-sm border border-info/50 bg-info/10 px-1.5 py-[2px] font-mono text-[9.5px] font-bold tracking-[0.14em] text-info">EXPERIMENTAL</span>
        </div>
        <span className="font-mono text-[10.5px] text-fg-4">robust z · median/MAD</span>
      </div>
      <div className="px-5 py-4">
        {readings.length === 0 ? (
          <div className="py-3 text-[12.5px] text-fg-4">No drift reading in this bundle{bundle.findings.some((f) => f.fkind === 'drift') ? ' yet — scrub forward' : ''}.</div>
        ) : (
          readings.map(({ finding, score }) => {
            const v = score.value ?? 0;
            const pct = Math.min(100, (Math.abs(v) / maxScore) * 100);
            return (
              <div key={finding.seq} className="mb-3 last:mb-0">
                <div className="flex items-baseline justify-between gap-3">
                  <div className="flex items-baseline gap-2">
                    <TraceNumber
                      t={score}
                      title="Drift score"
                      format={(x) => <span className="font-mono text-[30px] font-semibold leading-none tracking-tight text-fg">{x === null ? '—' : x.toFixed(2)}</span>}
                    />
                    <span className="font-mono text-[11px] text-fg-4">z</span>
                  </div>
                  <span className="flex items-center gap-1.5 font-mono text-[10.5px] text-fg-4">
                    finding <SeqChip seq={finding.seq} /> · detector {finding.detector_version}
                  </span>
                </div>
                <div className="relative mt-3 h-2 overflow-hidden rounded-full bg-bg-well ring-1 ring-line">
                  <div
                    className="h-full rounded-full transition-[width] duration-700 ease-enter"
                    style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${C.info}55, ${C.info})`, boxShadow: `0 0 14px -2px ${C.info}` }}
                  />
                </div>
                <div className="mt-1 flex justify-between font-mono text-[9.5px] text-fg-5">
                  <span>0</span>
                  <span>scale to {maxScore.toFixed(0)} (display only — no threshold in bundle)</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <span className="mr-1 font-mono text-[10.5px] text-fg-4">shape computed over</span>
                  {finding.evidence_seqs.map((s) => (
                    <SeqChip key={s} seq={s} />
                  ))}
                </div>
              </div>
            );
          })
        )}
        <div className="mt-4 rounded-md border border-info/25 bg-info/[0.05] px-3 py-2.5 text-[12px] leading-snug text-fg-3">
          <span className="font-semibold text-info">Not a corroborated signal.</span> Drift compares this session’s shape (tool mix, destination novelty, inter-event gaps) with a benign baseline. It can fire on legitimate novelty, so it is excluded from the headline numbers and from the agreement rate, and it never triggers an action.
        </div>
      </div>
    </section>
  );
}

export default DriftPanel;
