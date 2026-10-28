/**
 * DivergenceFlow — "Agent said" vs "Reality recorded" as two paths.
 *
 * Every mark on this chart is one bundle record (lib/divergence.ts):
 *  - a column per record, in seq order (ordinal x — bursts stay legible);
 *  - the upper path carries the agent's assistant_claim records, the lower
 *    path the independently recorded fs / proc / decoy-network records;
 *  - the paths run together and split by one step per WARN finding and two
 *    per STOP finding, starting exactly at the column of the finding record;
 *  - green ties are claimAudit's corroborations (claim seq → act seq), red
 *    rings are its "never mentioned" acts.
 * Nothing is interpolated into data: the curves between columns are only
 * the drawing of the step changes. Click any mark to jump the timeline.
 */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { BundleRecord } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import { divergence, type DivergenceStep } from '../lib/divergence';
import { describe } from '../lib/describe';
import { FINDING_TITLE, SEVERITY_LABEL } from '../lib/codes';
import { useNav } from '../lib/nav';
import { C, LANE_COLOR, SEV_COLOR } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

const H = 304;
const MID = 176;
const PAD_L = 196;
const PAD_R = 84;
/** separation (px) while the paths are in step */
const G0 = 12;
/** maximum separation (px) */
const G_MAX = 196;

const CLAIM = LANE_COLOR.claim;
const REAL = C.accent;

function base(p: string): string {
  const i = p.lastIndexOf('/');
  return i >= 0 && i < p.length - 1 ? p.slice(i + 1) : p;
}

function clip(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/** short, schema-only node label */
function label(r: BundleRecord): string {
  switch (r.kind) {
    case 'assistant_claim': {
      const subj = r.claimed_paths[0] ?? r.claimed_hosts[0];
      return subj ? `${r.tool} ${base(subj)}` : r.tool;
    }
    case 'fs_event':
      return `${r.op} ${base(r.path)}`;
    case 'proc_event':
      return `${r.op} ${r.exe ?? `pid ${r.pid}`}`;
    case 'marker_read':
      return 'decoy key read';
    case 'outbound_post':
      return r.contains_marker ? 'POST + decoy' : 'POST → sink';
    case 'action_result':
      return `stopped · ${r.latency_ms} ms`;
    case 'finding':
      return FINDING_TITLE[r.fkind];
    default:
      return r.kind;
  }
}

function realityColor(r: BundleRecord): string {
  if (r.kind === 'fs_event') return LANE_COLOR.fs;
  if (r.kind === 'proc_event') return LANE_COLOR.proc;
  return LANE_COLOR.net;
}

/** Smooth path through knots with horizontal tangents (pure drawing of step changes). */
function smooth(pts: readonly [number, number][]): string {
  if (!pts.length) return '';
  let d = `M${pts[0]![0].toFixed(1)} ${pts[0]![1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1]!;
    const [x1, y1] = pts[i]!;
    if (y0 === y1) d += `L${x1.toFixed(1)} ${y1.toFixed(1)}`;
    else {
      const m = (x1 - x0) / 2;
      d += `C${(x0 + m).toFixed(1)} ${y0.toFixed(1)} ${(x1 - m).toFixed(1)} ${y1.toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`;
    }
  }
  return d;
}

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(1100);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setW(Math.max(560, Math.round(el.getBoundingClientRect().width)));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

interface Laid {
  step: DivergenceStep;
  x: number;
  /** half-separation before / after this column */
  hBefore: number;
  hAfter: number;
  past: boolean;
}

export function DivergenceFlow({ bundle, cursor }: { bundle: LoadedBundle; cursor: number }) {
  const nav = useNav();
  const [wrap, W] = useWidth<HTMLDivElement>();
  const dv = useMemo(() => divergence(bundle, cursor), [bundle, cursor]);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const n = dv.steps.length;
  const span = W - PAD_L - PAD_R;
  const dx = n > 1 ? span / (n - 1) : span;
  // fixed scale over the WHOLE bundle, so replay never rescales mid-split
  const k = dv.maxWeight > 0 ? Math.min(30, (G_MAX - G0) / dv.maxWeight) : 0;
  const half = (w: number) => (G0 + k * w) / 2;

  const laid: Laid[] = [];
  let prevW = 0;
  dv.steps.forEach((s, i) => {
    laid.push({ step: s, x: n > 1 ? PAD_L + i * dx : PAD_L + span / 2, hBefore: half(prevW), hAfter: half(s.weight), past: s.seq <= cursor });
    prevW = s.weight;
  });

  // knots: a split starts AT the finding column and opens over the next ~60% of a column
  const ease = Math.min(dx * 0.65, 54);
  const knots: [number, number][] = [[PAD_L - 28, half(0)]];
  for (const l of laid) {
    knots.push([l.x, l.hBefore]);
    if (l.hAfter !== l.hBefore) knots.push([l.x + ease, l.hAfter]);
  }
  const last = laid[laid.length - 1];
  knots.push([W - 8, last ? last.hAfter : half(0)]);

  const claimD = smooth(knots.map(([x, h]) => [x, MID - h]));
  const realD = smooth(knots.map(([x, h]) => [x, MID + h]));
  const riftD = `${claimD} ${smooth([...knots].reverse().map(([x, h]) => [x, MID + h])).replace(/^M/, 'L')} Z`;

  const lastPast = [...laid].reverse().find((l) => l.past);
  const cursorX = cursor >= (bundle.records[bundle.records.length - 1]?.seq ?? 0) ? W : lastPast ? lastPast.x + Math.min(dx * 0.5, 40) : PAD_L - 28;
  const revealW = mounted ? cursorX : PAD_L - 28;

  const hover = new Set(nav.hoverSeqs);
  const xBySeq = new Map(laid.map((l) => [l.step.seq, l]));
  const labelEvery = dx < 30 ? 0 : dx < 70 ? 2 : 1;
  // two label rows per side when columns are tight; label length fits the room it gets
  const stagger = labelEvery === 1 && dx < 150;
  const chars = Math.max(8, Math.min(22, Math.floor(((stagger || labelEvery === 2 ? 2 : 1) * dx - 8) / 6.4)));
  const rowOf = new Map<number, number>();
  {
    const nth: Record<string, number> = {};
    for (const l of laid) {
      const side = l.step.side === 'claim' ? 'c' : 'r';
      nth[side] = (nth[side] ?? -1) + 1;
      rowOf.set(l.step.seq, stagger ? (nth[side] as number) % 2 : 0);
    }
  }

  // finding labels: packed into up to three rows by estimated text extent (never overlapping)
  const fLabels: { l: Laid; row: number; end: boolean }[] = [];
  const rowRight = [-1e9, -1e9, -1e9];
  const rowLeft = [1e9, 1e9, 1e9];
  for (const l of laid) {
    const f = l.step.record;
    if (f.kind !== 'finding') continue;
    const wpx = (SEVERITY_LABEL[f.severity].length + FINDING_TITLE[f.fkind].length + String(f.seq).length + 3) * 6.6 + 16;
    const end = l.x + 6 + wpx > W - 8;
    const x0 = end ? l.x - 6 - wpx : l.x + 6;
    const x1 = x0 + wpx;
    let row = rowRight.findIndex((r, i) => x0 > r + 10 || x1 < (rowLeft[i] as number) - 10);
    if (row < 0) row = 2;
    rowRight[row] = Math.max(rowRight[row] as number, x1);
    rowLeft[row] = Math.min(rowLeft[row] as number, x0);
    fLabels.push({ l, row, end });
  }

  const split = dv.splitAt;
  // chip tone = loudest finding fired so far (state, not decoration)
  const fired = bundle.findings.filter((f) => f.seq <= cursor && f.fkind !== 'drift');
  const splitCol = fired.some((f) => f.severity === 'stop') ? C.stop : fired.some((f) => f.severity === 'warn') ? C.warn : C.info;
  const id = 'dv';

  const act = (seq: number) => ({
    role: 'button' as const,
    tabIndex: 0,
    style: { cursor: 'pointer' },
    onClick: () => nav.jump(seq),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') nav.jump(seq);
    },
    onMouseEnter: () => nav.setHoverSeqs([seq]),
    onMouseLeave: () => nav.setHoverSeqs([]),
  });

  const tip = (r: BundleRecord) => {
    const d = describe(r);
    return `seq ${r.seq} · ${d.title}${d.parts.length ? ` — ${d.parts.slice(0, 3).join(' · ')}` : ''}`;
  };

  return (
    <section className="card overflow-hidden" aria-label="Agent said versus reality recorded">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-3 border-b border-line px-5 py-4">
        <div className="min-w-[300px] flex-1">
          <div className="eyebrow text-accent">Divergence</div>
          <h2 className="mt-1.5 text-[20px] font-semibold leading-tight tracking-[-0.02em] text-fg">
            <span style={{ color: CLAIM }}>Agent said</span>
            <span className="mx-2 text-fg-4">vs</span>
            <span className="text-accent">reality recorded</span>
          </h2>
          <p className="mt-1 max-w-[760px] text-[12.5px] text-fg-3">
            One column per record, in seq order. The paths run together until a detector fires, then split — one step per WARN finding, two per STOP — at that finding’s exact seq.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {split ? (
            <div
              className="flex items-center gap-2 rounded-md border px-2.5 py-1.5"
              style={{ borderColor: `${splitCol}73`, background: `${splitCol}14`, boxShadow: `0 0 28px -10px ${splitCol}` }}
            >
              <span className="font-mono text-[10px] font-bold tracking-[0.14em]" style={{ color: splitCol }}>
                SPLIT AT
              </span>
              <SeqChip seq={split.seq} />
              <span className="text-[12px] text-fg-2">{FINDING_TITLE[split.fkind]}</span>
            </div>
          ) : (
            <div className="rounded-md border border-ok/35 bg-ok/[0.07] px-2.5 py-1.5 font-mono text-[10px] font-bold tracking-[0.14em] text-ok">IN STEP — NO FINDING YET</div>
          )}
          <div className="text-right font-mono text-[10.5px] leading-tight text-fg-4">
            separation
            <div className="text-[18px] font-semibold text-fg">
              <TraceNumber t={dv.weight} title="Path separation" format={(v) => <span>{v % 1 ? v.toFixed(1) : v}</span>} />
            </div>
          </div>
        </div>
      </div>

      <div ref={wrap} className="relative w-full bg-bg-well/40">
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block" role="img" aria-label="Agent claims path and recorded reality path, split at findings">
          <defs>
            <clipPath id={`${id}-reveal`}>
              <rect x="0" y="0" height={H} width={Math.max(0, revealW)} style={{ transition: mounted ? 'width 900ms cubic-bezier(0.2,0.8,0.2,1)' : 'none' }} />
            </clipPath>
            <linearGradient id={`${id}-rift`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={C.stop} stopOpacity="0.02" />
              <stop offset="0.5" stopColor={C.stop} stopOpacity="0.13" />
              <stop offset="1" stopColor={C.stop} stopOpacity="0.02" />
            </linearGradient>
            <filter id={`${id}-glow`} x="-5%" y="-50%" width="110%" height="200%">
              <feGaussianBlur stdDeviation="3.2" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* lane captions */}
          <g fontFamily="'JetBrains Mono Variable', ui-monospace, monospace" fontSize="10" fontWeight="700" letterSpacing="1.6">
            <text x={16} y={MID - half(0) - 18} fill={CLAIM}>
              AGENT SAID
            </text>
            <text x={16} y={MID - half(0) - 6} fill={C.fg4} fontWeight="500" letterSpacing="0.4" fontSize="9.5">
              its own narration
            </text>
            <text x={16} y={MID + half(0) + 16} fill={REAL}>
              REALITY RECORDED
            </text>
            <text x={16} y={MID + half(0) + 28} fill={C.fg4} fontWeight="500" letterSpacing="0.4" fontSize="9.5">
              fs · proc · decoy net
            </text>
          </g>

          {/* column guides */}
          {laid.map((l) => (
            <line key={`g${l.step.seq}`} x1={l.x} x2={l.x} y1={54} y2={H - 16} stroke={C.line} strokeOpacity={l.past ? 0.55 : 0.25} strokeDasharray="2 4" />
          ))}

          {/* ghost (not yet replayed) */}
          <path d={claimD} fill="none" stroke={CLAIM} strokeOpacity="0.12" strokeWidth="2" strokeDasharray="3 5" />
          <path d={realD} fill="none" stroke={REAL} strokeOpacity="0.12" strokeWidth="2" strokeDasharray="3 5" />

          <g clipPath={`url(#${id}-reveal)`}>
            <path d={riftD} fill={`url(#${id}-rift)`} />
            {/* corroboration ties: claimAudit's claim → act matches */}
            {laid
              .filter((l) => l.step.side === 'reality' && l.step.status === 'covered')
              .flatMap((l) =>
                l.step.coveredBy.map((cs) => {
                  const c = xBySeq.get(cs);
                  if (!c) return null;
                  const y1 = MID - c.hAfter;
                  const y2 = MID + l.hAfter;
                  return (
                    <path
                      key={`t${cs}-${l.step.seq}`}
                      d={`M${c.x} ${y1} C${c.x} ${(y1 + y2) / 2} ${l.x} ${(y1 + y2) / 2} ${l.x} ${y2}`}
                      fill="none"
                      stroke={C.ok}
                      strokeOpacity={hover.has(cs) || hover.has(l.step.seq) ? 0.95 : 0.5}
                      strokeWidth="1.4"
                    />
                  );
                }),
              )}
            <path d={claimD} fill="none" stroke={CLAIM} strokeWidth="2.6" strokeLinecap="round" filter={`url(#${id}-glow)`} />
            <path d={realD} fill="none" stroke={REAL} strokeWidth="2.6" strokeLinecap="round" filter={`url(#${id}-glow)`} />
          </g>

          {/* finding rifts + labels */}
          {fLabels.map(({ l, row, end }) => {
            const f = l.step.record;
            if (f.kind !== 'finding') return null;
            const col = SEV_COLOR[f.severity];
            const ly = 20 + row * 17;
            const top = MID - l.hAfter - 8;
            const bot = MID + l.hAfter + 8;
            const hot = hover.has(f.seq) || nav.selected === f.seq;
            return (
              <g key={`f${f.seq}`} opacity={l.past ? 1 : 0.18} {...act(f.seq)}>
                <title>{tip(f)}</title>
                <line x1={l.x} x2={l.x} y1={ly + 5} y2={top} stroke={col} strokeOpacity="0.45" strokeDasharray="2 3" />
                <rect x={l.x - 3.5} y={top} width={7} height={bot - top} rx={3.5} fill={col} fillOpacity={hot ? 0.55 : 0.28} stroke={col} strokeOpacity="0.9" />
                {l.past && f.severity === 'stop' ? (
                  <circle cx={l.x} cy={MID} r={9} fill="none" stroke={col} strokeWidth="1.5" className="animate-pulse-ring" style={{ transformBox: 'fill-box', transformOrigin: 'center' }} />
                ) : null}
                <circle cx={l.x} cy={MID} r={5} fill={col} style={{ filter: `drop-shadow(0 0 6px ${col})` }} />
                {l.past ? (
                <text x={end ? l.x - 6 : l.x + 6} y={ly} textAnchor={end ? 'end' : 'start'} fontSize="10.5" fontFamily="'JetBrains Mono Variable', ui-monospace, monospace" fill={col} fontWeight="700" letterSpacing="0.8">
                  {SEVERITY_LABEL[f.severity]}
                  <tspan fill={C.fg2} fontWeight="500" letterSpacing="0" dx="6">
                    {FINDING_TITLE[f.fkind]}
                  </tspan>
                  <tspan fill={C.fg4} fontWeight="500" letterSpacing="0" dx="6">
                    #{f.seq}
                  </tspan>
                </text>
                ) : null}
              </g>
            );
          })}

          {/* nodes */}
          {laid.map((l, i) => {
            const s = l.step;
            const r = s.record;
            const showLabel = labelEvery !== 0 && (labelEvery === 1 || i % 2 === 0);
            const hot = hover.has(s.seq) || nav.selected === s.seq;
            const op = l.past ? 1 : 0.22;
            if (s.side === 'claim') {
              const y = MID - l.hAfter;
              const col = s.status === 'contradicted' ? C.warn : s.status === 'unobservable' ? C.fg4 : CLAIM;
              return (
                <g key={s.seq} opacity={op} {...act(s.seq)}>
                  <title>{`${tip(r)} · ${s.status}`}</title>
                  <rect x={l.x - 6} y={y - 6} width={12} height={12} rx={2} transform={`rotate(45 ${l.x} ${y})`} fill={C.card} stroke={col} strokeWidth={hot ? 2.6 : 1.8} />
                  {s.status === 'contradicted' ? (
                    <text x={l.x} y={y + 3.5} textAnchor="middle" fontSize="9" fontWeight="800" fill={col}>
                      ≠
                    </text>
                  ) : (
                    <circle cx={l.x} cy={y} r={2.2} fill={col} />
                  )}
                  {showLabel ? (
                    <text x={l.x} y={y - 15 - (rowOf.get(s.seq) ?? 0) * 13} textAnchor="middle" fontSize="10" fontFamily="'JetBrains Mono Variable', ui-monospace, monospace" fill={hot ? C.fg : C.fg3}>
                      {clip(label(r), chars)}
                    </text>
                  ) : null}
                </g>
              );
            }
            if (s.side === 'stop') {
              const y = MID + l.hAfter;
              return (
                <g key={s.seq} opacity={op} {...act(s.seq)}>
                  <title>{tip(r)}</title>
                  <rect x={l.x - 7} y={y - 7} width={14} height={14} rx={2} fill={C.stop} style={{ filter: `drop-shadow(0 0 8px ${C.stop})` }} />
                  <rect x={l.x - 2.5} y={y - 2.5} width={5} height={5} fill="#1a0606" />
                  {showLabel ? (
                    <text x={l.x} y={y + 24 + (rowOf.get(s.seq) ?? 0) * 13} textAnchor="middle" fontSize="10" fontWeight="700" fontFamily="'JetBrains Mono Variable', ui-monospace, monospace" fill={C.stop}>
                      {clip(label(r), chars)}
                    </text>
                  ) : null}
                </g>
              );
            }
            if (s.side === 'reality') {
              const y = MID + l.hAfter;
              const col = realityColor(r);
              const unclaimed = s.status === 'unclaimed';
              return (
                <g key={s.seq} opacity={op} {...act(s.seq)}>
                  <title>{`${tip(r)} · ${unclaimed ? 'never mentioned by the agent' : s.status === 'covered' ? `covered by claim ${s.coveredBy.map((c) => `#${c}`).join(' ')}` : 'context'}`}</title>
                  {unclaimed ? <circle cx={l.x} cy={y} r={10} fill="none" stroke={C.stop} strokeOpacity="0.85" strokeWidth="1.5" strokeDasharray="3 2" /> : null}
                  <circle cx={l.x} cy={y} r={hot ? 6.5 : 5.2} fill={C.card} stroke={col} strokeWidth="2" />
                  <circle cx={l.x} cy={y} r={2.2} fill={col} />
                  {showLabel ? (
                    <text x={l.x} y={y + 25 + (rowOf.get(s.seq) ?? 0) * 13} textAnchor="middle" fontSize="10" fontFamily="'JetBrains Mono Variable', ui-monospace, monospace" fill={unclaimed ? '#ff8a8a' : hot ? C.fg : C.fg3}>
                      {clip(label(r), chars)}
                    </text>
                  ) : null}
                </g>
              );
            }
            return null;
          })}

          {/* playhead */}
          {cursorX < W ? (
            <g style={{ transform: `translateX(${mounted ? cursorX : PAD_L - 28}px)`, transition: 'transform 900ms cubic-bezier(0.2,0.8,0.2,1)' }}>
              <line x1={0} x2={0} y1={48} y2={H - 10} stroke={C.accent} strokeWidth="1.5" strokeOpacity="0.85" />
              <circle cx={0} cy={48} r={3.5} fill={C.accent} />
            </g>
          ) : null}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line px-5 py-2.5 font-mono text-[10.5px] text-fg-4">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rotate-45 rounded-[1px] border" style={{ borderColor: CLAIM }} /> claim
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rotate-45 rounded-[1px] border border-warn" /> claim not observed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full border" style={{ borderColor: LANE_COLOR.fs }} /> recorded act
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-dashed border-stop" /> never mentioned
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-px w-4 bg-ok" /> corroborated (claim → act)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-[2px] bg-stop" /> process group stopped
        </span>
        <span className="ml-auto">every mark is one record — hover for its seq, click to jump</span>
      </div>
    </section>
  );
}

export default DivergenceFlow;
