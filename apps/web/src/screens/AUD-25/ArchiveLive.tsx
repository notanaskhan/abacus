// AUD-25 on the server's data (A-07-T47; A-07 F7): the AU-C 230 clock, the nine computed checklist
// items, the binder index and the lock from `GET …/archive` (polled every 10 s by the host's
// `useLiveArchive`, every 2 s while the lock runs). No artboard words: labels are the screen's,
// values the server's. "Lock archive…" shows only with the server's `archive.lock` and opens the
// sheet's "Assembly is complete" attestation; the seal and G9 are ArchiveLockWorkflow's. No delete
// control anywhere after lock, and nothing here is agent-owned.

import type { AuditArchiveStateOut } from "@abacus/api-client";
import { Button, Checkbox, DEFAULT_TZ, Dialog, Icon, dateTime } from "@abacus/ui";
import { type JSX, useState } from "react";
import { governanceWords } from "../../domain/completion-live";
// The live screen's own words (never the artboard copy, which carries the handoff's sample data
// and must stay out of a production build: dist.test's ac10).
const TITLE = "Assembly & archive";
const LOCK = "Lock archive…";
const CHECKLIST_TITLE = "Archive checklist";
const BINDER_TITLE = "Binder index";
const SHEET = {
  title: "Lock the archive",
  body: "Contents become read-only and are sealed with a SHA-256 hash",
  attest: "Assembly is complete",
  roll: "Then roll forward to PY2026 (ENG-13)",
  cancel: "Cancel",
  confirm: "Lock archive",
} as const;

export interface ArchiveLiveProps {
  archive: AuditArchiveStateOut;
  /** DV-6: the governance letters' required count (`GET …/governance`). */
  governance?: { sent: number; total: number } | undefined;
  /** Locking: the decision is recorded and ArchiveLockWorkflow seals (the host polls). */
  running?: boolean;
  problem?: string | null;
  tz?: string;
  thenRollForward?: boolean;
  onThenRollForward?: (on: boolean) => void;
  onLock?: () => void;
  onBack?: () => void;
}

/** "Archive in N days" (red only at 7 days or fewer, AUD-25 e). */
export function clockWords(daysLeft: number | null): string | null {
  if (daysLeft === null) return null;
  return `Archive in ${String(daysLeft)} ${daysLeft === 1 ? "day" : "days"}`;
}

export function ArchiveLive(props: ArchiveLiveProps): JSX.Element {
  const { archive } = props;
  const tz = props.tz ?? DEFAULT_TZ;
  const [open, setOpen] = useState(false);
  const [attested, setAttested] = useState(false);
  const locked = archive.status === "locked";
  const canLock = archive.allowed_actions.includes("archive.lock") && props.onLock !== undefined;
  const ready = archive.checklist_done === archive.checklist_total;
  const clock = clockWords(archive.days_left);
  const atRisk = archive.days_left !== null && archive.days_left <= 7;
  return (
    <div data-screen="AUD-25" data-live="true" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center gap-2 px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
        <h2 className="flex-1 text-[15px] font-medium">{TITLE}</h2>
        {locked ? (
          <span data-locked="true" className="text-[13px]">
            Locked {dateTime(archive.locked_at ?? "", { tz })} · {archive.locked_by_name ?? ""}
            {archive.seal_sha256 !== null &&
              ` · seal ${archive.seal_sha256.slice(0, 4)}…${archive.seal_sha256.slice(-4)}`}
          </span>
        ) : (
          <>
            {clock !== null && (
              <span
                data-clock={atRisk ? "risk" : "ok"}
                className={`rounded-pill px-[8px] text-[12px] ${atRisk ? "bg-red-tint text-red-ink" : ""}`}
              >
                {clock}
              </span>
            )}
            {canLock && (
              <Button
                size="sm"
                disabled={!ready || props.running === true}
                onClick={() => {
                  setAttested(false);
                  setOpen(true);
                }}
              >
                {props.running === true ? "Locking…" : LOCK}
              </Button>
            )}
          </>
        )}
      </div>
      {props.problem != null && (
        <p
          role="alert"
          className="mx-[12px] mb-2 rounded-pane bg-red-tint px-[12px] py-2 text-[13px]"
        >
          {props.problem}
        </p>
      )}
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label={CHECKLIST_TITLE}
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            {CHECKLIST_TITLE} · {archive.checklist_done} of {archive.checklist_total}
          </h3>
          <ul>
            {archive.checklist.map((i) => (
              <li
                key={i.key}
                data-item={i.key}
                data-done={i.done ? "true" : "false"}
                className="flex min-h-[36px] items-center gap-2 px-[12px] text-[13px]"
              >
                <Icon name={i.done ? "circle-check" : "circle"} size={13} />
                <span className="flex-1">{i.title}</span>
                {i.detail !== null && <span className="text-ink-3">{i.detail}</span>}
              </li>
            ))}
            {props.governance === undefined || props.governance.total === 0 ? null : (
              <li
                data-governance="true"
                className="flex min-h-[36px] items-center gap-2 px-[12px] text-[13px] text-ink-2"
              >
                {governanceWords(props.governance)}
              </li>
            )}
          </ul>
        </section>
        <section
          aria-label={BINDER_TITLE}
          className="min-w-0 flex-1 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
            {BINDER_TITLE}
          </h3>
          <ul>
            {archive.binder.map((b) => (
              <li
                key={b.section}
                data-section={b.section}
                className="flex min-h-[32px] items-center gap-2 px-[12px] text-[13px]"
              >
                <span className="w-[20px] font-medium">{b.section}</span>
                <span className="flex-1">{b.title}</span>
                <span className="text-ink-3">
                  {b.workpapers + b.source_documents + b.run_logs}
                </span>
              </li>
            ))}
          </ul>
          {archive.retention_until !== null && (
            <p className="px-[12px] py-2 text-[12px] text-ink-3">
              Retention until {archive.retention_until}
            </p>
          )}
        </section>
      </div>
      <Dialog open={open} onOpenChange={setOpen} title={SHEET.title} description={SHEET.body}>
        <Checkbox label={SHEET.attest} showLabel checked={attested} onChange={setAttested} />
        {props.onThenRollForward !== undefined && (
          <Checkbox
            label={SHEET.roll}
            showLabel
            checked={props.thenRollForward === true}
            onChange={props.onThenRollForward}
          />
        )}
        <div className="mt-3 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
            }}
          >
            {SHEET.cancel}
          </Button>
          <Button
            disabled={!attested}
            onClick={() => {
              setOpen(false);
              props.onLock?.();
            }}
          >
            {SHEET.confirm}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
