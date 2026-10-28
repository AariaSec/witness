/**
 * ConfidenceGauge — the analyst report's `confidence` field as a liquid-fill
 * instrument.
 *
 * The ONLY input is `report.confidence` (a schema float 0..1 written by the
 * analyst pass). The fill level is that value — nothing else moves the
 * liquid. The wave and the settle-overshoot are physics on the way TO that
 * value (a damped spring), never a second data source; once settled the
 * surface rests at exactly `confidence` and the waves only ripple around it.
 *
 * The whole instrument is wrapped in <TraceNumber>, so hovering it shows the
 * provenance popover (report seq + field) like every other number here.
 *
 * Colour: the analyst is advisory (it never affects pass/fail), so a live
 * model reading is drawn in the `info` hue. An offline template / schema-fail
 * report carries a fixed fallback value, not a model judgment — it is drawn
 * in neutral grey and labelled as such, so a template constant can never be
 * mistaken for a model's confidence on camera.
 */
import { useEffect, useId, useRef } from 'react';
import type { Report } from '../schema/bundle';
import type { Traced } from '../lib/derive';
import { C } from '../lib/tokens';
import { TraceNumber } from './TraceTooltip';

const VB = 200;
const CX = 100;
const CY = 100;
/** liquid / glass radius */
const R = 82;
/** surface y for a given level 0..1 (top of the glass at level 1) */
const surfaceY = (level: number) => CY + R - level * 2 * R;

type Tone = { top: string; bottom: string; back: string; glow: string; rim: string };

const TONES: Record<'model' | 'template', Tone> = {
  model: { top: '#7da5ff', bottom: '#1f3a9e', back: '#6f9bff', glow: C.info, rim: '#6f9bff' },
  template: { top: '#8590A2', bottom: '#3a4458', back: '#566179', glow: '#566179', rim: '#566179' },
};

const reducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/**
 * Closed path: a sine surface across the glass at `y0`, filled down past the
 * bottom of the glass. Sampled every 4 units — smooth at any size we draw.
 */
function wavePath(y0: number, amp: number, wavelength: number, phase: number, closed: boolean): string {
  const x0 = CX - R - 6;
  const x1 = CX + R + 6;
  const k = (2 * Math.PI) / wavelength;
  let d = '';
  for (let x = x0; x <= x1 + 0.001; x += 4) {
    const y = y0 + amp * Math.sin(k * x + phase);
    d += `${d ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  if (closed) d += `L${x1} ${VB + 20}L${x0} ${VB + 20}Z`;
  return d;
}

interface LiquidProps {
  value: number;
  /** false → empty glass (report not yet reached by the replay cursor) */
  filled: boolean;
  tone: Tone;
  size: number;
}

/** The SVG instrument. Animates via refs (no React re-render per frame). */
function Liquid({ value, filled, tone, size }: LiquidProps) {
  const uid = useId().replace(/:/g, '');
  const front = useRef<SVGPathElement>(null);
  const back = useRef<SVGPathElement>(null);
  const crest = useRef<SVGPathElement>(null);
  const clip = useRef<SVGPathElement>(null);
  const label = useRef<SVGTextElement>(null);
  const labelIn = useRef<SVGTextElement>(null);

  const target = filled ? Math.min(1, Math.max(0, value)) : 0;
  const state = useRef({ level: 0, vel: 0, phase: 0, shown: 0 });

  useEffect(() => {
    const s = state.current;
    const paint = () => {
      const y = surfaceY(s.level);
      // slosh: amplitude grows with how fast the surface is still moving,
      // and relaxes to a gentle resting ripple once settled at `target`.
      const amp = s.level <= 0.001 ? 0 : 3.2 + Math.min(9, Math.abs(s.vel) * 14);
      const fd = wavePath(y, amp, 96, s.phase, true);
      front.current?.setAttribute('d', fd);
      clip.current?.setAttribute('d', fd);
      back.current?.setAttribute('d', wavePath(y - 2.5, amp * 0.85, 128, -s.phase * 0.8 + 1.7, true));
      crest.current?.setAttribute('d', wavePath(y, amp, 96, s.phase, false));
      const txt = `${Math.round(s.shown * 100)}`;
      if (label.current) label.current.textContent = txt;
      if (labelIn.current) labelIn.current.textContent = txt;
    };

    if (reducedMotion() || typeof requestAnimationFrame === 'undefined') {
      s.level = target;
      s.shown = target;
      s.vel = 0;
      paint();
      return;
    }

    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      // under-damped spring toward the recorded value → a real overshoot-and-settle
      // ω ≈ 2.2 rad/s, ζ ≈ 0.7 → a ~2.5 s pour with a small (<5% of the step) slosh past the mark
      const kSpring = 4.84;
      const damp = 3.1;
      const acc = -kSpring * (s.level - target) - damp * s.vel;
      s.vel += acc * dt;
      s.level += s.vel * dt;
      if (s.level < 0) {
        s.level = 0;
        s.vel = 0;
      }
      // the printed number tracks the surface but never passes the field value
      // (the slosh is shown by the liquid, never by the number)
      s.shown = target >= s.shown ? Math.max(s.shown, Math.min(s.level, target)) : Math.min(s.shown, Math.max(s.level, target));
      if (Math.abs(target - s.shown) < 0.004) s.shown = target;
      s.phase += dt * 2.1;
      paint();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  const ticks = [0.25, 0.5, 0.75];
  const g = (n: string) => `${n}-${uid}`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${VB} ${VB}`} aria-hidden className="block overflow-visible">
      <defs>
        <clipPath id={g('glass')}>
          <circle cx={CX} cy={CY} r={R} />
        </clipPath>
        <clipPath id={g('liq')}>
          <path ref={clip} />
        </clipPath>
        <linearGradient id={g('front')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={tone.top} stopOpacity="0.95" />
          <stop offset="1" stopColor={tone.bottom} stopOpacity="0.98" />
        </linearGradient>
        <radialGradient id={g('well')} cx="0.5" cy="0.38" r="0.7">
          <stop offset="0" stopColor="#141b28" />
          <stop offset="1" stopColor="#06080d" />
        </radialGradient>
        <linearGradient id={g('bezel')} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3a4458" />
          <stop offset="0.5" stopColor="#1f2836" />
          <stop offset="1" stopColor="#2c3749" />
        </linearGradient>
        <radialGradient id={g('vol')} cx="0.5" cy="0.42" r="0.58">
          <stop offset="0.62" stopColor="#000000" stopOpacity="0" />
          <stop offset="1" stopColor="#000000" stopOpacity="0.42" />
        </radialGradient>
        <radialGradient id={g('spec')} cx="0.32" cy="0.2" r="0.55">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.16" />
          <stop offset="0.6" stopColor="#ffffff" stopOpacity="0.02" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <filter id={g('glow')} x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>

      {/* halo behind the glass, tinted by the liquid, scaled by the level */}
      <circle cx={CX} cy={CY} r={R + 4} fill={tone.glow} opacity={filled ? 0.1 + 0.18 * target : 0} filter={`url(#${g('glow')})`} style={{ transition: 'opacity 900ms ease' }} />

      {/* bezel */}
      <circle cx={CX} cy={CY} r={R + 9} fill="none" stroke={`url(#${g('bezel')})`} strokeWidth="5" />
      <circle cx={CX} cy={CY} r={R + 9} fill="none" stroke={tone.rim} strokeOpacity={filled ? 0.35 : 0.12} strokeWidth="1" />
      <circle cx={CX} cy={CY} r={R + 3} fill="none" stroke="#0a0d14" strokeWidth="4" />

      {/* glass well */}
      <circle cx={CX} cy={CY} r={R} fill={`url(#${g('well')})`} />

      <g clipPath={`url(#${g('glass')})`}>
        {/* level graduations — the scale the liquid is read against */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={CX - R} x2={CX - R + 14} y1={surfaceY(t)} y2={surfaceY(t)} stroke="#3a4458" strokeWidth="1" />
            <line x1={CX + R - 14} x2={CX + R} y1={surfaceY(t)} y2={surfaceY(t)} stroke="#3a4458" strokeWidth="1" />
          </g>
        ))}
        <path ref={back} fill={tone.back} opacity="0.32" />
        <path ref={front} fill={`url(#${g('front')})`} />
        <path ref={crest} fill="none" stroke="#dce7ff" strokeOpacity="0.8" strokeWidth="1.4" />
      </g>

      {/* the number: drawn twice — light above the surface, dark inside the liquid */}
      <g fontFamily='"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, monospace' textAnchor="middle">
        <text x={CX} y={CY + 14} fontSize="52" fontWeight="700" letterSpacing="-2" fill={C.fg}>
          <tspan ref={label} />
          <tspan fontSize="22" fontWeight="600" dx="2" fill={C.fg3}>
            %
          </tspan>
        </text>
        <g clipPath={`url(#${g('liq')})`}>
          <g clipPath={`url(#${g('glass')})`}>
            <text x={CX} y={CY + 14} fontSize="52" fontWeight="700" letterSpacing="-2" fill="#06080d">
              <tspan ref={labelIn} />
              <tspan fontSize="22" fontWeight="600" dx="2" fill="#06080d" fillOpacity="0.7">
                %
              </tspan>
            </text>
          </g>
        </g>
        <text x={CX} y={CY + 36} fontSize="9" fontWeight="600" letterSpacing="2.4" fill={C.fg3} opacity="0.9" style={{ mixBlendMode: 'screen' }}>
          CONFIDENCE
        </text>
      </g>

      {/* glass: spherical volume shading, specular sheen, inner edge */}
      <circle cx={CX} cy={CY} r={R} fill={`url(#${g('vol')})`} pointerEvents="none" />
      <circle cx={CX} cy={CY} r={R} fill={`url(#${g('spec')})`} pointerEvents="none" />
      <path
        d={`M ${CX - R * 0.72} ${CY - R * 0.36} A ${R * 0.8} ${R * 0.8} 0 0 1 ${CX - R * 0.1} ${CY - R * 0.79}`}
        fill="none"
        stroke="#ffffff"
        strokeOpacity="0.18"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx={CX} cy={CY} r={R} fill="none" stroke="#ffffff" strokeOpacity="0.07" strokeWidth="1" />
    </svg>
  );
}

export interface ConfidenceGaugeProps {
  report: Report;
  /** report.confidence as a Traced (seq-provenanced) value */
  t: Traced<number>;
  /** has the replay cursor reached the report record? */
  shown: boolean;
  size?: number;
}

export function ConfidenceGauge({ report, t, shown, size = 176 }: ConfidenceGaugeProps) {
  const model = report.analyst_status === 'ok';
  const tone = TONES[model ? 'model' : 'template'];
  return (
    <figure className="flex shrink-0 flex-col items-center" aria-label={`Analyst confidence ${shown ? t.value.toFixed(2) : 'not yet reached'}`}>
      <TraceNumber
        t={t}
        title={model ? 'Analyst confidence (model output)' : 'Fallback template confidence (no model judgment)'}
        className="inline-block rounded-full !no-underline"
        format={(v) => <Liquid value={v} filled={shown} tone={tone} size={size} />}
      />
      <figcaption className="mt-2 flex flex-col items-center gap-1 text-center">
        <span
          className={`rounded-sm border px-1.5 py-[2px] font-mono text-[9.5px] font-bold tracking-[0.12em] ${
            model ? 'border-info/40 bg-info/10 text-info' : 'border-fg-4/50 bg-white/[0.03] text-fg-3'
          }`}
        >
          {model ? 'LIVE MODEL READING' : report.analyst_status === 'offline' ? 'TEMPLATE CONSTANT' : 'SCHEMA-FAIL FALLBACK'}
        </span>
        <span className="font-mono text-[10px] text-fg-4">
          {shown ? `confidence = ${t.value.toFixed(2)} · seq #${report.seq}` : 'scrub to the report record'}
        </span>
      </figcaption>
    </figure>
  );
}

export default ConfidenceGauge;
