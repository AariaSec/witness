import { useTween } from '../lib/useTween';

/** Animated display of an already-traced number (wrap inside TraceNumber's format). */
export function Tween({ value, format }: { value: number; format: (v: number) => string }) {
  const v = useTween(value);
  return <>{format(v)}</>;
}
