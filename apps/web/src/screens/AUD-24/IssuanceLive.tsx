// AUD-24 on the server's data (A-07-T47; A-07 F6): G5 to G7 and the also-required rows from
// `GET …/release` (polled every 10 s by the host's `useLiveRelease`), and G8 once the engagement
// partner releases. No artboard words: the gate titles are the screen's labels, every value the
// server's. "Release report…" shows only with the server's `report.release` and opens the one
// checkbox the design names; the step-up is the server's (a stale second factor opens the shell's
// step-up). Nothing here is agent-owned.

import type { AuditReleaseOut } from "@abacus/api-client";
import { Button, Checkbox, DEFAULT_TZ, Dialog, Icon, dateTime } from "@abacus/ui";
import { type JSX, useState } from "react";
// The live screen's own words (never the artboard copy, which carries the handoff's sample data
// and must stay out of a production build: dist.test's ac10).
const TITLE = "Issuance & release";
const MET = "✓ Met";
const NOT_MET = "Not met";
const GATE_TITLE: Readonly<Record<string, string>> = {
  G5: "Reviewed",
  G6: "EQR concurred",
  G7: "Represented",
};
const DIALOG = {
  title: "Release report",
  attest: "I am the engagement partner and I authorize release of this report",
  cancel: "Cancel",
  confirm: "Release report",
} as const;

const ALSO_LABEL: Readonly<Record<string, string>> = {
  fs_approved: "Final FS approved by management",
  bring_down: "Bring-down through the report date",
  independence: "Independence reconfirmed",
  final_materiality: "Final materiality",
  governance_260: "AU-C 260 completion communication",
};

export interface IssuanceLiveProps {
  release: AuditReleaseOut;
  /** Releasing: the grant is issued and ReleaseWorkflow runs (the host polls). */
  running?: boolean;
  /** A refusal in words (the host maps the server's code). */
  problem?: string | null;
  tz?: string;
  onRelease?: () => void;
  onBack?: () => void;
}

export function IssuanceLive(props: IssuanceLiveProps): JSX.Element {
  const { release } = props;
  const tz = props.tz ?? DEFAULT_TZ;
  const [open, setOpen] = useState(false);
  const [attested, setAttested] = useState(false);
  const released = release.released_at !== null;
  // The control shows only when the server lists it and the host binds it: never a dead button.
  const canAct =
    release.allowed_actions.includes("report.release") && props.onRelease !== undefined;
  const blocked = release.gates.filter((g) => !g.met).map((g) => g.gate);
  return (
    <div data-screen="AUD-24" data-live="true" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center gap-2 px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
        <h2 className="flex-1 text-[15px] font-medium">{TITLE}</h2>
        {released ? (
          <span data-released="true" className="text-[13px]">
            Released {dateTime(release.released_at ?? "", { tz })} ·{" "}
            {release.released_by_name ?? release.engagement_partner_name}
          </span>
        ) : canAct ? (
          <Button
            size="sm"
            disabled={!release.can_release || props.running === true}
            onClick={() => {
              setAttested(false);
              setOpen(true);
            }}
          >
            {props.running === true ? "Releasing…" : "Release report…"}
          </Button>
        ) : (
          <span className="text-[13px] text-ink-3">
            Only {release.engagement_partner_name} can release this report
          </span>
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
      {!released && blocked.length > 0 && (
        <p data-blocked="true" className="mx-[12px] mb-2 text-[13px] text-ink-3">
          Blocked by {blocked.join(", ")}
        </p>
      )}
      <div className="grid gap-[10px] px-[12px] pb-[12px]">
        {release.gates.map((g) => {
          const title = GATE_TITLE[g.gate] ?? g.gate;
          return (
            <section
              key={g.gate}
              data-gate={g.gate}
              data-met={g.met ? "true" : "false"}
              className="flex items-center gap-2 rounded-pane bg-card px-[12px] py-[10px] shadow-e1"
            >
              <Icon name={g.met ? "circle-check" : "circle"} size={15} />
              <span className="w-[40px] font-medium">{g.gate}</span>
              <span className="flex-1">{title}</span>
              <span className="text-[13px] text-ink-3">{g.value ?? ""}</span>
              <span className="text-[13px]">{g.met ? MET : NOT_MET}</span>
            </section>
          );
        })}
        <section aria-label="Also required" className="rounded-pane bg-card shadow-e1">
          <ul>
            {release.also_required.map((a) => (
              <li
                key={a.key}
                data-also={a.key}
                data-met={a.met ? "true" : "false"}
                className="flex min-h-[36px] items-center gap-2 px-[12px] text-[13px]"
              >
                <Icon name={a.met ? "circle-check" : "circle"} size={13} />
                <span className="flex-1">{ALSO_LABEL[a.key] ?? a.key}</span>
                <span className="text-ink-3">{a.value ?? ""}</span>
              </li>
            ))}
          </ul>
        </section>
        {release.documentation_completion_date !== null && (
          <p data-clock="true" className="text-[13px]">
            Archive by {release.documentation_completion_date}
          </p>
        )}
      </div>
      <Dialog open={open} onOpenChange={setOpen} title={DIALOG.title}>
        <Checkbox label={DIALOG.attest} showLabel checked={attested} onChange={setAttested} />
        <div className="mt-3 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setOpen(false);
            }}
          >
            {DIALOG.cancel}
          </Button>
          <Button
            disabled={!attested}
            onClick={() => {
              setOpen(false);
              props.onRelease?.();
            }}
          >
            {DIALOG.confirm}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
