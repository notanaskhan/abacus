import { Button, Icon, Pill, Tag } from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import {
  ALSO,
  ALSO_TITLE,
  BAR,
  DELIVERED,
  DELIVERY,
  DIALOG,
  DOCK,
  FILES,
  FILING,
  type Frame,
  G7_BLOCKED,
  G8,
  GATES,
  type Gate,
  MET,
  NOT_MET,
  PILL,
  REPORT_DATE,
  TITLE,
  TOAST,
} from "./copy";

// AUD-24 · Issuance & release in fixture mode on T2 (A-07-T38; handoff AUD-24). The last gate
// before the report leaves the firm: G5, G6 and G7 with their live values, what else must hold,
// and G8, recorded only when the engagement partner releases. Release is a person's act behind a
// dialog with the partner's attestation and a step-up (the host runs it); the agent never
// releases or applies a signature, and nothing on this canvas is agent-owned.

export type { Frame } from "./copy";

export interface IssuanceProps {
  frame: Frame;
  /** The viewer is the engagement partner and the server lists `report.release`. */
  canRelease?: boolean;
  /** Opens the step-up and records G8 (the host calls the release route). */
  onRelease?: () => void;
  onOpen?: (target: string) => void;
}

function Disc({ done, half }: { done: boolean; half?: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-disc={done ? "done" : half === true ? "half" : "ring"}
      className={`inline-flex size-[22px] shrink-0 items-center justify-center rounded-full ${done ? "bg-green text-on-dark" : "inset-shadow-hair"}`}
    >
      {done && <Icon name="check" size={13} />}
    </span>
  );
}

function Kv({
  label,
  value,
  onOpen,
}: {
  label: string;
  value: string;
  onOpen?: () => void;
}): JSX.Element {
  return (
    <div className="flex min-h-[30px] items-center justify-between gap-3 px-[14px] text-[12.5px]">
      <span className="text-ink-2">{label}</span>
      {onOpen !== undefined ? (
        <button type="button" className="font-medium hover:underline" onClick={onOpen}>
          {value}
        </button>
      ) : (
        <span className="font-medium">{value}</span>
      )}
    </div>
  );
}

function GateCard({
  gate,
  met,
  onOpen,
}: {
  gate: Gate;
  met: boolean;
  onOpen?: (target: string) => void;
}): JSX.Element {
  return (
    <section
      aria-label={`${gate.gate} ${gate.title}`}
      data-gate={gate.gate}
      data-met={met ? "true" : "false"}
      className="rounded-[12px] bg-card shadow-e1"
    >
      <header className="flex h-[44px] items-center gap-2 px-[14px]">
        <Disc done={met} />
        <Tag>{gate.gate}</Tag>
        <h3 className="text-[14px] font-medium">{gate.title}</h3>
        <span className="ml-auto">
          {met ? <Pill variant="green-tint">{MET}</Pill> : <Pill variant="amber">{NOT_MET}</Pill>}
        </span>
      </header>
      <div className="pb-[6px]">
        {gate.gate === "G7" && !met ? (
          <Kv label="Status" value={G7_BLOCKED} />
        ) : (
          gate.rows.map(([label, value, target]) => (
            <Kv
              key={label}
              label={label}
              value={value}
              {...(onOpen !== undefined
                ? {
                    onOpen: () => {
                      onOpen(target);
                    },
                  }
                : {})}
            />
          ))
        )}
      </div>
    </section>
  );
}

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title}>
      <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
        {title}
      </h3>
      {children}
    </section>
  );
}

function ReleaseDialog({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  const [attested, setAttested] = useState(false);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={DIALOG.title}
      data-sheet="release"
      className="w-[500px] rounded-[12px] bg-card p-[18px] shadow-e3"
    >
      <h2 className="text-[16px] font-medium">{DIALOG.title}</h2>
      <dl className="mt-3 flex flex-col gap-1">
        {DIALOG.rows.map(([label, value]) => (
          <div key={label} className="flex justify-between text-[12.5px]">
            <dt className="text-ink-2">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
      <label className="mt-4 flex items-start gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={attested}
          onChange={(e) => {
            setAttested(e.target.checked);
          }}
        />
        <span>{DIALOG.attest}</span>
      </label>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          {DIALOG.cancel}
        </Button>
        <Button variant="primary" disabled={!attested} onClick={onConfirm}>
          {DIALOG.confirm}
        </Button>
      </div>
    </div>
  );
}

export function Issuance({
  frame,
  canRelease = false,
  onRelease,
  onOpen,
}: IssuanceProps): JSX.Element {
  const blocked = frame === "b";
  const released = frame === "d" || frame === "f";
  const nonPartner = frame === "e" || !canRelease;
  const [dialog, setDialog] = useState(frame === "c");
  const enabled = frame === "a" && canRelease && !dialog;
  const pill = released ? PILL.released : blocked ? PILL.completion : PILL.ready;
  let caption: string = BAR.reserved;
  if (blocked) caption = BAR.blocked;
  else if (frame === "e") caption = BAR.nonPartner;
  return (
    <div data-screen="AUD-24" data-frame={frame} className="flex h-full flex-col bg-shell">
      <div className="flex h-[59px] items-center justify-between px-[16px]">
        <div className="flex items-center gap-2">
          <h1 className="text-[15px] font-medium">{TITLE}</h1>
          <Pill variant={released ? "green" : blocked ? "neutral" : "green-tint"}>{pill}</Pill>
        </div>
        <span className="text-[13px] text-ink-3">{REPORT_DATE}</span>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px]">
        <main aria-label={TITLE} className="flex w-[696px] flex-col">
          <div className="flex flex-1 flex-col gap-[10px] overflow-auto p-[10px]">
            {GATES.map((g) => (
              <GateCard
                key={g.gate}
                gate={g}
                met={!(blocked && g.gate === "G7")}
                {...(onOpen !== undefined ? { onOpen } : {})}
              />
            ))}
            <section aria-label={ALSO_TITLE} className="rounded-[12px] bg-card shadow-e1">
              <h3 className="flex h-[40px] items-center px-[14px] text-[13.5px] font-medium">
                {ALSO_TITLE}
              </h3>
              {ALSO.map(([label, value]) => (
                <div
                  key={label}
                  className="flex min-h-[34px] items-center gap-2 px-[14px] text-[12.5px]"
                >
                  <Icon name="circle-check" size={15} aria-hidden="true" />
                  <span>{label}</span>
                  <span className="ml-auto text-ink-3">{value}</span>
                </div>
              ))}
            </section>
            <section
              aria-label="G8"
              data-gate="G8"
              data-met={released ? "true" : "false"}
              className={`rounded-[12px] p-[14px] ${released ? "bg-card shadow-e1" : "inset-shadow-hair"}`}
            >
              <div className="flex items-center gap-2">
                <Disc done={released} />
                <span className="text-[14px] font-medium">{released ? G8.done : G8.pending}</span>
              </div>
              {released ? (
                <p data-clock="archive" className="mt-2 text-[12.5px] text-ink-2">
                  {G8.clock}
                </p>
              ) : (
                <p className="mt-2 text-[12.5px] text-ink-2">{G8.body}</p>
              )}
            </section>
          </div>
          {!released && (
            <div
              data-bar="release"
              className="flex items-center justify-between bg-card px-[14px] py-[12px] inset-shadow-hair"
            >
              <span className="text-[12.5px] text-ink-2">{BAR.left}</span>
              <div className="flex flex-col items-end">
                <Button
                  variant="primary"
                  icon="send"
                  opensDialog
                  disabled={!enabled}
                  onClick={() => {
                    setDialog(true);
                  }}
                >
                  {BAR.button}
                </Button>
                <span className="mt-1 text-[11px] text-ink-3">
                  {nonPartner && frame === "e" ? BAR.nonPartner : caption}
                </span>
              </div>
            </div>
          )}
          {released && frame === "d" && (
            <div
              role="status"
              data-toast="released"
              className="mx-auto mb-3 rounded-[10px] bg-espresso px-4 py-2 text-[13px] text-on-dark"
            >
              {TOAST}
            </div>
          )}
        </main>
        <aside aria-label={DOCK.title} className="flex w-[330px] flex-col bg-card shadow-e1">
          <h2 className="flex h-[46px] items-center justify-center text-[14px] font-medium">
            {DOCK.title}
          </h2>
          <Band title={DOCK.pack}>
            {FILES.map((f, i) => (
              <div key={f.name} className="flex min-h-[44px] items-center gap-2 px-[14px]">
                <Icon name="file" size={15} aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] font-medium">{f.name}</div>
                  <div className="text-[11.5px] text-ink-3">{f.meta}</div>
                </div>
                {released && i === 0 ? (
                  <Pill variant="green-tint">{DELIVERED}</Pill>
                ) : (
                  <Pill variant={f.tone}>{f.pill}</Pill>
                )}
              </div>
            ))}
          </Band>
          <Band title={DOCK.delivery}>
            {DELIVERY.map(([label, value]) => (
              <Kv key={label} label={label} value={value} />
            ))}
          </Band>
          <Band title={DOCK.filings}>
            <div
              data-filing="form_5500"
              className="m-[10px] rounded-[10px] bg-card p-[12px] shadow-e1"
            >
              <div className="text-[12.5px] font-medium">{FILING.title}</div>
              <div className="mt-1 text-[11.5px] text-ink-3">{FILING.filer}</div>
              <div className="mt-1 text-[11.5px] text-ink-3">{FILING.due}</div>
              <div className="mt-2">
                {frame === "f" ? (
                  <Pill variant="green-tint">{FILING.filed}</Pill>
                ) : (
                  <Pill variant="amber">{FILING.awaiting}</Pill>
                )}
              </div>
            </div>
          </Band>
        </aside>
      </div>
      {dialog && (
        <div className="fixed inset-0 flex items-center justify-center z-(--z-modal) bg-(--scrim)">
          <ReleaseDialog
            onCancel={() => {
              setDialog(false);
            }}
            onConfirm={() => {
              setDialog(false);
              onRelease?.();
            }}
          />
        </div>
      )}
    </div>
  );
}
