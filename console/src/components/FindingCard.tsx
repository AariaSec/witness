/**
 * FindingCard — one detector finding, expandable.
 *
 * Collapsed: severity, what fired, time-to-detect (traced), evidence chips.
 * Expanded: every evidence record (click → jump), the actions the policy took
 * with their latencies, detector version. Drift findings are labelled
 * experimental and never styled as a corroborated alarm.
 */
import { useState } from 'react';
import type { Finding } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import { actionTimings, timeToDetect } from '../lib/derive';
import { describe } from '../lib/describe';
import { ACTION_LABEL, FINDING_BLURB, FINDING_TITLE, KIND_LABEL, SEVERITY_LABEL } from '../lib/codes';
import { LANE_COLOR, SEV_CLASSES, SEV_COLOR } from '../lib/tokens';
import { laneOf } from '../lib/derive';
import { fmtMs, fmtRel } from '../lib/format';
import { SeqChip, TraceNumber } from './TraceTooltip';
import { useNav } from '../lib/nav';

export interface FindingCardProps {
  bundle: LoadedBundle;
  finding: Finding;
  cursor: number;
  defaultOpen?: boolean;
  focused: boolean;
  onFocus: (seq: number | null) => void;
}

function SeverityIcon({ sev }: { sev: Finding['severity'] }) {
  const c = SEV_COLOR[sev];
  if (sev === 'stop')
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
        <path d="M6 1.5h6L16.5 6v6L12 16.5H6L1.5 12V6Z" fill={`${c}22`} stroke={c} strokeWidth="1.5" />
        <rect x="6" y="6" width="6" height="6" rx="1" fill={c} />
      </svg>
    );
  if (sev === 'warn')
    return (
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
        <path d="M9 2L16.5 15.5H1.5Z" fill={`${c}22`} stroke={c} strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M9 7v4" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="9" cy="13.2" r="1" fill={c} />
      </svg>
    );
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <circle cx="9" cy="9" r="7.25" fill={`${c}22`} stroke={c} strokeWidth="1.5" />
      <path d="M9 8v4.5" stroke={c} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="9" cy="5.6" r="1" fill={c} />
    </svg>
  );
}

export function FindingCard({ bundle, finding: f, cursor, defaultOpen = false, focused, onFocus }: FindingCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const nav = useNav();
  const ttd = timeToDetect(bundle, f);
  const acts = actionTimings(bundle, f, cursor);
  const sev = SEV_CLASSES[f.severity];
  const experimental = f.fkind === 'drift';
  const isStop = f.severity === 'stop';

  return (
    <article
      className={`relative animate-pop-in overflow-hidden rounded-xl border bg-card transition-all duration-200 ease-enter ${sev.border} ${
        focused ? `${sev.glow} -translate-y-px` : 'hover:-translate-y-px'
      } ${isStop ? 'shadow-glow-stop' : ''}`}
      onMouseEnter={() => onFocus(f.seq)}
      aria-label={`${SEVERITY_LABEL[f.severity]} finding: ${FINDING_TITLE[f.fkind]}`}
    >
      {isStop ? <div className="stripes-stop pointer-events-none absolute inset-x-0 top-0 h-1" aria-hidden /> : null}
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{ background: `radial-gradient(420px 120px at 0% 0%, ${SEV_COLOR[f.severity]}1c, transparent 70%)` }}
        aria-hidden
      />
      <button
        type="button"
        className="relative flex w-full items-start gap-3 px-4 pb-3 pt-3.5 text-left"
        onClick={() => {
          setOpen((o) => !o);
          nav.jump(f.seq);
        }}
        aria-expanded={open}
      >
        <span className="mt-[1px] shrink-0">
          <SeverityIcon sev={f.severity} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className={`font-mono text-[10.5px] font-bold tracking-[0.14em] ${sev.text}`}>{SEVERITY_LABEL[f.severity]}</span>
            <span className="text-[14.5px] font-semibold tracking-[-0.01em] text-fg">{FINDING_TITLE[f.fkind]}</span>
            {experimental ? (
              <span className="stripes-experimental rounded-sm border border-info/40 px-1.5 py-[2px] font-mono text-[9.5px] font-semibold tracking-[0.12em] text-info">
                EXPERIMENTAL
              </span>
            ) : null}
          </span>
          <span className="mt-1 block text-[12.5px] leading-snug text-fg-3">{FINDING_BLURB[f.fkind]}</span>
        </span>
        <span className="shrink-0 text-right">
          <span className="block font-mono text-[11px] text-fg-4">#{f.seq}</span>
          <span className="block font-mono text-[11px] text-fg-4">{fmtRel(f.ts_mono)}</span>
        </span>
      </button>

      <div className="relative flex flex-wrap items-center gap-x-5 gap-y-2 px-4 pb-3">
        <div className="flex items-baseline gap-2">
          <span className="eyebrow text-fg-4">detect</span>
          <TraceNumber
            t={ttd}
            title="Time to detect"
            format={(v) => <span className="font-mono text-[13px] font-semibold text-fg">{v === null ? '—' : fmtMs(v)}</span>}
          />
        </div>
        {acts.map((a) => (
          <div key={a.action.seq} className="flex items-baseline gap-2">
            <span className={`eyebrow ${a.action.ok ? 'text-ok/80' : 'text-stop'}`}>
              {a.action.action === 'stop_pgroup' ? 'stop' : a.action.action === 'close_marker' ? 'close' : 'sign'}
            </span>
            <TraceNumber
              t={a.latency}
              title={`${ACTION_LABEL[a.action.action]} latency`}
              format={(v) => (
                <span className={`font-mono text-[13px] font-semibold ${a.action.ok ? 'text-ok' : 'text-stop'}`}>
                  {a.action.ok ? '' : 'FAILED · '}
                  {fmtMs(v)}
                </span>
              )}
            />
          </div>
        ))}
        <div className="ml-auto flex flex-wrap gap-1">
          {f.evidence_seqs.slice(0, open ? 0 : 6).map((s) => (
            <SeqChip key={s} seq={s} />
          ))}
          {!open && f.evidence_seqs.length > 6 ? <span className="chip text-fg-4">+{f.evidence_seqs.length - 6}</span> : null}
        </div>
      </div>

      {open ? (
        <div className="relative animate-fade-in border-t border-line bg-bg-well/60 px-4 py-3">
          <div className="eyebrow mb-2 text-fg-4">Evidence · {f.evidence_seqs.length} record{f.evidence_seqs.length === 1 ? '' : 's'}</div>
          <ol className="space-y-1">
            {f.evidence_seqs.map((s) => {
              const r = bundle.bySeq.get(s);
              if (!r)
                return (
                  <li key={s} className="font-mono text-[11.5px] text-stop">
                    #{s} — not in this bundle
                  </li>
                );
              const d = describe(r);
              return (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => nav.jump(s)}
                    onMouseEnter={() => nav.setHoverSeqs([s])}
                    onMouseLeave={() => nav.setHoverSeqs([])}
                    className="group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
                  >
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: LANE_COLOR[laneOf(r)] }} />
                    <span className="w-9 shrink-0 font-mono text-[11.5px] text-fg-4 group-hover:text-accent">#{s}</span>
                    <span className="w-[86px] shrink-0 font-mono text-[11px] text-fg-4">{KIND_LABEL[r.kind]}</span>
                    <span className={`min-w-0 flex-1 truncate text-[12.5px] ${d.alarm ? 'text-stop' : 'text-fg-2'}`}>{d.title}</span>
                    <span className="shrink-0 font-mono text-[10.5px] text-fg-5 group-hover:text-fg-3">jump →</span>
                  </button>
                </li>
              );
            })}
          </ol>
          {acts.length ? (
            <>
              <div className="eyebrow mb-2 mt-3 text-fg-4">Policy actions</div>
              <ul className="space-y-1">
                {acts.map((a) => (
                  <li key={a.action.seq} className="flex flex-wrap items-center gap-3 px-2 font-mono text-[11.5px]">
                    <SeqChip seq={a.action.seq} />
                    <span className={a.action.ok ? 'text-ok' : 'text-stop'}>{a.action.ok ? '✓' : '✗'}</span>
                    <span className="text-fg-2">{ACTION_LABEL[a.action.action]}</span>
                    {a.action.detail ? <span className="text-fg-4">{a.action.detail}</span> : null}
                    <span className="ml-auto text-fg-3">
                      evidence → done{' '}
                      <TraceNumber t={a.evidenceToDone} title="Evidence to action complete" format={(v) => (v === null ? '—' : fmtMs(v))} className="text-fg" />
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <div className="mt-3 flex items-center gap-4 font-mono text-[10.5px] text-fg-4">
            <span>detector {f.detector_version}</span>
            {f.score !== null ? <span>score {f.score}</span> : null}
            <span>digest {f.digest?.slice(0, 12) ?? '—'}…</span>
          </div>
        </div>
      ) : null}
    </article>
  );
}

export default FindingCard;
