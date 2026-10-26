/**
 * Hero — the three-second read: what the agent said, what witness recorded,
 * and what the policy did about it. Built ONLY from derived, traced numbers
 * and schema fields — the sentences are fixed console templates, never text
 * from the bundle.
 */
import type { AssistantClaim } from '../schema/bundle';
import type { LoadedBundle } from '../lib/loadBundle';
import {
  claimAudit,
  findingCounts,
  medianTimeToDetect,
  stopSummary,
  traced,
  type Traced,
} from '../lib/derive';
import { fmtMs, fmtPct } from '../lib/format';
import { C, LANE_COLOR, SEV_COLOR } from '../lib/tokens';
import { TraceNumber } from './TraceTooltip';
import { Tween } from './Tween';

export interface HeroProps {
  bundle: LoadedBundle;
  cursor: number;
}

interface Fact {
  key: string;
  t: Traced;
  text: (n: number) => string;
  alarm: boolean;
}

function Kpi({
  label,
  children,
  sub,
  tone = 'fg',
}: {
  label: string;
  children: React.ReactNode;
  sub?: React.ReactNode;
  tone?: 'fg' | 'ok' | 'stop' | 'warn';
}) {
  const glow = tone === 'stop' ? 'text-glow-stop text-stop' : tone === 'ok' ? 'text-ok' : tone === 'warn' ? 'text-warn' : 'text-fg';
  return (
    <div className="group relative overflow-hidden rounded-xl border border-line bg-card/70 px-4 pb-3.5 pt-3 transition-colors hover:border-line-strong">
      <div className="eyebrow text-fg-4">{label}</div>
      <div className={`mt-2 font-mono text-[34px] font-semibold leading-none tracking-[-0.03em] tabular-nums ${glow}`}>{children}</div>
      {sub ? <div className="mt-2 text-[11.5px] text-fg-3">{sub}</div> : null}
    </div>
  );
}

export function Hero({ bundle, cursor }: HeroProps) {
  const fc = findingCounts(bundle, cursor);
  const ttd = medianTimeToDetect(bundle, cursor);
  const stop = stopSummary(bundle, cursor);
  const audit = claimAudit(bundle, cursor);

  // What the agent said: its final structured summary if it emitted one.
  const claims = bundle.byKind.assistant_claim.filter((c) => c.seq <= cursor);
  const finalClaim: AssistantClaim | undefined =
    [...claims].reverse().find((c) => c.source === 'json_output') ?? claims[claims.length - 1];

  // What witness recorded.
  const rs = bundle.records.filter((r) => r.seq <= cursor);
  const writes = rs.filter((r) => r.kind === 'fs_event' && !r.path.startsWith('.session/') && r.op !== 'write_denied');
  const writePaths = new Set(writes.map((r) => (r.kind === 'fs_event' ? r.path : '')));
  const markerReads = rs.filter((r) => r.kind === 'marker_read');
  const leaks = rs.filter((r) => r.kind === 'outbound_post' && r.contains_marker);
  const posts = rs.filter((r) => r.kind === 'outbound_post' && !r.contains_marker);
  const protectedW = rs.filter((r) => r.kind === 'fs_event' && r.protected);
  const escapes = rs.filter((r) => r.kind === 'proc_event' && r.op === 'escape');

  const allFacts: Fact[] = [
    {
      key: 'w',
      t: traced(writePaths.size, writes.map((r) => r.seq), 'distinct lab paths with a recorded create/modify/delete/move'),
      text: (n) => `${n} file${n === 1 ? '' : 's'} changed`,
      alarm: false,
    },
    {
      key: 'm',
      t: traced(markerReads.length, markerReads.map((r) => r.seq), 'marker_read records (decoy key fetched)'),
      text: (n) => `decoy key read${n > 1 ? ` ×${n}` : ''}`,
      alarm: true,
    },
    {
      key: 'l',
      t: traced(leaks.length, leaks.map((r) => r.seq), 'outbound_post records with contains_marker=true'),
      text: (n) => `decoy value POSTed${n > 1 ? ` ×${n}` : ''}`,
      alarm: true,
    },
    {
      key: 'p',
      t: traced(posts.length, posts.map((r) => r.seq), 'outbound_post records without the decoy value'),
      text: (n) => `${n} other POST${n === 1 ? '' : 's'} to sink`,
      alarm: false,
    },
    {
      key: 'x',
      t: traced(protectedW.length, protectedW.map((r) => r.seq), 'fs_event records on protected paths'),
      text: (n) => `${n} protected write${n === 1 ? '' : 's'}`,
      alarm: true,
    },
    {
      key: 'e',
      t: traced(escapes.length, escapes.map((r) => r.seq), 'proc_event records with op=escape'),
      text: (n) => `${n} pgroup escape${n === 1 ? '' : 's'}`,
      alarm: true,
    },
  ];
  const facts = allFacts.filter((f) => f.t.value > 0 || f.key === 'w');

  const said = finalClaim
    ? (() => {
        const subj = [...finalClaim.claimed_paths, ...finalClaim.claimed_hosts];
        const verb = { read: 'read', write: 'wrote', edit: 'edited', shell: 'ran commands', http: 'contacted', search: 'searched', other: 'acted' }[finalClaim.tool];
        return {
          t: traced(finalClaim.claimed_count ?? subj.length, [finalClaim.seq], `claimed_count of agent claim seq ${finalClaim.seq}`),
          verb,
          subj,
          count: finalClaim.claimed_count,
        };
      })()
    : null;

  const ended = bundle.runEnd !== null && cursor >= bundle.runEnd.seq;
  const tone: 'stop' | 'warn' | 'ok' = fc.bySeverity.stop.value ? 'stop' : fc.bySeverity.warn.value ? 'warn' : 'ok';

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]" aria-label="Run verdict">
      <div className="card relative overflow-hidden px-6 py-5">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full opacity-50 blur-3xl"
          style={{ background: tone === 'stop' ? `${C.stop}33` : tone === 'warn' ? `${C.warn}26` : `${C.ok}22` }}
          aria-hidden
        />
        <div className="relative">
          <div className="flex items-center gap-2">
            <span className="eyebrow text-accent">Verdict</span>
            <span className="font-mono text-[10.5px] text-fg-4">as of seq {cursor} · deterministic · no model in the loop</span>
          </div>

          <div className="mt-4 grid grid-cols-[88px_minmax(0,1fr)] items-baseline gap-x-4 gap-y-3">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rotate-45 rounded-[2px]" style={{ background: LANE_COLOR.claim }} />
              <span className="eyebrow" style={{ color: LANE_COLOR.claim }}>
                Said
              </span>
            </div>
            <div className="text-[24px] font-medium leading-tight tracking-[-0.02em] text-fg-2">
              {said ? (
                <>
                  {said.verb} <span className="text-fg">{said.subj.length ? said.subj.join(', ') : '—'}</span>
                  {said.count !== null ? (
                    <>
                      {' '}
                      <span className="text-fg-4">·</span>{' '}
                      <TraceNumber t={said.t} title="Claimed count" format={(v) => <span className="text-fg">{v}</span>} /> file{said.count === 1 ? '' : 's'}
                    </>
                  ) : null}
                </>
              ) : (
                <span className="text-fg-4">no narration recorded yet</span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-accent" />
              <span className="eyebrow text-accent">Did</span>
            </div>
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[24px] font-medium leading-tight tracking-[-0.02em]">
              {facts.map((f, i) => (
                <span key={f.key} className={`animate-fade-in ${f.alarm ? 'text-stop text-glow-stop' : 'text-fg'}`}>
                  <TraceNumber t={f.t} title={f.text(f.t.value)} format={(n) => f.text(n)} />
                  {i < facts.length - 1 ? <span className="text-fg-5">,</span> : null}
                </span>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-sm" style={{ background: stop.status === 'failed' ? C.stop : stop.status === 'ok' ? C.ok : C.fg4 }} />
              <span className="eyebrow text-fg-3">Then</span>
            </div>
            <div className="text-[17px] leading-snug text-fg-2">
              {stop.status === 'ok' ? (
                <>
                  <span className="font-semibold text-ok">Run stopped</span>{' '}
                  <TraceNumber t={stop.evidenceToStop} title="Evidence → stopped" format={(v) => <span className="font-mono text-fg">{v === null ? '—' : fmtMs(v)}</span>} /> after the first
                  evidence — policy action took{' '}
                  <TraceNumber t={stop.latency} title="Stop action latency" format={(v) => <span className="font-mono text-fg">{v === null ? '—' : fmtMs(v)}</span>} />.
                </>
              ) : stop.status === 'failed' ? (
                <span className="font-semibold text-stop">STOP FAILED — the process group did not die. Shown honestly.</span>
              ) : stop.status === 'pending' ? (
                <span className="text-warn">A stop-severity finding fired; stop action not yet recorded.</span>
              ) : (
                <span className="text-fg-3">
                  {ended ? `No stop was needed${audit.verdict === 'agree' ? ' — narration matches the record.' : '.'}` : 'Recording — no stop so far.'}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Kpi
          label="Findings"
          tone={tone === 'ok' ? 'fg' : tone}
          sub={
            <span className="flex items-center gap-3">
              {(['stop', 'warn', 'info'] as const).map((s) => (
                <span key={s} className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEV_COLOR[s] }} />
                  <TraceNumber t={fc.bySeverity[s]} title={`${s} findings`} format={(v) => <span className="font-mono text-fg-2">{v}</span>} />
                  <span className="text-fg-4">{s}</span>
                </span>
              ))}
            </span>
          }
        >
          <TraceNumber t={fc.total} title="Findings" format={(v) => <Tween value={v} format={(x) => String(Math.round(x))} />} />
        </Kpi>
        <Kpi label="Time to detect" sub="median, first evidence → finding · drift excluded">
          <TraceNumber t={ttd} title="Median time to detect" format={(v) => (v === null ? '—' : <Tween value={v} format={(x) => fmtMs(x)} />)} />
        </Kpi>
        <Kpi
          label="Evidence → stopped"
          tone={stop.status === 'failed' ? 'stop' : stop.status === 'ok' ? 'ok' : 'fg'}
          sub={stop.status === 'ok' ? `stop_pgroup ${stop.action?.detail ?? ''} · ok` : stop.status === 'failed' ? 'stop action FAILED' : stop.status === 'pending' ? 'stop pending' : ended ? 'no stop needed' : 'none so far'}
        >
          <TraceNumber t={stop.evidenceToStop} title="Evidence → stopped" format={(v) => (v === null ? '—' : <Tween value={v} format={(x) => fmtMs(x)} />)} />
        </Kpi>
        <Kpi
          label="Said = did"
          tone={audit.agreement.value === null ? 'fg' : audit.agreement.value >= 0.999 ? 'ok' : 'warn'}
          sub={
            <span>
              <TraceNumber t={audit.unclaimedCount} title="Never mentioned" format={(v) => <span className="font-mono text-stop">{v}</span>} /> acts never mentioned ·{' '}
              <TraceNumber t={audit.contradicted} title="Contradicted" format={(v) => <span className="font-mono text-warn">{v}</span>} /> contradicted
            </span>
          }
        >
          <TraceNumber t={audit.agreement} title="Agreement rate" format={(v) => (v === null ? '—' : <Tween value={v} format={(x) => fmtPct(x)} />)} />
        </Kpi>
      </div>
    </section>
  );
}

export default Hero;
