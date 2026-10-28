/**
 * witness · evidence console
 *
 * Static, client-side only. Loads one bundle.jsonl (drag-drop, file picker,
 * same-origin ?bundle= path, or the bundled demo) and replays it. Nothing is
 * uploaded; the only network request is fetching a same-origin bundle file.
 */
import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
} from "react";
import {
  BundleLoadError,
  ISSUE_TEXT,
  fetchBundle,
  readBundleFile,
  type LoadedBundle,
} from "./lib/loadBundle";
import { auditReceipt } from "./lib/verifyReceipt";
import { seqAtTime } from "./lib/derive";
import { NavContext, type Nav } from "./lib/nav";
import { clamp, shortHash } from "./lib/format";
import { Hero } from "./components/Hero";
import { Timeline } from "./components/Timeline";
import { FindingCard } from "./components/FindingCard";
import { ClaimDiff } from "./components/ClaimDiff";
import { DivergenceFlow } from "./components/DivergenceFlow";
import { ReceiptPanel } from "./components/ReceiptPanel";
import { ReportPanel } from "./components/ReportPanel";
import { DriftPanel } from "./components/DriftPanel";
import { Scrubber } from "./components/Scrubber";

// three.js is ~600 KB — split into its own same-origin chunk (CSP script-src 'self' still holds)
const BlastRadiusScene = lazy(() => import("./components/BlastRadiusScene"));

const DEMO_URL = "bundles/demo.jsonl";

/** Only same-origin relative paths ending in .jsonl — never an arbitrary URL. */
export function safeBundlePath(p: string | null): string | null {
  if (!p) return null;
  if (
    !/^[A-Za-z0-9._\-/]+\.jsonl$/.test(p) ||
    p.includes("..") ||
    p.startsWith("/") ||
    p.startsWith("//")
  )
    return null;
  return p;
}

function fullView(b: LoadedBundle): [number, number] {
  const pad = Math.max(0.2, (b.span.t1 - b.span.t0) * 0.03);
  return [b.span.t0 - pad, b.span.t1 + pad];
}

/* -------------------------------------------------------------- chrome */

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#111722" stroke="#2c3749" />
        <circle
          cx="16"
          cy="16"
          r="8.5"
          fill="none"
          stroke="#FF9F0A"
          strokeWidth="2.2"
        />
        <circle cx="16" cy="16" r="2.6" fill="#FF9F0A" />
        <path
          d="M4 16h4M24 16h4"
          stroke="#FF9F0A"
          strokeWidth="1.6"
          strokeLinecap="round"
          opacity="0.6"
        />
      </svg>
      <div className="leading-none">
        <div className="text-[16px] font-semibold tracking-[-0.02em] text-fg">
          witness
        </div>
        <div className="mt-0.5 font-mono text-[9.5px] uppercase tracking-[0.18em] text-fg-4">
          evidence console
        </div>
      </div>
    </div>
  );
}

function Heartbeat({ alive }: { alive: boolean }) {
  return (
    <span
      className="relative flex h-2.5 w-2.5"
      aria-label={alive ? "replaying" : "idle"}
    >
      {alive ? (
        <span className="absolute inset-0 animate-pulse-ring rounded-full bg-accent" />
      ) : null}
      <span
        className={`relative h-2.5 w-2.5 rounded-full ${alive ? "bg-accent" : "bg-fg-5"}`}
      />
    </span>
  );
}

function StatusChip({
  tone,
  label,
  value,
  title,
}: {
  tone: "ok" | "warn" | "stop" | "muted";
  label: string;
  value: string;
  title?: string;
}) {
  const cls = {
    ok: "border-ok/35 bg-ok/[0.07] text-ok",
    warn: "border-warn/35 bg-warn/[0.07] text-warn",
    stop: "border-stop/45 bg-stop/[0.08] text-stop",
    muted: "border-line-strong bg-card-raised text-fg-3",
  }[tone];
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] ${cls}`}
    >
      <span className="text-[9.5px] font-semibold uppercase tracking-[0.14em] opacity-80">
        {label}
      </span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

function IssuesChip({ b }: { b: LoadedBundle }) {
  const [open, setOpen] = useState(false);
  const errors = b.issues.filter((i) => i.level === "error").length;
  const warns = b.issues.length - errors;
  if (!b.issues.length)
    return (
      <StatusChip
        tone="ok"
        label="integrity"
        value="clean"
        title="No structural issues found while loading"
      />
    );
  return (
    <span className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <StatusChip
          tone={errors ? "stop" : "warn"}
          label="integrity"
          value={`${errors ? `${errors} err` : ""}${errors && warns ? " · " : ""}${warns ? `${warns} warn` : ""}`}
        />
      </button>
      {open ? (
        <div className="absolute right-0 top-9 z-50 w-[380px] animate-pop-in rounded-lg border border-line-strong bg-[#0d121c]/95 p-3 shadow-card backdrop-blur-md">
          <div className="eyebrow mb-2">Load issues — bundle still replays</div>
          <ul className="max-h-72 space-y-1 overflow-y-auto">
            {b.issues.map((i, k) => (
              <li key={k} className="flex gap-2 font-mono text-[11px]">
                <span
                  className={i.level === "error" ? "text-stop" : "text-warn"}
                >
                  {i.level}
                </span>
                <span className="text-fg-2">{ISSUE_TEXT[i.code]}</span>
                <span className="ml-auto shrink-0 text-fg-4">
                  {i.seq !== undefined
                    ? `#${i.seq}`
                    : i.line !== undefined
                      ? `L${i.line}`
                      : ""}
                  {i.key ? ` ${i.key}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </span>
  );
}

/* --------------------------------------------------------------- landing */

function Landing({
  onPick,
  error,
  loading,
}: {
  onPick: () => void;
  error: string | null;
  loading: boolean;
}) {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-2xl flex-col items-center justify-center px-6 text-center">
      <div className="mb-6 scale-150">
        <Logo />
      </div>
      <h1 className="mt-6 text-[34px] font-semibold leading-tight tracking-[-0.03em] text-fg">
        Did the agent do what it said it did?
      </h1>
      <p className="mt-3 max-w-xl text-[15px] text-fg-3">
        Drop a witness <span className="font-mono text-fg-2">bundle.jsonl</span>{" "}
        to replay an AI coding-agent session against independently recorded
        telemetry. Parsed in this tab — nothing is uploaded.
      </p>
      {error ? (
        <div className="mt-6 rounded-md border border-stop/40 bg-stop/10 px-4 py-2.5 text-[13px] text-stop">
          {error}
        </div>
      ) : null}
      <div className="mt-8 flex gap-3">
        <button
          type="button"
          className="btn-accent"
          onClick={onPick}
          disabled={loading}
        >
          {loading ? "Loading…" : "Open bundle.jsonl"}
        </button>
      </div>
      <div className="mt-10 w-full rounded-xl border border-dashed border-line-strong bg-card/40 px-6 py-10 font-mono text-[12px] text-fg-4">
        drop a .jsonl file anywhere on this page
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- app */

export default function App() {
  const [bundle, setBundle] = useState<LoadedBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [shareMode, setShareMode] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const [playT, setPlayT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [view, setView] = useState<[number, number]>([0, 1]);
  const [selected, setSelected] = useState<number | null>(null);
  const [focusFinding, setFocusFinding] = useState<number | null>(null);
  const [hoverSeqs, setHoverSeqs] = useState<readonly number[]>([]);
  /**
   * Two-tab split so the first screen is a short, glanceable story rather
   * than one long scroll past every panel. Both tabs stay mounted (CSS
   * `hidden`, not unmount) so replay state, hover wiring, and `jump()`'s
   * `#timeline` scroll target are never lost switching between them.
   */
  const [tab, setTab] = useState<"overview" | "evidence">("overview");

  const adopt = useCallback(
    (b: LoadedBundle, replay: boolean, atSeq: number | null = null) => {
      setBundle(b);
      setError(null);
      document.documentElement.dataset.simulated =
        b.manifest.simulated === false ? "false" : "true";
      setView(fullView(b));
      setSelected(null);
      const stop =
        b.findings.find((f) => f.severity === "stop") ?? b.findings[0];
      setFocusFinding(stop ? stop.seq : null);
      const at = atSeq !== null ? b.bySeq.get(atSeq) : undefined;
      if (at) {
        // deep link: ?seq=N — playhead parked on that record, record selected
        setPlayT(at.ts_mono);
        setPlaying(false);
        setSelected(at.seq);
        if (at.kind === "finding") setFocusFinding(at.seq);
      } else if (replay) {
        setPlayT(b.span.t0);
        setPlaying(true);
      } else {
        setPlayT(b.span.t1);
        setPlaying(false);
      }
    },
    [],
  );

  const fail = useCallback((e: unknown) => {
    document.documentElement.dataset.simulated = "unknown";
    setError(
      e instanceof BundleLoadError
        ? e.message
        : "Could not read this file as a witness bundle.",
    );
  }, []);

  // initial load: ?bundle= (same-origin path) or the bundled demo
  useEffect(() => {
    const qs = new URLSearchParams(window.location.search);
    const path = safeBundlePath(qs.get("bundle")) ?? DEMO_URL;
    const replay = qs.get("replay") === "1";
    const seqParam = qs.get("seq");
    const atSeq =
      seqParam !== null && /^\d+$/.test(seqParam) ? Number(seqParam) : null;
    const sp = Number(qs.get("speed"));
    if ([0.5, 1, 2, 4, 8].includes(sp)) setSpeed(sp);
    setShareMode(qs.get("view") === "share");
    fetchBundle(path)
      .then((b) => adopt(b, replay, atSeq))
      .catch((e) => {
        // A missing demo is not an error worth shouting about — show the landing.
        if (path !== DEMO_URL) fail(e);
      })
      .finally(() => setLoading(false));
  }, [adopt, fail]);

  const openFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      setLoading(true);
      try {
        adopt(await readBundleFile(file), false);
      } catch (e) {
        fail(e);
      } finally {
        setLoading(false);
      }
    },
    [adopt, fail],
  );

  // replay clock — the only rAF loop driving narrative state
  useEffect(() => {
    if (!playing || !bundle) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      setPlayT((t) => {
        // compress dead air: race through gaps > 1.5s between records
        const next = bundle.records.find((r) => r.ts_mono > t);
        const gap = next ? next.ts_mono - t : 0;
        const nt = t + dt * speed * (gap > 1.5 ? 6 : 1);
        if (nt >= bundle.span.t1) {
          setPlaying(false);
          return bundle.span.t1;
        }
        return nt;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, bundle, speed]);

  const cursor = useMemo(
    () => (bundle ? seqAtTime(bundle, playT) : -1),
    [bundle, playT],
  );

  // keep the playhead inside the zoom window while replaying
  useEffect(() => {
    if (!playing) return;
    setView((v) => {
      const s = v[1] - v[0];
      if (playT > v[1] - s * 0.08) return [playT - s * 0.25, playT + s * 0.75];
      if (playT < v[0]) return [playT - s * 0.1, playT + s * 0.9];
      return v;
    });
  }, [playT, playing]);

  // focus newly fired stop findings during replay
  useEffect(() => {
    if (!bundle || !playing) return;
    const latest = [...bundle.findings].reverse().find((f) => f.seq <= cursor);
    if (latest) setFocusFinding(latest.seq);
  }, [cursor, bundle, playing]);

  const jump = useCallback(
    (seq: number) => {
      if (!bundle) return;
      const r = bundle.bySeq.get(seq);
      if (!r) return;
      setPlaying(false);
      if (seq > cursor) setPlayT(r.ts_mono);
      setSelected(seq);
      if (r.kind === "finding") setFocusFinding(seq);
      setView((v) => {
        const s = v[1] - v[0];
        return r.ts_mono < v[0] || r.ts_mono > v[1]
          ? [r.ts_mono - s / 2, r.ts_mono + s / 2]
          : v;
      });
      setTab("evidence");
      // Deferred one frame: switching tabs un-hides #timeline via a React
      // re-render, which hasn't painted yet in this same tick.
      requestAnimationFrame(() => {
        document
          .getElementById("timeline")
          ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    },
    [bundle, cursor],
  );

  const step = useCallback(
    (dir: -1 | 1) => {
      if (!bundle) return;
      setPlaying(false);
      const base = selected ?? cursor;
      const idx = bundle.records.findIndex((r) => r.seq === base);
      const nr = bundle.records[clamp(idx + dir, 0, bundle.records.length - 1)];
      if (!nr) return;
      if (nr.seq > cursor) setPlayT(nr.ts_mono);
      setSelected(nr.seq);
    },
    [bundle, cursor, selected],
  );

  const restart = useCallback(() => {
    if (!bundle) return;
    setSelected(null);
    setPlayT(bundle.span.t0);
    setView((v) => {
      const s = v[1] - v[0];
      return [bundle.span.t0 - s * 0.05, bundle.span.t0 + s * 0.95];
    });
    setPlaying(true);
  }, [bundle]);

  const togglePlay = useCallback(() => {
    if (!bundle) return;
    if (!playing && playT >= bundle.span.t1) return restart();
    setPlaying((p) => !p);
  }, [bundle, playing, playT, restart]);

  // keyboard
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (!bundle) return;
      if (e.key === " ") {
        e.preventDefault();
        togglePlay();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        step(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        step(-1);
      } else if (e.key === "Home") restart();
      else if (e.key === "End") {
        setPlaying(false);
        setPlayT(bundle.span.t1);
      } else if (e.key === "f") {
        const nf =
          bundle.findings.find((f) => f.seq > (selected ?? -1)) ??
          bundle.findings[0];
        if (nf) jump(nf.seq);
      } else if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bundle, togglePlay, step, restart, jump, selected]);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    void openFile(e.dataTransfer.files[0]);
  };

  const audit = useMemo(() => (bundle ? auditReceipt(bundle) : null), [bundle]);

  const nav: Nav | null = useMemo(
    () =>
      bundle
        ? { bundle, jump, selected, cursor, hoverSeqs, setHoverSeqs }
        : null,
    [bundle, jump, selected, cursor, hoverSeqs],
  );

  const picker = (
    <input
      ref={fileInput}
      type="file"
      accept=".jsonl,application/jsonl,application/x-ndjson,text/plain"
      className="hidden"
      onChange={(e) => {
        void openFile(e.target.files?.[0]);
        e.target.value = "";
      }}
    />
  );

  const dropHandlers = {
    onDragOver: (e: DragEvent) => {
      e.preventDefault();
      setDragging(true);
    },
    onDragLeave: (e: DragEvent) => {
      if (e.currentTarget === e.target) setDragging(false);
    },
    onDrop,
  };

  const dropOverlay = dragging ? (
    <div className="pointer-events-none fixed inset-0 z-[90] flex items-center justify-center bg-bg/80 backdrop-blur-sm">
      <div className="rounded-2xl border-2 border-dashed border-accent/70 bg-card/80 px-12 py-10 text-center shadow-glow-accent">
        <div className="text-[20px] font-semibold text-fg">
          Drop bundle.jsonl
        </div>
        <div className="mt-1 font-mono text-[12px] text-fg-3">
          parsed locally · nothing is uploaded
        </div>
      </div>
    </div>
  ) : null;

  if (!bundle || !nav || !audit) {
    return (
      <div {...dropHandlers} className="min-h-[calc(100vh-30px)]">
        {picker}
        {dropOverlay}
        <Landing
          onPick={() => fileInput.current?.click()}
          error={error}
          loading={loading}
        />
      </div>
    );
  }

  if (shareMode) {
    return (
      <NavContext.Provider value={nav}>
        <div className="min-h-screen bg-bg-deep px-8 py-10">
          <div className="mx-auto max-w-[900px]">
            <div className="mb-6 flex items-center gap-3">
              <Logo />
              <span className="font-mono text-[12px] text-fg-4">
                The agent's report. The recorder's record. They disagree.
              </span>
            </div>
            <ClaimDiff bundle={bundle} cursor={cursor} />
            <div className="mt-4 text-center font-mono text-[10.5px] text-fg-5">
              aariasec.github.io/witness — content-free, independently recorded,
              every number traces to a seq
            </div>
          </div>
        </div>
      </NavContext.Provider>
    );
  }

  const m = bundle.manifest;
  const findingsShown = bundle.findings.filter((f) => f.seq <= cursor);
  const sigTone =
    audit.verdict === "verified"
      ? "ok"
      : audit.verdict === "signature_only"
        ? "warn"
        : "stop";
  const sigText = {
    verified: "verified",
    signature_only: "sig ok · binding ✗",
    invalid: "INVALID",
    absent: "absent",
  }[audit.verdict];

  return (
    <NavContext.Provider value={nav}>
      <div {...dropHandlers} className="min-h-[calc(100vh-30px)] pb-[96px]">
        {picker}
        {dropOverlay}

        {/* header */}
        <header className="sticky top-[30px] z-40 border-b border-line bg-bg/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-canvas flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3">
            <Logo />
            <span className="hidden h-6 w-px bg-line md:block" />
            <div className="flex min-w-0 items-center gap-3">
              <Heartbeat alive={playing} />
              <div className="min-w-0 leading-tight">
                <div className="truncate font-mono text-[13px] text-fg">
                  <span className="text-fg-4">run </span>
                  {m.run_id}
                </div>
                <div className="font-mono text-[10.5px] text-fg-4">
                  {m.platform} · witness {m.witness_version} · schema{" "}
                  {bundle.schema.version} · ports {m.marker_port}/{m.sink_port}
                  {m.degraded.length ? (
                    <span className="text-warn">
                      {" "}
                      · degraded: {m.degraded.join(", ")}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {m.simulated ? (
                <StatusChip
                  tone="warn"
                  label="mode"
                  value="simulated"
                  title="manifest.simulated = true"
                />
              ) : (
                <StatusChip tone="muted" label="mode" value="recorded" />
              )}
              <StatusChip
                tone={sigTone}
                label="receipt"
                value={sigText}
                title="Ed25519 verified in this browser"
              />
              <StatusChip
                tone={bundle.chain.ok ? "ok" : "stop"}
                label="chain"
                value={
                  bundle.chain.ok
                    ? `${bundle.chain.links} links`
                    : `broken @${bundle.chain.firstBadSeq}`
                }
                title="prev → digest linkage across every record"
              />
              <IssuesChip b={bundle} />
              <button
                type="button"
                className="btn ml-1"
                onClick={() => fileInput.current?.click()}
              >
                Open bundle
              </button>
            </div>
          </div>
          {!bundle.chain.ok || audit.verdict === "invalid" ? (
            <div className="border-t border-stop/40 bg-stop/10 px-6 py-1.5 text-center font-mono text-[11.5px] text-stop">
              {audit.verdict === "invalid"
                ? "RECEIPT SIGNATURE DOES NOT VERIFY"
                : "HASH CHAIN BROKEN"}{" "}
              — the bundle still replays, but its integrity is not established.
            </div>
          ) : null}
          {error ? (
            <div className="border-t border-stop/40 bg-stop/10 px-6 py-1.5 text-center font-mono text-[11.5px] text-stop">
              {error}
            </div>
          ) : null}
        </header>

        <main className="mx-auto max-w-canvas space-y-5 px-6 pt-5">
          <Hero bundle={bundle} cursor={cursor} />

          <nav
            className="flex gap-1.5 border-b border-line pb-2"
            aria-label="Section"
          >
            <button
              type="button"
              className={tab === "overview" ? "btn-accent" : "btn"}
              aria-current={tab === "overview" ? "page" : undefined}
              onClick={() => setTab("overview")}
            >
              Overview
            </button>
            <button
              type="button"
              className={tab === "evidence" ? "btn-accent" : "btn"}
              aria-current={tab === "evidence" ? "page" : undefined}
              onClick={() => setTab("evidence")}
            >
              Full evidence
            </button>
            <span className="ml-2 self-center font-mono text-[10.5px] text-fg-4">
              {tab === "overview"
                ? "what happened, at a glance"
                : "timeline, claims, receipt, analyst, drift"}
            </span>
          </nav>

          <div className={tab === "evidence" ? "space-y-5" : "hidden"}>
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_410px]">
              <div id="timeline" className="min-w-0 scroll-mt-28">
                <Timeline
                  bundle={bundle}
                  cursor={cursor}
                  playT={playT}
                  selected={selected}
                  onSelect={setSelected}
                  view={view}
                  onView={setView}
                  hoverSeqs={hoverSeqs}
                  focusFinding={focusFinding}
                  onFocusFinding={setFocusFinding}
                  following={playing}
                />
              </div>
              <aside className="min-w-0 space-y-3" aria-label="Findings">
                <div className="flex items-baseline justify-between px-1">
                  <span className="eyebrow">Findings</span>
                  <span className="font-mono text-[10.5px] text-fg-4">
                    {findingsShown.length} of {bundle.findings.length} · hover
                    to trace · click to expand
                  </span>
                </div>
                {findingsShown.length === 0 ? (
                  <div className="card px-5 py-8 text-center text-[13px] text-fg-4">
                    No findings yet at seq {cursor}.
                  </div>
                ) : (
                  [...findingsShown]
                    .sort(
                      (a, b) =>
                        ({ stop: 0, warn: 1, info: 2 })[a.severity] -
                          { stop: 0, warn: 1, info: 2 }[b.severity] ||
                        a.seq - b.seq,
                    )
                    .map((f) => (
                      <FindingCard
                        key={f.seq}
                        bundle={bundle}
                        finding={f}
                        cursor={cursor}
                        defaultOpen={f.severity === "stop"}
                        focused={focusFinding === f.seq}
                        onFocus={setFocusFinding}
                      />
                    ))
                )}
              </aside>
            </div>

            <ClaimDiff bundle={bundle} cursor={cursor} />

            <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,1fr)]">
              <ReceiptPanel bundle={bundle} cursor={cursor} />
              <ReportPanel bundle={bundle} cursor={cursor} />
              <DriftPanel bundle={bundle} cursor={cursor} />
            </div>
          </div>

          <div className={tab === "overview" ? "space-y-5" : "hidden"}>
            <DivergenceFlow bundle={bundle} cursor={cursor} />

            <Suspense
              fallback={
                <section
                  className="card h-[640px] animate-pulse"
                  aria-label="Blast radius loading"
                />
              }
            >
              <BlastRadiusScene bundle={bundle} cursor={cursor} />
            </Suspense>
          </div>

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line pb-4 pt-4 font-mono text-[10.5px] text-fg-4">
            <span>
              {bundle.sourceName} · {bundle.records.length} records ·{" "}
              {(bundle.bytes / 1024).toFixed(1)} KB · policy{" "}
              {shortHash(m.policy_hash, 4)} · key {m.pubkey.slice(0, 10)}…
            </span>
            <span>
              Every number traces to a seq — hover it. Metadata only: no prompt,
              response or file content exists in a bundle.
            </span>
          </footer>
        </main>

        {/* transport + lower third */}
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg/90 backdrop-blur-md">
          <div className="mx-auto max-w-canvas px-6 py-2.5">
            <Scrubber
              bundle={bundle}
              playT={playT}
              cursor={cursor}
              playing={playing}
              speed={speed}
              view={view}
              onSeekTime={(t) => {
                setPlaying(false);
                setPlayT(t);
              }}
              onTogglePlay={togglePlay}
              onRestart={restart}
              onStep={step}
              onSpeed={setSpeed}
              onView={setView}
            />
          </div>
          {m.simulated ? (
            <div className="border-t border-line-faint bg-bg-deep/80 py-1 text-center font-mono text-[10px] uppercase tracking-[0.18em] text-accent/80">
              Simulated reconstruction · our machine · decoy key, decoy values
              only
            </div>
          ) : null}
        </div>
      </div>
    </NavContext.Provider>
  );
}
