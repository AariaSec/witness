/** Colour tokens mirrored from tailwind.config.ts for SVG / inline-computed paint. */
import type { Severity } from '../schema/bundle';
import type { Lane } from './derive';

export const C = {
  bg: '#0a0d14',
  well: '#080b11',
  card: '#111722',
  line: '#1f2836',
  lineStrong: '#2c3749',
  fg: '#F5F8FD',
  fg2: '#C3CCD9',
  fg3: '#8590A2',
  fg4: '#566179',
  fg5: '#3a4458',
  accent: '#FF9F0A',
  ok: '#3ddc97',
  info: '#6f9bff',
  warn: '#f2b23e',
  stop: '#ff5d5d',
} as const;

export const LANE_COLOR: Record<Lane, string> = {
  claim: '#b8a2ff',
  proc: '#7fb4cc',
  fs: '#5fd0b5',
  net: '#ff9f6a',
  witness: '#FF9F0A',
  meta: '#8590A2',
};

export const SEV_COLOR: Record<Severity, string> = { stop: C.stop, warn: C.warn, info: C.info };

export const SEV_CLASSES: Record<Severity, { text: string; bg: string; border: string; glow: string }> = {
  stop: { text: 'text-stop', bg: 'bg-stop/10', border: 'border-stop/50', glow: 'shadow-glow-stop' },
  warn: { text: 'text-warn', bg: 'bg-warn/10', border: 'border-warn/40', glow: 'shadow-glow-warn' },
  info: { text: 'text-info', bg: 'bg-info/10', border: 'border-info/40', glow: 'shadow-glow-info' },
};
