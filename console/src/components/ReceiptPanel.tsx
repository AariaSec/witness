/**
 * ReceiptPanel — the run's signed receipt, verified LIVE in this browser.
 *
 * The Ed25519 check runs client-side (verifyReceipt.ts) against the public
 * key pinned in the manifest. "Tamper test" flips one field of an in-memory
 * copy of the body and re-verifies, so a viewer can watch the signature fail
 * — proof the green state is computed, not decorative.
 */
import { useEffect, useMemo, useState } from 'react';
import type { LoadedBundle } from '../lib/loadBundle';
import { auditReceipt, verifyReceipt, type ReceiptAudit, type SigResult } from '../lib/verifyReceipt';
import { traced } from '../lib/derive';
import { fmtWall, shortHash } from '../lib/format';
import { C } from '../lib/tokens';
import { SeqChip, TraceNumber } from './TraceTooltip';

export interface ReceiptPanelProps {
  bundle: LoadedBundle;
  cursor: number;
}

type Mode = 'real' | 'tampered';

function Seal({ state, scanning }: { state: 'ok' | 'warn' | 'bad' | 'idle'; scanning: boolean }) {
  const color = state === 'ok' ? C.ok : state === 'warn' ? C.warn : state === 'bad' ? C.stop : C.fg4;
  const teeth = 24;
  const pts: string[] = [];
  for (let i = 0; i < teeth * 2; i++) {
    const a = (i / (teeth * 2)) * Math.PI * 2;
    const r = i % 2 ? 42 : 46;
    pts.push(`${50 + r * Math.cos(a)},${50 + r * Math.sin(a)}`);
  }
  return (
    <div className="relative h-[104px] w-[104px] shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full" aria-hidden>
        <polygon points={pts.join(' ')} fill={`${color}14`} stroke={color} strokeOpacity={0.55} strokeWidth={1.2} />
        <circle cx="50" cy="50" r="35" fill={C.card} stroke={color} strokeOpacity={0.8} strokeWidth={1.4} />
        <circle
          cx="50"
          cy="50"
          r="30"
          fill="none"
          stroke={color}
          strokeOpacity={0.5}
          strokeWidth={1}
          strokeDasharray="2 3"
          className={scanning ? 'origin-center animate-[spin_1.2s_linear_infinite]' : ''}
          style={{ transformBox: 'fill-box' }}
        />
        {scanning ? null : state === 'ok' ? (
          <path d="M37 51l9 9l17-19" fill="none" stroke={color} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" className="animate-fade-in" />
        ) : state === 'bad' ? (
          <path d="M39 39l22 22m0-22L39 61" fill="none" stroke={color} strokeWidth={5} strokeLinecap="round" className="animate-fade-in" />
        ) : state === 'warn' ? (
          <path d="M50 36v17m0 9v1" fill="none" stroke={color} strokeWidth={5} strokeLinecap="round" />
        ) : (
          <circle cx="50" cy="50" r="4" fill={color} />
        )}
      </svg>
      {state === 'ok' && !scanning ? <div className="absolute inset-0 rounded-full shadow-glow-ok" aria-hidden /> : null}
      {state === 'bad' && !scanning ? <div className="absolute inset-0 rounded-full shadow-glow-stop" aria-hidden /> : null}
    </div>
  );
}

export function ReceiptPanel({ bundle, cursor }: ReceiptPanelProps) {
  const audit: ReceiptAudit = useMemo(() => auditReceipt(bundle), [bundle]);
  const r = bundle.receipt;
  const revealed = r !== null && cursor >= r.seq;
  const [mode, setMode] = useState<Mode>('real');
  const [scanning, setScanning] = useState(false);
  const [live, setLive] = useState<SigResult | null>(null);

  // Re-run verification on reveal and whenever the mode flips — visibly.
  useEffect(() => {
    if (!r || !revealed) {
      setLive(null);
      return;
    }
    setScanning(true);
    const result =
      mode === 'real'
        ? verifyReceipt(r, bundle.manifest.pubkey, bundle.rawLineBySeq.get(r.seq))
        : verifyReceipt({ ...r, body: { ...r.body, records: r.body.records + 1 } }, bundle.manifest.pubkey, null);
    setLive(result);
    const id = window.setTimeout(() => setScanning(false), 650);
    return () => window.clearTimeout(id);
  }, [r, revealed, mode, bundle]);

  if (!r) {
    return (
      <section className="card p-5" aria-label="Receipt">
        <div className="eyebrow">Receipt</div>
        <div className="mt-3 flex items-center gap-4">
          <Seal state="bad" scanning={false} />
          <div>
            <div className="text-[16px] font-semibold text-stop">No receipt in this bundle</div>
            <p className="mt-1 text-[12.5px] text-fg-3">The run was not sealed. Its records still replay, but nothing binds them to a signing key.</p>
          </div>
        </div>
      </section>
    );
  }

  const sigOk = live?.ok ?? false;
  const bindingsOk = audit.checks.every((c) => c.ok || c.critical);
  const state: 'ok' | 'warn' | 'bad' | 'idle' = !revealed || !live ? 'idle' : !sigOk ? 'bad' : mode === 'real' && !bindingsOk ? 'warn' : 'ok';
  const headline = !revealed
    ? 'Awaiting receipt'
    : scanning
      ? 'Verifying…'
      : state === 'ok'
        ? 'Signature verified'
        : state === 'warn'
          ? 'Signature valid · binding issue'
          : 'Signature INVALID';

  const tally = Object.entries(r.body.findings);
  const findingsT = traced(
    tally.reduce((a, [, n]) => a + n, 0),
    [r.seq, ...bundle.findings.filter((f) => f.seq < r.seq).map((f) => f.seq)],
    'sum of the signed findings tally in the receipt body',
  );
  const recordsT = traced(r.body.records, [r.seq], 'records field of the signed receipt body');

  return (
    <section className="card overflow-hidden" aria-label="Receipt">
      <div className="card-hd">
        <span className="eyebrow">Signed receipt</span>
        <span className="font-mono text-[10.5px] text-fg-4">Ed25519 · verified in this browser · @noble/ed25519</span>
      </div>
      <div className="relative flex items-center gap-5 px-5 py-5">
        {scanning ? (
          <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
            <div className="absolute inset-y-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-accent/10 to-transparent" />
          </div>
        ) : null}
        <Seal state={state} scanning={scanning || !revealed} />
        <div className="min-w-0 flex-1">
          <div
            role="status"
            aria-live="polite"
            className={`text-[19px] font-semibold tracking-[-0.01em] ${
              state === 'ok' ? 'text-ok text-glow-ok' : state === 'bad' ? 'text-stop text-glow-stop' : state === 'warn' ? 'text-warn' : 'text-fg-3'
            }`}
          >
            {headline}
          </div>
          <div className="mt-1 text-[12.5px] text-fg-3">
            {!revealed
              ? `Sealed at seq ${r.seq} when the run ends — scrub forward.`
              : mode === 'tampered'
                ? 'Tamper test: one field (records +1) changed in an in-memory copy. Same signature, same key.'
                : 'Signature over canonical JSON of the receipt body, checked against the key pinned at seq 0.'}
          </div>
          {revealed && live && !scanning ? (
            <div className="mt-2 font-mono text-[11px] text-fg-4">
              {live.ok ? `ok · ${live.encoding === 'lossless' ? 'bytes as recorded' : 'python-repr encoding'} · ${live.ms} ms` : `fail · ${live.reason} · ${live.ms} ms`}
            </div>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <button type="button" className="btn" disabled={!revealed} onClick={() => setMode((m) => (m === 'real' ? 'tampered' : 'real'))}>
            {mode === 'real' ? 'Tamper test' : 'Restore original'}
          </button>
          <span className="font-mono text-[10px] text-fg-5">{mode === 'real' ? 'flip one field, re-verify' : 'showing tampered copy'}</span>
        </div>
      </div>

      {revealed ? (
        <>
          {mode === 'tampered' ? (
            <div className="border-t border-line bg-stop/[0.05] px-5 py-1.5 font-mono text-[10.5px] text-stop/80">
              checks below describe the ORIGINAL file on disk — only the in-memory copy was tampered
            </div>
          ) : null}
          <ul className={`grid grid-cols-1 gap-x-6 border-t border-line px-5 py-3 transition-opacity sm:grid-cols-2 ${mode === 'tampered' ? 'opacity-35' : ''}`}>
            {audit.checks.map((c) => (
              <li key={c.id} className="flex items-start gap-2.5 py-1">
                <span
                  className={`mt-[1px] flex h-4 w-4 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-bold ${c.ok ? 'bg-ok/15 text-ok' : c.critical ? 'bg-stop/15 text-stop' : 'bg-warn/15 text-warn'}`}
                  aria-hidden
                >
                  {c.ok ? '✓' : '✗'}
                </span>
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium text-fg-2">{c.label}</span>
                  <span className="block font-mono text-[10.5px] leading-snug text-fg-4">{c.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          <div className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
            {[
              ['records', <TraceNumber key="r" t={recordsT} title="Signed record count" format={(v) => v} />],
              ['findings', <TraceNumber key="f" t={findingsT} title="Signed findings" format={(v) => v} />],
              ['stop', <span key="s" className={r.body.stop_status === 'failed' ? 'text-stop' : r.body.stop_status === 'ok' ? 'text-ok' : 'text-fg-2'}>{r.body.stop_status}</span>],
              ['signed', <span key="t" className="text-[11px]">{fmtWall(r.body.signed_at).slice(11)}</span>],
            ].map(([k, v]) => (
              <div key={k as string} className="bg-card px-4 py-2.5">
                <div className="eyebrow text-fg-4">{k}</div>
                <div className="mt-1 font-mono text-[15px] font-semibold text-fg">{v}</div>
              </div>
            ))}
          </div>
          <div className="space-y-1 border-t border-line px-5 py-3 font-mono text-[10.5px] text-fg-4">
            <div className="flex items-center gap-2">
              <span className="w-24 shrink-0">final digest</span>
              <span className="truncate text-fg-3" title={r.body.final_digest}>
                {r.body.final_digest}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-24 shrink-0">public key</span>
              <span className="truncate text-fg-3">{r.body.pubkey}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-24 shrink-0">signature</span>
              <span className="truncate text-fg-3">{shortHash(r.sig, 20)}</span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="w-24 shrink-0">tally</span>
              {tally.map(([k, n]) => (
                <span key={k} className="chip">
                  {k} <span className="text-fg">{n}</span>
                </span>
              ))}
              <span className="ml-auto flex items-center gap-1.5">
                sealed at <SeqChip seq={r.seq} />
              </span>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

export default ReceiptPanel;
