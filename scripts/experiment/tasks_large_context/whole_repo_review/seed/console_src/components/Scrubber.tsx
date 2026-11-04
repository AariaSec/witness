/**
 * Scrubber — compact transport + minimap for long runs.
 *
 * Minimap: record density per lane, finding pins (severity-coloured), the
 * current zoom window (drag to pan, edges to resize) and the playhead (drag
 * to scrub). Transport: restart, play/pause, step, speed.
 */
import { useMemo, useRef, type PointerEvent as RPointerEvent } from 'react';
import type { LoadedBundle } from '../lib/loadBundle';
import { LANES, laneOf } from '../lib/derive';
import { C, LANE_COLOR, SEV_COLOR } from '../lib/tokens';
import { clamp, fmtClock } from '../lib/format';

export interface ScrubberProps {
  bundle: LoadedBundle;
  playT: number;
  cursor: number;
  playing: boolean;
  speed: number;
  view: [number, number];
  onSeekTime: (t: number) => void;
  onTogglePlay: () => void;
  onRestart: () => void;
  onStep: (dir: -1 | 1) => void;
  onSpeed: (s: number) => void;
  onView: (v: [number, number]) => void;
}

const SPEEDS = [0.5, 1, 2, 4, 8];

function Icon({ d, label }: { d: string; label: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-label={label} role="img">
      <path d={d} fill="currentColor" />
    </svg>
  );
}

export function Scrubber(p: ScrubberProps) {
  const { bundle, playT, cursor, playing, speed, view } = p;
  const track = useRef<HTMLDivElement>(null);
  const drag = useRef<{ mode: 'seek' | 'pan' | 'l' | 'r'; x0: number; v: [number, number] } | null>(null);
  const t0 = bundle.span.t0;
  const t1 = bundle.span.t1;
  const total = Math.max(1e-6, t1 - t0);
  const frac = (t: number) => clamp((t - t0) / total, 0, 1);

  const BINS = 120;
  const density = useMemo(() => {
    const out = LANES.map(() => new Array<number>(BINS).fill(0));
    for (const r of bundle.records) {
      const li = LANES.findIndex((l) => l.id === laneOf(r));
      const bi = Math.min(BINS - 1, Math.floor(frac(r.ts_mono) * BINS));
      const row = out[li];
      if (row) row[bi] = (row[bi] ?? 0) + 1;
    }
    return out;
  }, [bundle]);
  const maxD = Math.max(1, ...density.flat());

  const tAt = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect) return t0;
    return t0 + clamp((clientX - rect.left) / rect.width, 0, 1) * total;
  };

  const onDown = (e: RPointerEvent<HTMLDivElement>, mode: 'seek' | 'pan' | 'l' | 'r') => {
    e.stopPropagation();
    drag.current = { mode, x0: e.clientX, v: view };
    track.current?.setPointerCapture(e.pointerId);
    if (mode === 'seek') p.onSeekTime(tAt(e.clientX));
  };
  const onMove = (e: RPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    const rect = track.current?.getBoundingClientRect();
    if (!rect) return;
    if (d.mode === 'seek') return p.onSeekTime(tAt(e.clientX));
    const dt = ((e.clientX - d.x0) / rect.width) * total;
    const lo = t0 - total * 0.05;
    const hi = t1 + total * 0.05;
    const s = d.v[1] - d.v[0];
    if (d.mode === 'pan') {
      const n0 = clamp(d.v[0] + dt, lo, hi - s);
      p.onView([n0, n0 + s]);
    } else if (d.mode === 'l') {
      p.onView([clamp(d.v[0] + dt, lo, d.v[1] - 0.02), d.v[1]]);
    } else {
      p.onView([d.v[0], clamp(d.v[1] + dt, d.v[0] + 0.02, hi)]);
    }
  };
  const onUp = () => {
    drag.current = null;
  };

  const vl = frac(view[0]) * 100;
  const vr = frac(view[1]) * 100;
  const last = bundle.records[bundle.records.length - 1];

  return (
    <div className="flex items-center gap-4">
      {/* transport */}
      <div className="flex shrink-0 items-center gap-1">
        <button type="button" className="btn h-8 w-8 justify-center p-0" onClick={p.onRestart} aria-label="Restart replay" title="Restart (Home)">
          <Icon label="restart" d="M2 2h2v10H2zM12 2v10L5 7z" />
        </button>
        <button type="button" className="btn h-8 w-8 justify-center p-0" onClick={() => p.onStep(-1)} aria-label="Previous record" title="Previous record (←)">
          <Icon label="previous" d="M11 2v10L4 7zM2 2h2v10H2z" />
        </button>
        <button
          type="button"
          onClick={p.onTogglePlay}
          aria-label={playing ? 'Pause replay' : 'Play replay'}
          title="Play / pause (space)"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-[#1a1206] shadow-glow-accent transition-transform hover:scale-105 active:scale-95"
        >
          {playing ? <Icon label="pause" d="M3 2h3v10H3zM8 2h3v10H8z" /> : <Icon label="play" d="M3.5 1.8v10.4L12 7z" />}
        </button>
        <button type="button" className="btn h-8 w-8 justify-center p-0" onClick={() => p.onStep(1)} aria-label="Next record" title="Next record (→)">
          <Icon label="next" d="M3 2v10l7-5zM10 2h2v10h-2z" />
        </button>
        <div className="ml-1 flex overflow-hidden rounded-md border border-line-strong">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => p.onSpeed(s)}
              aria-pressed={speed === s}
              className={`px-1.5 py-1 font-mono text-[10.5px] transition-colors ${speed === s ? 'bg-accent/15 text-accent' : 'text-fg-4 hover:text-fg-2'}`}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      {/* minimap */}
      <div
        ref={track}
        className="relative h-[46px] min-w-0 flex-1 cursor-pointer overflow-hidden rounded-md border border-line bg-bg-well"
        onPointerDown={(e) => onDown(e, 'seek')}
        onPointerMove={onMove}
        onPointerUp={onUp}
        role="slider"
        aria-label="Replay position"
        aria-valuemin={0}
        aria-valuemax={last?.seq ?? 0}
        aria-valuenow={cursor}
        aria-valuetext={`seq ${cursor} at ${fmtClock(playT - t0)}`}
        tabIndex={0}
      >
        <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="none" viewBox={`0 0 ${BINS} ${LANES.length * 6}`} aria-hidden>
          {density.map((row, li) =>
            row.map((n, bi) =>
              n ? (
                <rect
                  key={`${li}-${bi}`}
                  x={bi}
                  y={li * 6 + 1}
                  width={0.9}
                  height={4}
                  fill={LANE_COLOR[LANES[li]?.id ?? 'meta']}
                  opacity={0.25 + 0.75 * (n / maxD)}
                />
              ) : null,
            ),
          )}
        </svg>
        {/* replayed region */}
        <div className="pointer-events-none absolute inset-y-0 left-0 bg-accent/[0.07]" style={{ width: `${frac(playT) * 100}%` }} />
        {/* finding pins */}
        {bundle.findings.map((f) => (
          <div
            key={f.seq}
            className="pointer-events-none absolute top-0 h-full w-[2px]"
            style={{ left: `${frac(f.ts_mono) * 100}%`, background: SEV_COLOR[f.severity], opacity: f.seq <= cursor ? 0.95 : 0.3, boxShadow: f.seq <= cursor ? `0 0 8px ${SEV_COLOR[f.severity]}` : undefined }}
          />
        ))}
        {/* zoom window */}
        <div
          className="absolute inset-y-0 cursor-grab border-x-2 border-fg-3/60 bg-white/[0.04] active:cursor-grabbing"
          style={{ left: `${vl}%`, width: `${Math.max(0.5, vr - vl)}%` }}
          onPointerDown={(e) => onDown(e, 'pan')}
          title="Visible window — drag to pan"
        >
          <div className="absolute inset-y-0 -left-1.5 w-3 cursor-ew-resize" onPointerDown={(e) => onDown(e, 'l')} />
          <div className="absolute inset-y-0 -right-1.5 w-3 cursor-ew-resize" onPointerDown={(e) => onDown(e, 'r')} />
        </div>
        {/* playhead */}
        <div className="pointer-events-none absolute inset-y-0 w-0" style={{ left: `${frac(playT) * 100}%` }}>
          <div className="absolute inset-y-0 -left-px w-[2px] bg-accent shadow-glow-accent" />
          <div className="absolute -left-[5px] -top-px h-0 w-0 border-x-[5px] border-t-[6px] border-x-transparent" style={{ borderTopColor: C.accent }} />
        </div>
      </div>

      {/* timecode */}
      <div className="shrink-0 text-right">
        <div className="font-mono text-[15px] font-medium tabular-nums text-fg">{fmtClock(playT - t0)}</div>
        <div className="font-mono text-[10.5px] text-fg-4">
          seq <span className="text-fg-2">{cursor}</span> / {last?.seq ?? 0} · {fmtClock(total)}
        </div>
      </div>
    </div>
  );
}

export default Scrubber;
