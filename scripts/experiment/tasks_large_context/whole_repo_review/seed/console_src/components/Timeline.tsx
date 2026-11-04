/**
 * Timeline — the flight-recorder view.
 *
 *  ┌ swimlanes ───────────────────────────────────────────────┐
 *  │ Agent said  ◆        ◆      ◆        ◆                    │  narration (digests)
 *  │ Files                  ■  ■                               │  fs watcher
 *  │ Processes    ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●        │  pgroup watcher
 *  │ Decoy net                          ▲    ▶                 │  marker · sink
 *  │ Witness                            ⚑    ⚑ ✓               │  findings · actions
 *  └──────────────────────────────────────── playhead ┃ ──────┘
 *  event log (seq-ordered rows, expandable)
 *
 * The x axis is ts_mono (monotonic); ORDER is always seq. Findings paint a
 * severity band from their earliest evidence to the moment they fired.
 */
import { useCallback, useContext, useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from 'react';
import type { BundleRecord, Finding, ProcEvent } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import { LANES, earliestEvidence, laneOf, timeToDetect, type Lane } from '../lib/derive';
import { describe, fieldsOf } from '../lib/describe';
import { FINDING_TITLE, KIND_LABEL, SEVERITY_LABEL } from '../lib/codes';
import { C, LANE_COLOR, SEV_COLOR } from '../lib/tokens';
import { clamp, fmtMs, fmtRel, fmtWall, shortHash } from '../lib/format';
import { SeqChip } from './TraceTooltip';
import { NavContext } from '../lib/nav';

export interface TimelineProps {
  bundle: LoadedBundle;
  /** replay cursor — inclusive seq */
  cursor: number;
  /** playhead position in ts_mono seconds */
  playT: number;
  selected: number | null;
  onSelect: (seq: number | null) => void;
  view: [number, number];
  onView: (v: [number, number]) => void;
  hoverSeqs: readonly number[];
  /** finding whose evidence links should be drawn */
  focusFinding: number | null;
  onFocusFinding: (seq: number | null) => void;
  following: boolean;
}

const GUTTER = 150;
const PAD_R = 18;
/** two rows of finding flags above the lanes */
const FLAG_ROWS = 2;
const FLAG_H = 19;
const TOP = 14 + FLAG_ROWS * FLAG_H;
const LANE_H = 38;
const AXIS_H = 26;

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(960);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const cw = entries[0]?.contentRect.width;
      if (cw) setW(cw);
    });
    ro.observe(el);
    setW(el.getBoundingClientRect().width || 960);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function niceStep(span: number, target: number): number {
  const raw = span / target;
  const p = 10 ** Math.floor(Math.log10(raw));
  const m = raw / p;
  return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p;
}

/* ================================================================ chart */

function Mark({ r, x, y, color, alarm }: { r: BundleRecord; x: number; y: number; color: string; alarm: boolean }) {
  const s = 5.5;
  const fill = alarm ? C.stop : color;
  switch (r.kind) {
    case 'assistant_claim':
      return <rect x={x - s} y={y - s} width={s * 2} height={s * 2} rx={2} transform={`rotate(45 ${x} ${y})`} fill={fill} />;
    case 'fs_event':
      return <rect x={x - s} y={y - s} width={s * 2} height={s * 2} rx={2} fill={fill} />;
    case 'proc_event':
      return r.op === 'spawn' ? (
        <circle cx={x} cy={y} r={s} fill={fill} />
      ) : (
        <circle cx={x} cy={y} r={s - 1.2} fill={C.bg} stroke={fill} strokeWidth={1.8} />
      );
    case 'marker_read':
      // key glyph
      return (
        <g fill="none" stroke={fill} strokeWidth={2} strokeLinecap="round">
          <circle cx={x - 2.5} cy={y} r={3.6} fill={C.bg} />
          <path d={`M${x + 1} ${y}h6m-2 0v3`} />
        </g>
      );
    case 'outbound_post':
      return <path d={`M${x - s} ${y - s}L${x + s + 1} ${y}L${x - s} ${y + s}Z`} fill={fill} />;
    case 'finding': {
      const c = SEV_COLOR[r.severity];
      return (
        <g>
          <path d={`M${x} ${y + 8}V${y - 9}`} stroke={c} strokeWidth={2} />
          <path d={`M${x} ${y - 9}h9l-3 4l3 4h-9Z`} fill={c} />
        </g>
      );
    }
    case 'action_result':
      return (
        <g>
          <circle cx={x} cy={y} r={s + 0.5} fill={C.bg} stroke={r.ok ? C.ok : C.stop} strokeWidth={1.6} />
          <path
            d={r.ok ? `M${x - 2.6} ${y}l1.8 2l3.6 -4` : `M${x - 2.5} ${y - 2.5}l5 5m0 -5l-5 5`}
            stroke={r.ok ? C.ok : C.stop}
            strokeWidth={1.7}
            fill="none"
            strokeLinecap="round"
          />
        </g>
      );
    case 'receipt':
      return (
        <g>
          <circle cx={x} cy={y} r={s + 1.5} fill={C.accent} />
          <circle cx={x} cy={y} r={s - 1.5} fill="none" stroke={C.bg} strokeWidth={1.4} />
        </g>
      );
    case 'run_end':
      return <rect x={x - 1.5} y={y - 9} width={3} height={18} rx={1} fill={C.fg3} />;
    case 'clock_warning':
      return <path d={`M${x} ${y - s - 1}L${x + s + 1} ${y + s}H${x - s - 1}Z`} fill="none" stroke={C.warn} strokeWidth={1.6} />;
    default:
      return <circle cx={x} cy={y} r={s - 1.5} fill={color} />;
  }
}

function SwimlaneChart(props: TimelineProps) {
  const { bundle, cursor, playT, selected, onSelect, view, onView, hoverSeqs, focusFinding, onFocusFinding } = props;
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ r: BundleRecord; x: number; y: number } | null>(null);
  const drag = useRef<{ x0: number; v: [number, number] } | null>(null);

  const H = TOP + LANES.length * LANE_H + AXIS_H;
  const PW = Math.max(100, width - GUTTER - PAD_R);
  const [v0, v1] = view;
  const span = Math.max(1e-6, v1 - v0);
  const x = useCallback((t: number) => GUTTER + ((t - v0) / span) * PW, [v0, span, PW]);
  const laneY = (l: Lane) => TOP + LANES.findIndex((L) => L.id === l) * LANE_H + LANE_H / 2;
  const full: [number, number] = useMemo(() => {
    const pad = Math.max(0.2, (bundle.span.t1 - bundle.span.t0) * 0.03);
    return [bundle.span.t0 - pad, bundle.span.t1 + pad];
  }, [bundle]);

  const hoverSet = useMemo(() => new Set(hoverSeqs), [hoverSeqs]);

  // process lifespans
  const lifespans = useMemo(() => {
    const out: { pid: number; exe: string; t0: number; t1: number | null; s0: number; s1: number | null }[] = [];
    const open = new Map<number, number>();
    for (const r of bundle.byKind.proc_event as ProcEvent[]) {
      if (r.op === 'spawn') {
        open.set(r.pid, out.length);
        out.push({ pid: r.pid, exe: r.exe ?? '?', t0: r.ts_mono, t1: null, s0: r.seq, s1: null });
      } else if (r.op === 'exit') {
        const i = open.get(r.pid);
        const span = i !== undefined ? out[i] : undefined;
        if (span) {
          span.t1 = r.ts_mono;
          span.s1 = r.seq;
        }
      }
    }
    return out;
  }, [bundle]);

  const focus = focusFinding !== null ? bundle.bySeq.get(focusFinding) : undefined;
  const focusF = focus && focus.kind === 'finding' ? focus : null;

  // ---- interactions
  const zoomAt = (clientX: number, factor: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = clamp(clientX - rect.left - GUTTER, 0, PW);
    const tAt = v0 + (px / PW) * span;
    const minSpan = 0.02;
    const maxSpan = full[1] - full[0];
    const ns = clamp(span * factor, minSpan, maxSpan);
    let n0 = tAt - (px / PW) * ns;
    n0 = clamp(n0, full[0], full[1] - ns);
    onView([n0, n0 + ns]);
  };

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        zoomAt(e.clientX, Math.exp(e.deltaY * 0.01));
      } else if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        const d = ((e.shiftKey ? e.deltaY : e.deltaX) / PW) * span;
        const n0 = clamp(v0 + d, full[0], full[1] - span);
        onView([n0, n0 + span]);
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  });

  const onPointerDown = (e: RPointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest('[data-mark]')) return;
    drag.current = { x0: e.clientX, v: [v0, v1] };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: RPointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    if (!d) return;
    const dt = ((d.x0 - e.clientX) / PW) * (d.v[1] - d.v[0]);
    const s = d.v[1] - d.v[0];
    const n0 = clamp(d.v[0] + dt, full[0], full[1] - s);
    onView([n0, n0 + s]);
  };
  const onPointerUp = () => {
    drag.current = null;
  };

  // ---- ticks
  const step = niceStep(span, Math.max(3, Math.floor(PW / 110)));
  const ticks: number[] = [];
  for (let t = Math.ceil(v0 / step) * step; t <= v1 + 1e-9; t += step) ticks.push(t);
  const digits = step < 0.01 ? 3 : step < 0.1 ? 2 : step < 1 ? 1 : 0;

  const visible = (r: BundleRecord) => r.seq <= cursor;
  const inView = (t: number) => t >= v0 - span * 0.05 && t <= v1 + span * 0.05;

  const markPos = (r: BundleRecord) => ({ x: x(r.ts_mono), y: laneY(laneOf(r)) });

  const playX = x(playT);

  return (
    <div ref={wrapRef} className="relative select-none">
      <svg
        ref={svgRef}
        width={width}
        height={H}
        className="block cursor-grab active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={() => onView(full)}
        role="img"
        aria-label="Swimlane timeline of recorded events"
      >
        <defs>
          <clipPath id="plot">
            <rect x={GUTTER} y={0} width={PW + PAD_R} height={H} />
          </clipPath>
          <linearGradient id="playglow" x1="0" x2="1">
            <stop offset="0" stopColor={C.accent} stopOpacity="0" />
            <stop offset="1" stopColor={C.accent} stopOpacity="0.10" />
          </linearGradient>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* lane rows + labels */}
        {LANES.map((l, i) => {
          const y0 = TOP + i * LANE_H;
          return (
            <g key={l.id}>
              <rect x={0} y={y0} width={width} height={LANE_H} fill={i % 2 ? 'rgba(255,255,255,0.012)' : 'transparent'} />
              <line x1={GUTTER} x2={width - PAD_R} y1={y0 + LANE_H / 2} y2={y0 + LANE_H / 2} stroke={C.line} strokeDasharray="1 5" />
              <rect x={14} y={y0 + LANE_H / 2 - 4} width={3} height={8} rx={1.5} fill={LANE_COLOR[l.id]} />
              <text x={26} y={y0 + LANE_H / 2 - 2} fill={C.fg2} fontSize={12} fontWeight={550} fontFamily="Inter Variable, Inter, sans-serif">
                {l.label}
              </text>
              <text x={26} y={y0 + LANE_H / 2 + 11} fill={C.fg4} fontSize={9.5} fontFamily="JetBrains Mono Variable, monospace">
                {l.sub}
              </text>
            </g>
          );
        })}
        <line x1={GUTTER - 0.5} x2={GUTTER - 0.5} y1={TOP - 6} y2={H - AXIS_H} stroke={C.line} />

        <g clipPath="url(#plot)">
          {/* grid */}
          {ticks.map((t) => (
            <line key={t} x1={x(t)} x2={x(t)} y1={TOP - 4} y2={H - AXIS_H} stroke={C.line} strokeOpacity={0.55} />
          ))}

          {/* replayed region tint */}
          <rect x={GUTTER} y={TOP} width={Math.max(0, playX - GUTTER)} height={LANES.length * LANE_H} fill="url(#playglow)" />

          {/* finding bands */}
          {bundle.findings.filter(visible).map((f) => {
            const e = earliestEvidence(bundle, f);
            const xa = x(e ? e.ts_mono : f.ts_mono);
            const xb = x(f.ts_mono);
            const c = SEV_COLOR[f.severity];
            const active = focusFinding === f.seq;
            return (
              <g key={`band-${f.seq}`} className="animate-band-in" style={{ transformOrigin: `${xb}px ${TOP}px` }}>
                <rect
                  x={Math.min(xa, xb) - 2}
                  y={TOP}
                  width={Math.max(4, Math.abs(xb - xa) + 4)}
                  height={LANES.length * LANE_H}
                  fill={c}
                  fillOpacity={active ? 0.16 : f.severity === 'stop' ? 0.1 : 0.06}
                  rx={3}
                />
                <line x1={xb} x2={xb} y1={TOP - 4} y2={H - AXIS_H} stroke={c} strokeOpacity={active ? 0.9 : 0.5} strokeWidth={active ? 1.5 : 1} />
              </g>
            );
          })}

          {/* process lifespans */}
          {lifespans.map((p) => {
            if (p.s0 > cursor) return null;
            const t1 = p.t1 !== null && p.s1 !== null && p.s1 <= cursor ? p.t1 : Math.min(playT, bundle.span.t1);
            const y = laneY('proc');
            return (
              <rect
                key={`life-${p.s0}`}
                x={x(p.t0)}
                y={y - 2}
                width={Math.max(1, x(t1) - x(p.t0))}
                height={4}
                rx={2}
                fill={LANE_COLOR.proc}
                fillOpacity={0.28}
              />
            );
          })}

          {/* ghosted future */}
          {bundle.records
            .filter((r) => !visible(r) && inView(r.ts_mono))
            .map((r) => {
              const { x: mx, y } = markPos(r);
              return <circle key={`g-${r.seq}`} cx={mx} cy={y} r={2.2} fill={C.fg4} fillOpacity={0.35} />;
            })}

          {/* evidence links for the focused finding */}
          {focusF && visible(focusF)
            ? focusF.evidence_seqs.map((s) => {
                const r = bundle.bySeq.get(s);
                if (!r) return null;
                const a = markPos(focusF);
                const b = markPos(r);
                const mx = (a.x + b.x) / 2;
                return (
                  <path
                    key={`link-${s}`}
                    d={`M${a.x} ${a.y}C${mx} ${a.y},${mx} ${b.y},${b.x} ${b.y}`}
                    fill="none"
                    stroke={SEV_COLOR[focusF.severity]}
                    strokeWidth={1.4}
                    strokeOpacity={0.85}
                    strokeDasharray="4 4"
                    filter="url(#glow)"
                  >
                    <animate attributeName="stroke-dashoffset" from="16" to="0" dur="0.8s" repeatCount="indefinite" />
                  </path>
                );
              })
            : null}

          {/* marks */}
          {bundle.records.filter(visible).map((r) => {
            if (!inView(r.ts_mono)) return null;
            const { x: mx, y } = markPos(r);
            const lane = laneOf(r);
            const d = describe(r);
            const isSel = selected === r.seq;
            const isHov = hoverSet.has(r.seq);
            return (
              <g
                key={r.seq}
                data-mark
                className="cursor-pointer"
                onMouseEnter={() => {
                  setHover({ r, x: mx, y });
                  if (r.kind === 'finding') onFocusFinding(r.seq);
                }}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(r.seq);
                  if (r.kind === 'finding') onFocusFinding(r.seq);
                }}
              >
                <circle cx={mx} cy={y} r={12} fill="transparent" />
                {(isSel || isHov) && (
                  <circle cx={mx} cy={y} r={11} fill="none" stroke={isSel ? C.accent : C.fg2} strokeWidth={1.5} strokeOpacity={0.9} />
                )}
                {r.seq === cursor && props.following ? (
                  <circle cx={mx} cy={y} r={7} fill="none" stroke={LANE_COLOR[lane]} className="origin-center animate-pulse-ring" style={{ transformBox: 'fill-box' }} />
                ) : null}
                <Mark r={r} x={mx} y={y} color={LANE_COLOR[lane]} alarm={!!d.alarm && r.kind !== 'finding'} />
              </g>
            );
          })}

          {/* playhead */}
          <g pointerEvents="none">
            <line x1={playX} x2={playX} y1={TOP - 10} y2={H - AXIS_H} stroke={C.accent} strokeWidth={1.5} />
            <path d={`M${playX - 5} ${TOP - 14}h10l-5 6Z`} fill={C.accent} />
          </g>

          {/* finding flags (top rail) — greedy row packing so labels never overlap;
              a flag that cannot fit collapses to a pin (hover the pin for details). */}
          {(() => {
            const rowsEnd = new Array<number>(FLAG_ROWS).fill(-Infinity);
            // the focused finding gets first claim on a labelled slot
            const fs = bundle.findings
              .filter((f) => visible(f) && inView(f.ts_mono))
              .sort((a, b) => (a.seq === focusFinding ? -1 : b.seq === focusFinding ? 1 : a.ts_mono - b.ts_mono));
            return fs.map((f) => {
              const xb = x(f.ts_mono);
              const c = SEV_COLOR[f.severity];
              const label = `${SEVERITY_LABEL[f.severity]} · ${FINDING_TITLE[f.fkind]}`;
              const w = label.length * 6.1 + 14;
              const flip = xb + w > width - PAD_R;
              const x0 = flip ? xb - w : xb;
              let row = -1;
              for (let i = 0; i < FLAG_ROWS; i++) {
                if ((rowsEnd[i] as number) + 6 < x0) {
                  row = i;
                  rowsEnd[i] = x0 + w;
                  break;
                }
              }
              const handlers = {
                onMouseEnter: () => onFocusFinding(f.seq),
                onClick: () => {
                  onSelect(f.seq);
                  onFocusFinding(f.seq);
                },
              };
              if (row < 0) {
                return (
                  <g key={`flag-${f.seq}`} className="animate-fade-in cursor-pointer" {...handlers}>
                    <title>{label}</title>
                    <path d={`M${xb - 4} ${TOP - 12}h8l-4 6Z`} fill={c} />
                  </g>
                );
              }
              const y = 4 + row * FLAG_H;
              return (
                <g key={`flag-${f.seq}`} className="animate-fade-in cursor-pointer" {...handlers}>
                  <line x1={xb} x2={xb} y1={y + 17} y2={TOP - 4} stroke={c} strokeOpacity={0.5} />
                  <rect x={x0} y={y} width={w} height={17} rx={4} fill={C.bg} stroke={c} strokeOpacity={focusFinding === f.seq ? 1 : 0.6} />
                  <text x={x0 + 7} y={y + 12} fill={c} fontSize={10} fontWeight={600} letterSpacing="0.06em" fontFamily="JetBrains Mono Variable, monospace">
                    {label}
                  </text>
                </g>
              );
            });
          })()}
        </g>

        {/* axis */}
        <g>
          <line x1={GUTTER} x2={width - PAD_R} y1={H - AXIS_H + 0.5} y2={H - AXIS_H + 0.5} stroke={C.lineStrong} />
          {ticks.map((t) => (
            <text key={t} x={x(t)} y={H - 8} textAnchor="middle" fill={C.fg4} fontSize={10} fontFamily="JetBrains Mono Variable, monospace">
              {t.toFixed(digits)}s
            </text>
          ))}
          <text x={14} y={H - 8} fill={C.fg4} fontSize={9.5} fontFamily="JetBrains Mono Variable, monospace">
            ts_mono · seq-ordered
          </text>
        </g>
      </svg>

      {hover ? <MarkTooltip b={bundle} r={hover.r} x={hover.x} y={hover.y} width={width} /> : null}
    </div>
  );
}

function MarkTooltip({ b, r, x, y, width }: { b: LoadedBundle; r: BundleRecord; x: number; y: number; width: number }) {
  const d = describe(r);
  const lane = laneOf(r);
  const left = clamp(x + 16, 8, width - 300);
  const ttd = r.kind === 'finding' ? timeToDetect(b, r) : null;
  return (
    <div
      className="pointer-events-none absolute z-20 w-[284px] animate-pop-in rounded-lg border border-line-strong bg-[#0d121c]/95 p-3 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)] backdrop-blur-md"
      style={{ left, top: y + 14 }}
    >
      <div className="mb-1 flex items-center gap-2 font-mono text-[11px]">
        <span className="h-2 w-2 rounded-full" style={{ background: LANE_COLOR[lane] }} />
        <span className="text-fg">#{r.seq}</span>
        <span className="text-fg-3">{KIND_LABEL[r.kind]}</span>
        <span className="ml-auto text-fg-4">{fmtRel(r.ts_mono)}</span>
      </div>
      <div className={`text-[13px] font-medium ${d.alarm ? 'text-stop' : 'text-fg'}`}>{d.title}</div>
      <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 font-mono text-[11px] text-fg-3">
        {d.parts.map((p, i) => (
          <span key={i}>{p}</span>
        ))}
      </div>
      {ttd && ttd.value !== null ? (
        <div className="mt-2 font-mono text-[11px] text-fg-2">detected {fmtMs(ttd.value)} after first evidence</div>
      ) : null}
    </div>
  );
}

/* ============================================================== event log */

function RecordInspector({ r, b }: { r: BundleRecord; b: LoadedBundle }) {
  const prevRec = b.records.find((x) => x.seq === r.seq - 1);
  const linkOk = r.seq === 0 ? r.prev === null : !!prevRec && r.prev === prevRec.digest;
  return (
    <div className="animate-fade-in border-t border-line bg-bg-well/70 px-4 py-3">
      <div className="grid grid-cols-1 gap-x-8 gap-y-1.5 md:grid-cols-2">
        {fieldsOf(r).map(([k, v]) => (
          <div key={k} className="flex min-w-0 items-baseline gap-3 font-mono text-[11.5px]">
            <span className="w-32 shrink-0 text-fg-4">{k}</span>
            <FieldValue k={k} v={v} />
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line-faint pt-2.5 font-mono text-[11px] text-fg-3">
        <span>
          wall <span className="text-fg-2">{fmtWall(r.ts_wall)}</span> <span className="text-fg-4">(display only)</span>
        </span>
        <span>
          mono <span className="text-fg-2">{r.ts_mono.toFixed(3)}s</span>
        </span>
        <span className="flex items-center gap-1.5">
          prev <span className="text-fg-2">{shortHash(r.prev, 8)}</span>
          <span className={linkOk ? 'text-ok' : 'text-stop'}>{linkOk ? '⟵ links to' : '✗ broken link'}</span>
          {r.seq > 0 ? <span className="text-fg-2">#{r.seq - 1}</span> : <span className="text-fg-4">genesis</span>}
        </span>
        <span>
          digest <span className="text-fg-2">{shortHash(r.digest, 8)}</span>
        </span>
      </div>
    </div>
  );
}

function FieldValue({ k, v }: { k: string; v: unknown }) {
  const nav = useNavSafe();
  if (Array.isArray(v)) {
    if (k === 'evidence_seqs' || k === 'seq_refs' || k === 'record_seqs') {
      return (
        <span className="flex flex-wrap gap-1">
          {(v as number[]).map((s) => (nav ? <SeqChip key={s} seq={s} /> : <span key={s}>#{s}</span>))}
        </span>
      );
    }
    if (v.length === 0) return <span className="text-fg-5">[]</span>;
    if (v.every((x) => typeof x !== 'object')) return <span className="break-all text-fg-2">{v.join(', ')}</span>;
    return <span className="break-all text-fg-3">{v.length} item{v.length === 1 ? '' : 's'}</span>;
  }
  if (v && typeof v === 'object') return <span className="break-all text-fg-3">{Object.keys(v).length} fields</span>;
  if (typeof v === 'string' && /^[0-9a-f]{64}$/.test(v)) {
    return (
      <span className="truncate text-fg-2" title={v}>
        {v.slice(0, 16)}
        <span className="text-fg-4">…{v.slice(-6)}</span>
      </span>
    );
  }
  if (typeof v === 'boolean') return <span className={v ? 'text-warn' : 'text-fg-3'}>{String(v)}</span>;
  if (v === null) return <span className="text-fg-5">null</span>;
  if (k === 'finding_seq' && typeof v === 'number' && nav) return <SeqChip seq={v} />;
  return <span className="break-all text-fg-2">{String(v)}</span>;
}

// Inspector renders inside NavContext in the app; tolerant of its absence in isolation.
function useNavSafe() {
  return useContext(NavContext);
}

function LogRow({
  r,
  b,
  selected,
  hovered,
  onClick,
  fresh,
}: {
  r: BundleRecord;
  b: LoadedBundle;
  selected: boolean;
  hovered: boolean;
  onClick: () => void;
  fresh: boolean;
}) {
  const d = describe(r);
  const lane = laneOf(r);
  const f = r.kind === 'finding' ? (r as Finding) : null;
  const sevColor = f ? SEV_COLOR[f.severity] : null;
  return (
    <div
      data-seq={r.seq}
      className={`group relative ${fresh ? 'animate-row-in' : ''} ${selected ? 'animate-flash bg-card-raised' : ''}`}
      style={f ? { background: `linear-gradient(90deg, ${sevColor}1f, transparent 55%)` } : undefined}
    >
      {f ? <span className="absolute inset-y-0 left-0 w-[2px]" style={{ background: sevColor ?? undefined }} /> : null}
      <button
        type="button"
        onClick={onClick}
        aria-expanded={selected}
        className={`grid w-full grid-cols-[52px_78px_118px_minmax(0,1fr)_96px] items-center gap-2 px-4 py-[7px] text-left transition-colors duration-150 hover:bg-white/[0.025] ${hovered ? 'bg-accent/[0.06]' : ''}`}
      >
        <span className={`font-mono text-[11.5px] ${selected ? 'text-accent' : 'text-fg-4'}`}>#{r.seq}</span>
        <span className="font-mono text-[11.5px] text-fg-3">{fmtRel(r.ts_mono)}</span>
        <span className="flex items-center gap-2 font-mono text-[11px] text-fg-3">
          <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: LANE_COLOR[lane] }} />
          {KIND_LABEL[r.kind]}
        </span>
        <span className="flex min-w-0 items-baseline gap-3">
          {f ? (
            <span className="shrink-0 rounded-sm px-1.5 py-[2px] font-mono text-[10px] font-bold tracking-wider" style={{ color: sevColor ?? undefined, background: `${sevColor}1a`, border: `1px solid ${sevColor}55` }}>
              {SEVERITY_LABEL[f.severity]}
            </span>
          ) : null}
          <span className={`shrink-0 text-[13px] ${d.alarm ? 'font-medium text-stop' : f ? 'font-medium text-fg' : 'text-fg-2'}`}>{d.title}</span>
          <span className="truncate font-mono text-[11px] text-fg-4">{d.parts.join('  ·  ')}</span>
        </span>
        <span className="text-right font-mono text-[10.5px] text-fg-5 group-hover:text-fg-4">{shortHash(r.digest, 4)}</span>
      </button>
      {selected ? <RecordInspector r={r} b={b} /> : null}
    </div>
  );
}

function EventLog(props: TimelineProps & { laneFilter: Set<Lane> }) {
  const { bundle, cursor, selected, onSelect, hoverSeqs, laneFilter, following } = props;
  const listRef = useRef<HTMLDivElement>(null);
  const hoverSet = useMemo(() => new Set(hoverSeqs), [hoverSeqs]);
  const rows = bundle.records.filter((r) => r.seq <= cursor && laneFilter.has(laneOf(r)));
  const future = bundle.records.filter((r) => r.seq > cursor).length;
  const lastSeen = useRef(cursor);
  const freshFrom = lastSeen.current;
  useEffect(() => {
    lastSeen.current = cursor;
  }, [cursor]);

  // keep selected row in view
  useEffect(() => {
    if (selected === null) return;
    const el = listRef.current?.querySelector<HTMLElement>(`[data-seq="${selected}"]`);
    if (el && listRef.current) {
      const c = listRef.current;
      const top = el.offsetTop - c.offsetTop;
      if (top < c.scrollTop || top > c.scrollTop + c.clientHeight - 60) c.scrollTo({ top: top - 80, behavior: 'smooth' });
    }
  }, [selected]);

  // follow the playhead during replay
  useEffect(() => {
    if (!following || !listRef.current) return;
    listRef.current.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  }, [cursor, following]);

  return (
    <div ref={listRef} className="relative max-h-[440px] overflow-y-auto" role="list" aria-label="Event log">
      <div className="sticky top-0 z-10 grid grid-cols-[52px_78px_118px_minmax(0,1fr)_96px] gap-2 border-b border-line bg-card/95 px-4 py-2 backdrop-blur">
        {['seq', 't mono', 'kind', 'what was recorded', 'digest'].map((h, i) => (
          <span key={h} className={`eyebrow text-fg-4 ${i === 4 ? 'text-right' : ''}`}>
            {h}
          </span>
        ))}
      </div>
      <div className="divide-y divide-line-faint">
        {rows.map((r) => (
          <LogRow
            key={r.seq}
            r={r}
            b={bundle}
            selected={selected === r.seq}
            hovered={hoverSet.has(r.seq)}
            fresh={r.seq > freshFrom}
            onClick={() => onSelect(selected === r.seq ? null : r.seq)}
          />
        ))}
      </div>
      {future > 0 ? (
        <div className="flex items-center gap-3 px-4 py-3 font-mono text-[11px] text-fg-4">
          <span className="h-px flex-1 bg-gradient-to-r from-accent/50 to-transparent" />
          {future} more record{future === 1 ? '' : 's'} after the playhead
          <span className="h-px flex-1 bg-gradient-to-l from-accent/50 to-transparent" />
        </div>
      ) : null}
    </div>
  );
}

/* ================================================================== shell */

export function Timeline(props: TimelineProps) {
  const { bundle, view, onView, cursor } = props;
  const [laneFilter, setLaneFilter] = useState<Set<Lane>>(() => new Set(LANES.map((l) => l.id)));
  const counts = useMemo(() => {
    const c: Record<Lane, number> = { claim: 0, proc: 0, fs: 0, net: 0, witness: 0, meta: 0 };
    for (const r of bundle.records) if (r.seq <= cursor) c[laneOf(r)]++;
    return c;
  }, [bundle, cursor]);
  const full: [number, number] = [
    bundle.span.t0 - Math.max(0.2, (bundle.span.t1 - bundle.span.t0) * 0.03),
    bundle.span.t1 + Math.max(0.2, (bundle.span.t1 - bundle.span.t0) * 0.03),
  ];
  const zoom = (f: number) => {
    const c = (view[0] + view[1]) / 2;
    const s = clamp((view[1] - view[0]) * f, 0.02, full[1] - full[0]);
    const n0 = clamp(c - s / 2, full[0], full[1] - s);
    onView([n0, n0 + s]);
  };
  const zoomPct = Math.round(((full[1] - full[0]) / (view[1] - view[0])) * 100);

  return (
    <section className="card overflow-hidden" aria-label="Timeline">
      <div className="card-hd">
        <div className="flex items-center gap-3">
          <span className="eyebrow">Timeline</span>
          <span className="font-mono text-[11px] text-fg-4">
            {bundle.records.length} records · {(bundle.span.t1 - bundle.span.t0).toFixed(2)}s monotonic
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="mr-2 hidden font-mono text-[10.5px] text-fg-4 lg:inline">⌘/ctrl + scroll to zoom · drag to pan · dbl-click to fit</span>
          <button type="button" className="btn px-2 py-1" onClick={() => zoom(1 / 1.6)} aria-label="Zoom in">
            +
          </button>
          <button type="button" className="btn px-2 py-1" onClick={() => zoom(1.6)} aria-label="Zoom out">
            −
          </button>
          <button type="button" className="btn px-2 py-1 font-mono text-[11px]" onClick={() => onView(full)} aria-label="Fit whole run">
            fit · {zoomPct}%
          </button>
        </div>
      </div>
      <div className="border-b border-line bg-bg-well/40 pb-1 pt-2">
        <SwimlaneChart {...props} />
      </div>
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2">
        <span className="eyebrow mr-1 text-fg-4">Lanes</span>
        {LANES.map((l) => {
          const on = laneFilter.has(l.id);
          return (
            <button
              key={l.id}
              type="button"
              aria-pressed={on}
              onClick={() =>
                setLaneFilter((s) => {
                  const n = new Set(s);
                  if (on) n.delete(l.id);
                  else n.add(l.id);
                  return n;
                })
              }
              className={`chip transition-all ${on ? '' : 'opacity-35'}`}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: LANE_COLOR[l.id] }} />
              {l.label}
              <span className="text-fg-4">{counts[l.id]}</span>
            </button>
          );
        })}
      </div>
      <EventLog {...props} laneFilter={laneFilter} />
    </section>
  );
}

export default Timeline;
