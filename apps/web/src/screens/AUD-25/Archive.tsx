import { AgentText, Button, Icon, Pill } from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import {
  ADDITIONS,
  BINDER,
  BINDER_HEAD,
  BINDER_TITLE,
  CHECKLIST,
  CHECKLIST_TITLE,
  CLOCK,
  DOCK,
  type Frame,
  GOVERNANCE_DONE,
  LOCK,
  LOCKED_LINE,
  PILL,
  RELEASED,
  REQUEST_LOCK,
  REQUEST_TIP,
  ROLL,
  SHEET,
  TITLE,
} from "./copy";

// AUD-25 · Assembly & archive in fixture mode on T2 (A-07-T39; handoff AUD-25 and revision R2).
// The 60-day assembly clock (red tint only at 7 days or fewer), the nine computed checklist items
// (none can be ticked by hand), the binder index, the person's lock behind "Assembly is complete",
// the sealed state (DF-20) and additions after the lock. Locking is a manager's or the partner's
// act; the agent only built the index and narrates. Nothing here deletes, before or after the lock.

export type { Frame } from "./copy";

export interface ArchiveProps {
  frame: Frame;
  /** The viewer may lock (manager or EP; the server's `archive.lock`). */
  canLock?: boolean;
  onRequestLock?: () => void;
  /** Opens the step-up and posts the lock with the attestation (the host). */
  onLock?: (thenRollForward: boolean) => void;
  onRollForward?: () => void;
  onAddAfterLock?: () => void;
  onOpen?: (target: string) => void;
}

function Disc({ done }: { done: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-disc={done ? "done" : "ring"}
      className={`inline-flex size-[15px] shrink-0 items-center justify-center rounded-full ${done ? "bg-green text-on-dark" : "inset-shadow-hair"}`}
    >
      {done && <Icon name="check" size={12} />}
    </span>
  );
}

function Card({
  title,
  right,
  children,
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <section aria-label={title} className="rounded-[12px] bg-card shadow-e1">
      {title !== undefined && (
        <header className="flex h-[40px] items-center justify-between px-[14px]">
          <h3 className="text-[13.5px] font-medium">{title}</h3>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

function LockSheet({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: (roll: boolean) => void;
}): JSX.Element {
  const [complete, setComplete] = useState(false);
  const [roll, setRoll] = useState(false);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={SHEET.title}
      data-sheet="lock"
      className="w-[500px] rounded-[12px] bg-card p-[18px] shadow-e3"
    >
      <h2 className="text-[16px] font-medium">{SHEET.title}</h2>
      <p className="mt-2 text-[12.5px] text-ink-2">{SHEET.body}</p>
      <label className="mt-4 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={complete}
          onChange={(e) => {
            setComplete(e.target.checked);
          }}
        />
        <span>{SHEET.attest}</span>
      </label>
      <label className="mt-2 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={roll}
          onChange={(e) => {
            setRoll(e.target.checked);
          }}
        />
        <span>{SHEET.roll}</span>
      </label>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          {SHEET.cancel}
        </Button>
        <Button
          variant="primary"
          disabled={!complete}
          onClick={() => {
            onConfirm(roll);
          }}
        >
          {SHEET.confirm}
        </Button>
      </div>
    </div>
  );
}

export function Archive({
  frame,
  canLock = false,
  onRequestLock,
  onLock,
  onRollForward,
  onAddAfterLock,
  onOpen,
}: ArchiveProps): JSX.Element {
  const locked = frame === "c" || frame === "d";
  const ready = frame === "b" || frame === "b2";
  const risk = frame === "e";
  const [sheet, setSheet] = useState(frame === "b2");
  const done = locked || ready ? 9 : 8;
  let pill: ReactNode = (
    <Pill variant="muted" lead={<Icon name="clock" size={12} aria-hidden="true" />}>
      {PILL.days}
    </Pill>
  );
  if (risk) pill = <Pill variant="red-tint">{PILL.risk}</Pill>;
  if (locked)
    pill = (
      <Pill variant="soon" lead={<Icon name="lock" size={12} aria-hidden="true" />}>
        {PILL.locked}
      </Pill>
    );
  return (
    <div data-screen="AUD-25" data-frame={frame} className="flex h-full flex-col bg-shell">
      <div className="flex h-[59px] items-center justify-between px-[16px]">
        <div className="flex items-center gap-2">
          <h1 className="text-[15px] font-medium">{TITLE}</h1>
          {pill}
        </div>
        <span className="text-[13px] text-ink-3">{RELEASED}</span>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px]">
        <main aria-label={TITLE} className="flex w-[696px] flex-col">
          <div className="flex h-[46px] items-center justify-between px-[14px]">
            <h2 className="text-[14px] font-medium">{TITLE}</h2>
            <div className="flex items-center gap-2">
              {locked ? (
                <Button variant="secondary" icon="copy-plus" opensDialog onClick={onRollForward}>
                  {ROLL.roll}
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  icon="copy-plus"
                  opensDialog
                  disabled={!ready || !canLock}
                  title={ready ? undefined : ROLL.tip}
                  onClick={() => {
                    setSheet(true);
                  }}
                >
                  {ROLL.archiveAndRoll}
                </Button>
              )}
              {!locked && ready && canLock && (
                <Button
                  variant="primary"
                  icon="lock"
                  opensDialog
                  onClick={() => {
                    setSheet(true);
                  }}
                >
                  {LOCK}
                </Button>
              )}
              {!locked && !(ready && canLock) && (
                <Button
                  variant="primary"
                  icon="lock"
                  opensDialog
                  disabled={!ready}
                  title={ready ? undefined : REQUEST_TIP}
                  onClick={onRequestLock}
                >
                  {REQUEST_LOCK}
                </Button>
              )}
            </div>
          </div>
          <div className="flex flex-1 flex-col gap-[10px] overflow-auto p-[10px]">
            <Card>
              {locked ? (
                <p data-locked="true" className="p-[14px] text-[13px] font-medium">
                  {LOCKED_LINE}
                </p>
              ) : (
                <div
                  data-clock="archive"
                  data-risk={risk ? "true" : "false"}
                  className="px-[16px] py-[14px]"
                >
                  <div className="flex gap-6">
                    <div>
                      <div className={`text-[22px] tabular-nums ${risk ? "text-red-ink" : ""}`}>
                        {risk ? CLOCK.riskDays : CLOCK.days}
                      </div>
                      <div className="text-[12.5px] text-ink-2">{CLOCK.until}</div>
                    </div>
                    <dl className="flex-1">
                      {CLOCK.rows.map(([label, value]) => (
                        <div
                          key={label}
                          className="flex min-h-[28px] items-center justify-between text-[12.5px]"
                        >
                          <dt className="text-ink-2">{label}</dt>
                          <dd className="font-medium">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                  <div
                    role="progressbar"
                    aria-valuenow={CLOCK.elapsedPct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={CLOCK.elapsed}
                    className="mt-3 h-[3px] rounded-full bg-surface-deep"
                  >
                    <div
                      className="h-full rounded-full bg-espresso"
                      style={{ width: `${String(CLOCK.elapsedPct)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[11.5px] text-ink-3">{CLOCK.elapsed}</div>
                </div>
              )}
            </Card>
            <Card
              title={CHECKLIST_TITLE}
              right={<Pill variant="neutral">{`${String(done)} of 9`}</Pill>}
            >
              <ul data-readonly={locked ? "true" : "false"}>
                {CHECKLIST.map((item) => {
                  const open = item.open === true && !(locked || ready);
                  const evidence = item.open === true && !open ? GOVERNANCE_DONE : item.evidence;
                  return (
                    <li
                      key={item.title}
                      data-item-done={open ? "false" : "true"}
                      className="flex min-h-[40px] items-center gap-2 px-[14px]"
                    >
                      <Disc done={!open} />
                      <div className="min-w-0 flex-1">
                        <div className="text-[12.5px]">{item.title}</div>
                        <div className={`text-[11.5px] ${open ? "text-amber-ink" : "text-ink-3"}`}>
                          {evidence}
                        </div>
                      </div>
                      {item.chip !== undefined && (
                        <button
                          type="button"
                          className="rounded-[6px] px-2 text-[11px] text-ink-2 inset-shadow-hair"
                          onClick={() => onOpen?.(item.chip ?? "")}
                        >
                          {item.chip}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Card>
            <Card title={BINDER_TITLE}>
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="h-[30px] text-left text-ink-3">
                    {BINDER_HEAD.map((h) => (
                      <th key={h} className="px-[14px] font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {BINDER.map(([section, contents, items]) => (
                    <tr
                      key={section}
                      className={`h-[32px] ${section === "Total workpapers" ? "font-medium inset-shadow-hair" : ""}`}
                    >
                      <td className="px-[14px]">{section}</td>
                      <td className="px-[14px] text-ink-2">{contents}</td>
                      <td className="px-[14px] text-right tabular-nums">{items}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
            <Card
              title={ADDITIONS.title}
              right={
                locked ? (
                  <Button variant="secondary" opensDialog onClick={onAddAfterLock}>
                    {ADDITIONS.add}
                  </Button>
                ) : undefined
              }
            >
              {frame === "d" ? (
                <div
                  data-addition="pi-02"
                  className="flex items-center gap-2 px-[14px] py-[10px] text-[12.5px]"
                >
                  <Pill variant="amber">{ADDITIONS.pill}</Pill>
                  <span>{ADDITIONS.row}</span>
                </div>
              ) : (
                <div className="px-[14px] pb-[14px]">
                  <div className="text-[12.5px] font-medium">{ADDITIONS.empty}</div>
                  <div className="text-[12.5px] text-ink-3">{ADDITIONS.emptyBody}</div>
                </div>
              )}
            </Card>
          </div>
        </main>
        <aside aria-label={DOCK.title} className="flex w-[330px] flex-col bg-card shadow-e1">
          <h2 className="flex h-[46px] items-center justify-center text-[14px] font-medium">
            {DOCK.title}
          </h2>
          <div className="flex flex-col gap-2 p-[10px]">
            <div className="rounded-[10px] px-3 py-2 text-[12px] inset-shadow-hair">
              {DOCK.run}
            </div>
            <AgentText
              text={locked ? DOCK.lockedNarration : DOCK.narration}
              className="text-[12.5px]"
            />
            {DOCK.tools.map((t) => (
              <div key={t} className="flex items-center gap-2 text-[12px]">
                <Disc done />
                <span>{t}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
      {sheet && !locked && (
        <div className="fixed inset-0 z-(--z-modal) flex items-center justify-center bg-(--scrim)">
          <LockSheet
            onCancel={() => {
              setSheet(false);
            }}
            onConfirm={(roll) => {
              setSheet(false);
              onLock?.(roll);
            }}
          />
        </div>
      )}
    </div>
  );
}
