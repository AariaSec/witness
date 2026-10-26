/**
 * Fixed English for every enum the console renders.
 *
 * The analyst report carries ONLY enum codes (never free text). Codes the
 * console does not know are shown verbatim as a mono code chip — never
 * paraphrased, never "interpreted" into prose.
 */
import type { ActionKind, FindingKind, Kind, Severity } from '../schema/bundle';

export const REPORT_CODE_TEXT: Record<string, string> = {
  EXFIL_VIA_SINK: 'Decoy value was posted to the decoy sink',
  MARKER_READ: 'The decoy key was read from the marker service',
  DECOY_KEY_READ: 'The decoy key was read from the marker service',
  OUTBOUND_POST: 'An outbound POST reached the decoy sink',
  OUTBOUND_WITH_MARKER: 'An outbound POST carried the decoy value',
  CLAIM_MISMATCH: "The agent's narration does not match the record",
  MISMATCH: "The agent's narration does not match the record",
  UNCLAIMED_WRITE: 'A file was written that the agent never mentioned',
  UNCLAIMED_NETWORK: 'Network activity the agent never mentioned',
  UNCLAIMED_PROCESS: 'A process was spawned that the agent never mentioned',
  CLAIM_UNOBSERVED: 'The agent claimed an action that was not recorded',
  COUNT_MISMATCH: 'Claimed count differs from the recorded count',
  PROTECTED_WRITE: 'A protected path was written',
  PGROUP_ESCAPE: 'A process left the observed process group',
  RUN_STOPPED: 'The run was stopped by policy',
  STOP_FAILED: 'The stop action failed',
  TOKEN_CLOSED: 'The decoy key endpoint was closed',
  DRIFT_ELEVATED: 'Session shape drifted from baseline (experimental)',
  BENIGN: 'No suspicious activity recorded',
  NO_FINDINGS: 'No findings',
  CLAIMS_CORROBORATED: 'Narrated actions are corroborated by the record',
  RECEIPT_SIGNED: 'A signed receipt closes the run',
  CLOCK_JUMP: 'Wall clock jumped during the run (ordering by seq)',
  TAILER_GAP: 'Session-log tailing skipped bytes',
  DEGRADED_SENSOR: 'A sensor ran in degraded mode',
};

export function reportCodeText(code: string): string | null {
  return REPORT_CODE_TEXT[code] ?? null;
}

export const FINDING_TITLE: Record<FindingKind, string> = {
  marker_read: 'Decoy key read',
  outbound_post: 'Outbound POST to decoy sink',
  mismatch: 'Reported ≠ recorded',
  protected_write: 'Protected path written',
  pgroup_escape: 'Process-group escape',
  drift: 'Behavioural drift',
};

export const FINDING_BLURB: Record<FindingKind, string> = {
  marker_read: 'A process under observation fetched the decoy key from the loopback marker service.',
  outbound_post: 'A process POSTed data to the loopback decoy sink. Body digested and discarded.',
  mismatch: "The agent's own narration disagrees with independently recorded telemetry.",
  protected_write: 'A write landed on a path the manifest marks as protected.',
  pgroup_escape: 'A process left the observed process group while still touching the lab.',
  drift: 'Session shape deviates from the benign baseline. Experimental — not a corroborated signal.',
};

export const SEVERITY_LABEL: Record<Severity, string> = { stop: 'STOP', warn: 'WARN', info: 'INFO' };

export const ACTION_LABEL: Record<ActionKind, string> = {
  close_marker: 'Close decoy endpoint',
  stop_pgroup: 'Stop process group',
  sign_receipt: 'Sign receipt',
};

export const KIND_LABEL: Record<Kind, string> = {
  manifest: 'manifest',
  marker_read: 'marker read',
  outbound_post: 'outbound post',
  fs_event: 'file',
  proc_event: 'process',
  assistant_claim: 'agent claim',
  tail_meta: 'tailer',
  finding: 'finding',
  action_result: 'action',
  clock_warning: 'clock',
  run_end: 'run end',
  receipt: 'receipt',
  report: 'report',
};

export const RUN_END_TEXT: Record<string, string> = {
  assistant_exit: 'agent exited',
  stopped: 'stopped by policy',
  interrupted: 'interrupted',
  timeout: 'timed out',
  ledger_error: 'ledger error (fail-closed)',
};
