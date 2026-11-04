/**
 * ReportPanel — the analyst's report, rendered from ENUM CODES only.
 * The report has no free-text field by design; codes map through a fixed
 * console table (lib/codes.ts). Unknown codes are shown verbatim as codes.
 */
import type { LoadedBundle } from '../lib/loadBundle';
import { reportCodeText } from '../lib/codes';
import { traced } from '../lib/derive';
import { shortHash } from '../lib/format';
import { C } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

const SEV_TONE: Record<string, string> = { stop: C.stop, warn: C.warn, info: C.info };

export function ReportPanel({ bundle, cursor }: { bundle: LoadedBundle; cursor: number }) {
  const r = bundle.report;
  if (!r) {
    return (
      <section className="card p-5" aria-label="Analyst report">
        <div className="eyebrow">Analyst report</div>
        <p className="mt-3 text-[12.5px] text-fg-4">No report record in this bundle. Everything above is computed locally from the records alone.</p>
      </section>
    );
  }
  const shown = cursor >= r.seq;
  const offline = r.analyst_status !== 'ok';
  const conf = traced(r.confidence, [r.seq], `confidence field of report seq ${r.seq}`);
  const tools = traced(r.tool_calls, [r.seq], `tool_calls field of report seq ${r.seq} (read-only get_record / query)`);

  return (
    <section className="card overflow-hidden" aria-label="Analyst report">
      <div className="card-hd">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Analyst report</span>
          <span
            className={`rounded-sm border px-1.5 py-[2px] font-mono text-[9.5px] font-bold tracking-[0.12em] ${
              r.analyst_status === 'ok' ? 'border-ok/40 bg-ok/10 text-ok' : r.analyst_status === 'offline' ? 'border-fg-4/50 bg-white/[0.03] text-fg-3' : 'border-stop/40 bg-stop/10 text-stop'
            }`}
          >
            {r.analyst_status === 'ok' ? 'MODEL' : r.analyst_status === 'offline' ? 'OFFLINE TEMPLATE' : 'SCHEMA FAIL'}
          </span>
        </div>
        <SeqChip seq={r.seq} />
      </div>
      {!shown ? (
        <div className="px-5 py-6 text-[12.5px] text-fg-4">Report is appended after the receipt — scrub to the end.</div>
      ) : (
        <div className="animate-fade-in px-5 py-4">
          <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-fg-4">
            <span>
              model <span className="text-fg-2">{r.model_id}</span>
            </span>
            <span>
              prompt <span className="text-fg-2">{shortHash(r.prompt_version, 4)}</span>
            </span>
            <span>
              tool calls <TraceNumber t={tools} title="Analyst tool calls" format={(v) => <span className="text-fg-2">{v}</span>} />
            </span>
            <span>
              confidence <TraceNumber t={conf} title="Analyst confidence" format={(v) => <span className="text-fg-2">{v.toFixed(2)}</span>} />
            </span>
          </div>
          {offline ? (
            <div className="mb-3 rounded-md border border-line bg-bg-well/60 px-3 py-2 text-[12px] text-fg-3">
              {r.analyst_status === 'offline'
                ? 'No model was called — this is the deterministic offline template built from record counts.'
                : 'The model output failed schema validation; this is the fallback template.'}
            </div>
          ) : null}
          <ul className="space-y-1.5">
            {r.summary_codes.map((c) => (
              <li key={c} className="flex items-start gap-2.5">
                <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span className="text-[13px] text-fg-2">{reportCodeText(c) ?? <span className="font-mono text-fg-3">{c}</span>}</span>
                <span className="ml-auto chip shrink-0 text-fg-4">{c}</span>
              </li>
            ))}
          </ul>
          {r.timeline.length ? (
            <>
              <div className="eyebrow mb-2 mt-4 text-fg-4">Report timeline</div>
              <ol className="relative space-y-2 border-l border-line pl-4">
                {r.timeline.map((s, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 bg-card" style={{ borderColor: SEV_TONE[s.severity] ?? C.fg4 }} />
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[12.5px] text-fg-2">{reportCodeText(s.code) ?? s.code}</span>
                      {s.seq_refs.map((q) => (
                        <SeqChip key={q} seq={q} />
                      ))}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </div>
      )}
    </section>
  );
}

export default ReportPanel;
