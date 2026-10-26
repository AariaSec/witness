/** Small pure formatting helpers. */

export function shortHash(h: string | null | undefined, n = 6): string {
  if (!h) return '—';
  return h.length <= n * 2 + 1 ? h : `${h.slice(0, n)}…${h.slice(-4)}`;
}

/** seconds → "+12.345s" relative clock */
export function fmtRel(sec: number, digits = 3): string {
  const sign = sec < 0 ? '−' : '+';
  return `${sign}${Math.abs(sec).toFixed(digits)}s`;
}

/** seconds → "00:12.345" */
export function fmtClock(sec: number): string {
  const s = Math.max(0, sec);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${String(m).padStart(2, '0')}:${r.toFixed(3).padStart(6, '0')}`;
}

export function fmtMs(ms: number): string {
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 10) return `${ms.toFixed(1)} ms`;
  if (ms < 10_000) return `${Math.round(ms).toLocaleString('en-US')} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function fmtBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function fmtWall(ts: number): string {
  const d = new Date(ts * 1000);
  return `${d.toISOString().replace('T', ' ').slice(0, 23)}Z`;
}

export function fmtPct(r: number | null): string {
  return r === null ? '—' : `${Math.round(r * 100)}%`;
}

export const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));
