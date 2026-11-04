/**
 * TraceTooltip — the "every number traces to a seq" affordance.
 *
 * `<TraceNumber t={traced} />` is the ONLY way the console renders a derived
 * number: it accepts a `Traced` (value + seqs + basis), so a number without
 * provenance cannot reach the screen. Hover / focus shows the basis and the
 * backing seqs; clicking a seq jumps the timeline to that record.
 */
import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import type { Traced } from '../lib/derive';
import { laneOf } from '../lib/derive';
import { KIND_LABEL } from '../lib/codes';
import { LANE_COLOR } from '../lib/tokens';
import { useNav } from '../lib/nav';

const MAX_CHIPS = 14;

export function SeqChip({ seq, label }: { seq: number; label?: string }) {
  const nav = useNav();
  const r = nav.bundle.bySeq.get(seq);
  const future = seq > nav.cursor;
  return (
    <button
      type="button"
      className={`seq-chip ${future ? 'opacity-40' : ''} ${nav.selected === seq ? 'border-accent text-accent' : ''}`}
      onClick={(e) => {
        e.stopPropagation();
        nav.jump(seq);
      }}
      onMouseEnter={() => nav.setHoverSeqs([seq])}
      onMouseLeave={() => nav.setHoverSeqs([])}
      title={r ? `seq ${seq} · ${KIND_LABEL[r.kind]} — click to jump` : `seq ${seq} (not in bundle)`}
      aria-label={`Jump to record ${seq}`}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: r ? LANE_COLOR[laneOf(r)] : '#566179' }} aria-hidden />
      #{seq}
      {label ? <span className="text-fg-3">{label}</span> : null}
    </button>
  );
}

interface TraceProps<T> {
  t: Traced<T>;
  format: (v: T) => ReactNode;
  className?: string;
  /** optional caption shown above the basis line */
  title?: string;
}

/** A traced value with a hover/focus provenance popover. */
export function TraceNumber<T>({ t, format, className = '', title }: TraceProps<T>) {
  const nav = useNav();
  const anchor = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const closeTimer = useRef<number | null>(null);

  const show = useCallback(() => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    setOpen(true);
    nav.setHoverSeqs(t.seqs);
  }, [nav, t.seqs]);
  const hide = useCallback(() => {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => {
      setOpen(false);
      nav.setHoverSeqs([]);
    }, 120);
  }, [nav]);

  useLayoutEffect(() => {
    if (!open || !anchor.current) return;
    const r = anchor.current.getBoundingClientRect();
    const above = r.top > 220;
    setPos({
      left: Math.min(Math.max(12, r.left + r.width / 2), window.innerWidth - 12),
      top: above ? r.top - 8 : r.bottom + 8,
      above,
    });
  }, [open]);

  const shown = t.seqs.slice(0, MAX_CHIPS);
  return (
    <>
      <span
        ref={anchor}
        tabIndex={0}
        role="button"
        aria-label={`${title ?? 'value'} — traces to ${t.seqs.length} record${t.seqs.length === 1 ? '' : 's'}`}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className={`cursor-help decoration-fg-5 decoration-dotted underline-offset-[6px] transition-colors hover:text-fg hover:decoration-accent/70 ${t.seqs.length ? 'underline' : ''} ${className}`}
      >
        {format(t.value)}
      </span>
      {open && pos
        ? createPortal(
            <div
              role="tooltip"
              onMouseEnter={show}
              onMouseLeave={hide}
              className="fixed z-[80] w-[300px] animate-pop-in rounded-lg border border-line-strong bg-[#0d121c]/95 p-3 text-left shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)] backdrop-blur-md"
              style={{
                left: pos.left,
                top: pos.top,
                transform: `translate(-50%, ${pos.above ? '-100%' : '0'})`,
              }}
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-glow-accent" aria-hidden />
                <span className="eyebrow text-accent">Traces to</span>
                <span className="ml-auto font-mono text-[11px] text-fg-3">
                  {t.seqs.length} record{t.seqs.length === 1 ? '' : 's'}
                </span>
              </div>
              {title ? <div className="mb-1 text-[12.5px] font-medium text-fg">{title}</div> : null}
              <div className="mb-2.5 text-[12px] leading-snug text-fg-3">{t.basis}</div>
              {t.seqs.length ? (
                <div className="flex flex-wrap gap-1">
                  {shown.map((s) => (
                    <SeqChip key={s} seq={s} />
                  ))}
                  {t.seqs.length > MAX_CHIPS ? (
                    <span className="chip text-fg-3">+{t.seqs.length - MAX_CHIPS} more</span>
                  ) : null}
                </div>
              ) : (
                <div className="font-mono text-[11px] text-fg-4">no backing records — value shown as “—”</div>
              )}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

export default TraceNumber;
