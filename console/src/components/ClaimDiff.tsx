/**
 * ClaimDiff — "reported vs recorded".
 *
 * Left: what the agent narrated about its own actions. The narration itself
 * is never stored — only its digest plus the structured fields the tailer
 * extracted (tool enum, paths, hosts, count). Right: what witness recorded
 * independently. Every pairing, contradiction and omission is called out,
 * and every number traces to seqs. Deterministic — no model involved; the
 * analyst report, if present, is shown as a cross-check, never as the source.
 */
import type { AssistantClaim, ClaimTool } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import { claimAudit, type ClaimItem, type ItemStatus, type RecordedAct, type Traced } from '../lib/derive';
import { describe } from '../lib/describe';
import { reportCodeText } from '../lib/codes';
import { fmtPct, fmtRel, shortHash } from '../lib/format';
import { C, LANE_COLOR } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

const VERB: Record<ClaimTool, string> = {
  read: 'read',
  write: 'wrote',
  edit: 'edited',
  shell: 'ran a shell command',
  http: 'contacted',
  search: 'searched',
  other: 'did an “other” action',
};

const STATUS: Record<ItemStatus | 'unclaimed', { label: string; color: string; glyph: string }> = {
  corroborated: { label: 'CORROBORATED', color: C.ok, glyph: '✓' },
  not_observed: { label: 'NOT OBSERVED', color: C.warn, glyph: '✗' },
  count_mismatch: { label: 'COUNT MISMATCH', color: C.warn, glyph: '≠' },
  unobservable: { label: 'NOT OBSERVABLE', color: C.fg4, glyph: '?' },
  unclaimed: { label: 'NEVER MENTIONED', color: C.stop, glyph: '!' },
};

function Pill({ s }: { s: keyof typeof STATUS }) {
  const st = STATUS[s];
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-sm px-1.5 py-[3px] font-mono text-[9.5px] font-bold tracking-[0.12em]"
      style={{ color: st.color, background: `${st.color}17`, border: `1px solid ${st.color}50` }}
    >
      <span aria-hidden>{st.glyph}</span>
      {st.label}
    </span>
  );
}

function claimSentence(c: AssistantClaim, item: ClaimItem): string {
  switch (item.subjectKind) {
    case 'count':
      return `reported ${item.claimed} file${item.claimed === 1 ? '' : 's'} changed`;
    case 'process':
      return VERB.shell;
    case 'none':
      return VERB[c.tool];
    default:
      return `${VERB[c.tool]} ${item.subject}`;
  }
}

function RecordedSide({ b, item }: { b: LoadedBundle; item: ClaimItem }) {
  if (item.status === 'unobservable') {
    return <span className="text-[12.5px] text-fg-4">A passive recorder cannot see reads — excluded from the rate, shown for completeness.</span>;
  }
  if (item.subjectKind === 'count') {
    return (
      <span className="flex flex-wrap items-center gap-2 text-[12.5px] text-fg-2">
        <span>
          recorded <b className={item.status === 'count_mismatch' ? 'text-warn' : 'text-ok'}>{item.recorded}</b> distinct file{item.recorded === 1 ? '' : 's'} changed
        </span>
        {item.recordSeqs.map((s) => (
          <SeqChip key={s} seq={s} />
        ))}
      </span>
    );
  }
  if (!item.recordSeqs.length) {
    return <span className="text-[12.5px] text-warn">no matching record anywhere in the run</span>;
  }
  return (
    <span className="flex min-w-0 flex-col gap-1">
      {item.recordSeqs.map((s) => {
        const r = b.bySeq.get(s);
        if (!r) return null;
        const d = describe(r);
        return (
          <span key={s} className="flex min-w-0 items-center gap-2">
            <SeqChip seq={s} />
            <span className="truncate text-[12.5px] text-fg-2">{d.title}</span>
            <span className="hidden truncate font-mono text-[10.5px] text-fg-4 xl:inline">{d.parts.slice(0, 2).join(' · ')}</span>
          </span>
        );
      })}
    </span>
  );
}

function Connector({ s }: { s: keyof typeof STATUS }) {
  const c = STATUS[s].color;
  const dashed = s === 'unobservable';
  return (
    <span className="relative flex h-full items-center justify-center" aria-hidden>
      <span className="absolute inset-x-0 top-1/2 h-px" style={{ background: dashed ? 'transparent' : `${c}66`, borderTop: dashed ? `1px dashed ${c}66` : undefined }} />
      <span
        className="relative flex h-6 w-6 items-center justify-center rounded-full border font-mono text-[12px] font-bold"
        style={{ color: c, borderColor: `${c}88`, background: C.card, boxShadow: s === 'unclaimed' ? `0 0 18px -2px ${c}aa` : undefined }}
      >
        {STATUS[s].glyph}
      </span>
    </span>
  );
}

function Segments({ parts }: { parts: { key: string; t: Traced; color: string; label: string; hatched?: boolean }[] }) {
  const total = parts.reduce((a, p) => a + p.t.value, 0) || 1;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-bg-well ring-1 ring-line">
        {parts.map((p) =>
          p.t.value ? (
            <div
              key={p.key}
              className="h-full transition-[width] duration-500 ease-enter"
              style={{
                width: `${(p.t.value / total) * 100}%`,
                background: p.hatched ? `repeating-linear-gradient(-45deg, ${p.color}66 0 4px, transparent 4px 8px)` : p.color,
                boxShadow: p.hatched ? undefined : `0 0 12px -2px ${p.color}`,
              }}
            />
          ) : null,
        )}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1.5">
        {parts.map((p) => (
          <span key={p.key} className="flex items-center gap-2 text-[12px] text-fg-3">
            <span className="h-2 w-2 rounded-[2px]" style={{ background: p.color }} />
            <TraceNumber t={p.t} title={p.label} format={(v) => <span className="font-mono font-semibold text-fg">{v}</span>} />
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function AgreementRing({ t }: { t: Traced<number | null> }) {
  const v = t.value ?? 0;
  const R = 34;
  const L = 2 * Math.PI * R;
  const color = t.value === null ? C.fg4 : v >= 0.999 ? C.ok : v >= 0.75 ? C.warn : C.stop;
  return (
    <div className="relative h-[92px] w-[92px] shrink-0">
      <svg viewBox="0 0 92 92" className="h-full w-full -rotate-90" aria-hidden>
        <circle cx="46" cy="46" r={R} fill="none" stroke={C.line} strokeWidth="7" />
        <circle
          cx="46"
          cy="46"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${L * v} ${L}`}
          style={{ transition: 'stroke-dasharray 700ms cubic-bezier(0.2,0.8,0.2,1)', filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <TraceNumber t={t} title="Agreement rate" format={(x) => <span className="font-mono text-[21px] font-semibold tracking-tight text-fg">{fmtPct(x)}</span>} />
        <span className="eyebrow mt-0.5 text-[8.5px] text-fg-4">agree</span>
      </div>
    </div>
  );
}

export interface ClaimDiffProps {
  bundle: LoadedBundle;
  cursor: number;
}

export function ClaimDiff({ bundle, cursor }: ClaimDiffProps) {
  const a = claimAudit(bundle, cursor);
  const report = bundle.report && bundle.report.seq <= cursor ? bundle.report : null;
  const unclaimedSeqs = new Set(a.unclaimed.map((u) => u.record.seq));
  const contradictedSeqs = new Set(a.contradicted.seqs);

  return (
    <section className="card overflow-hidden" aria-label="Reported versus recorded">
      <div className="relative flex flex-wrap items-center gap-6 border-b border-line px-5 py-5">
        <AgreementRing t={a.agreement} />
        <div className="min-w-[280px] flex-1">
          <div className="eyebrow text-accent">Reported vs recorded</div>
          <h2 className="mt-1.5 text-[22px] font-semibold leading-tight tracking-[-0.02em] text-fg">
            {a.verdict === 'no_claims'
              ? 'No narration recorded yet.'
              : a.verdict === 'agree'
                ? 'The agent’s account matches the record.'
                : 'The agent’s account does not match the record.'}
          </h2>
          <p className="mt-1 text-[13px] text-fg-3">
            Narration is stored as a digest plus structured fields (tool, paths, hosts, count) — never the words themselves. Each claimed item is matched against telemetry the agent cannot write to.
          </p>
          <div className="mt-4 max-w-[640px]">
            <Segments
              parts={[
                { key: 'c', t: a.corroborated, color: C.ok, label: 'corroborated' },
                { key: 'x', t: a.contradicted, color: C.warn, label: 'contradicted' },
                { key: 'u', t: a.unclaimedCount, color: C.stop, label: 'done but never mentioned' },
                { key: 'o', t: a.unobservable, color: C.fg4, label: 'not observable', hatched: true },
              ]}
            />
          </div>
        </div>
        {a.verdict === 'mismatch' ? (
          <div className="pointer-events-none absolute right-8 top-1/2 hidden -translate-y-1/2 lg:block" aria-hidden>
            <div className="animate-stamp rounded-md border-[3px] border-stop px-5 py-1.5 font-mono text-[34px] font-extrabold tracking-[0.16em] text-stop text-glow-stop opacity-90 [box-shadow:inset_0_0_0_2px_rgba(255,93,93,0.25)]">
              MISMATCH
            </div>
          </div>
        ) : a.verdict === 'agree' ? (
          <div className="pointer-events-none absolute right-8 top-1/2 hidden -translate-y-1/2 lg:block" aria-hidden>
            <div className="animate-stamp rounded-md border-[3px] border-ok px-5 py-1.5 font-mono text-[30px] font-extrabold tracking-[0.16em] text-ok text-glow-ok">CONSISTENT</div>
          </div>
        ) : null}
      </div>

      {/* column heads */}
      <div className="grid grid-cols-[minmax(0,1fr)_56px_minmax(0,1.15fr)] border-b border-line bg-bg-well/50 px-5 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rotate-45 rounded-[2px]" style={{ background: LANE_COLOR.claim }} />
          <span className="eyebrow" style={{ color: LANE_COLOR.claim }}>
            Agent said
          </span>
          <span className="font-mono text-[10.5px] text-fg-4">its own narration</span>
        </div>
        <div />
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-accent" />
          <span className="eyebrow text-accent">Witness recorded</span>
          <span className="font-mono text-[10.5px] text-fg-4">independent telemetry</span>
        </div>
      </div>

      <div className="divide-y divide-line-faint">
        {a.rows.flatMap((row) =>
          row.items.map((item, i) => (
            <div
              key={`${row.claim.seq}-${i}`}
              className="grid animate-row-in grid-cols-[minmax(0,1fr)_56px_minmax(0,1.15fr)] items-center gap-0 px-5 py-2.5 transition-colors hover:bg-white/[0.02]"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                {i === 0 ? <SeqChip seq={row.claim.seq} /> : <span className="w-[42px] shrink-0" />}
                <span className="min-w-0">
                  <span className="block truncate text-[13.5px] text-fg">{claimSentence(row.claim, item)}</span>
                  {i === 0 ? (
                    <span className="block font-mono text-[10.5px] text-fg-4">
                      {row.claim.source} · {fmtRel(row.claim.ts_mono)} · line {shortHash(row.claim.line_digest, 4)}
                    </span>
                  ) : null}
                </span>
              </div>
              <Connector s={item.status} />
              <div className="flex min-w-0 items-center gap-3">
                <Pill s={item.status} />
                <RecordedSide b={bundle} item={item} />
              </div>
            </div>
          )),
        )}

        {a.unclaimed.length ? (
          <div className="stripes-stop border-y border-stop/30 bg-stop/[0.05] px-5 py-2">
            <span className="eyebrow text-stop">Recorded — but the agent never mentioned it</span>
          </div>
        ) : null}
        {a.unclaimed.map((u: RecordedAct) => {
          const d = describe(u.record);
          return (
            <div key={u.record.seq} className="grid animate-row-in grid-cols-[minmax(0,1fr)_56px_minmax(0,1.15fr)] items-center bg-stop/[0.03] px-5 py-2.5">
              <div className="flex items-center gap-2.5 text-[13px] italic text-fg-4">
                <span className="w-[42px] shrink-0 text-center font-mono not-italic text-fg-5">∅</span>
                no claim covers this
              </div>
              <Connector s="unclaimed" />
              <div className="flex min-w-0 items-center gap-3">
                <Pill s="unclaimed" />
                <SeqChip seq={u.record.seq} />
                <span className={`truncate text-[13px] ${d.alarm ? 'font-medium text-stop' : 'text-fg'}`}>{d.title}</span>
                <span className="hidden truncate font-mono text-[10.5px] text-fg-4 xl:inline">{d.parts.slice(0, 2).join(' · ')}</span>
              </div>
            </div>
          );
        })}
        {a.rows.length === 0 && a.unclaimed.length === 0 ? (
          <div className="px-5 py-8 text-center text-[13px] text-fg-4">Nothing to compare yet — scrub forward.</div>
        ) : null}
      </div>

      {report && report.reported_vs_recorded.length ? (
        <div className="border-t border-line bg-bg-well/40 px-5 py-3.5">
          <div className="mb-2 flex items-center gap-2">
            <span className="eyebrow text-fg-3">Analyst cross-check</span>
            <span className="font-mono text-[10.5px] text-fg-4">
              {report.analyst_status === 'ok' ? report.model_id : `${report.analyst_status} · deterministic template`} · codes only, no free text
            </span>
          </div>
          <ul className="space-y-1.5">
            {report.reported_vs_recorded.map((d, i) => {
              const agrees = d.record_seqs.some((s) => unclaimedSeqs.has(s) || contradictedSeqs.has(s));
              const text = reportCodeText(d.code);
              return (
                <li key={i} className="flex flex-wrap items-center gap-2.5 text-[12.5px]">
                  <span className="chip text-fg-3">{d.code}</span>
                  <span className="text-fg-2">{text ?? <span className="text-fg-4">(unmapped code)</span>}</span>
                  <span className="text-fg-4">claim</span>
                  <SeqChip seq={d.claim_seq} />
                  <span className="text-fg-4">vs</span>
                  {d.record_seqs.map((s) => (
                    <SeqChip key={s} seq={s} />
                  ))}
                  <span className={`ml-auto font-mono text-[10.5px] ${agrees ? 'text-ok' : 'text-warn'}`}>
                    {agrees ? '✓ matches deterministic diff' : '≠ not in deterministic diff'}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export default ClaimDiff;
