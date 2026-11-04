import { createContext, useContext } from 'react';
import type { LoadedBundle } from './loadBundle';

/** Cross-component navigation: any seq chip can jump the timeline to a record. */
export interface Nav {
  bundle: LoadedBundle;
  /** select + reveal a record (moves the playhead forward if needed) */
  jump: (seq: number) => void;
  selected: number | null;
  /** replay cursor (inclusive seq) */
  cursor: number;
  hoverSeqs: readonly number[];
  setHoverSeqs: (s: readonly number[]) => void;
}

export const NavContext = createContext<Nav | null>(null);

export function useNav(): Nav {
  const n = useContext(NavContext);
  if (!n) throw new Error('NavContext missing');
  return n;
}
