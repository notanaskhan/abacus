import { DEFAULT_TZ, PaneHeader, ViewStateBody, dateTime } from "@abacus/ui";
import type { JSX } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { AuditCockpitPage } from "../AUD-02";
import { COPY } from "./copy";
import { NORTHWIND_AUDIT, NORTHWIND_ENGAGEMENT, type Aud06State, OPENS } from "./scenarios";
import { useTrialBalancePane } from "./TrialBalance";

// AUD-06's artboards (A-02-T09): Northwind's frames (a–f) are the AUD-02 cockpit with the Trial
// Balance row open, the Viewer dock on, and the artboard's line selected; the other engagements'
// frames (g, h and the added Granite Peak states) draw the same workpaper pane on its own until
// their cockpits exist (A-09, A-02-T14). Every figure is read through the generated client.

function Pane({ state }: { state: Aud06State }): JSX.Element {
  const opens = OPENS[state];
  const { canvas } = useTrialBalancePane(opens.engagementId, {
    initial: {
      tab: opens.tab,
      layer: opens.layer,
      ...(opens.selected === undefined ? {} : { line: opens.selected }),
    },
  });
  const state_ = canvas.state ?? { kind: "ready" };
  return (
    <section
      aria-label={COPY.title}
      className="flex h-[860px] w-[536px] flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <PaneHeader title={canvas.title} titleAlign="left" right={canvas.actions} />
      {canvas.controls !== undefined && state_.kind === "ready" && (
        <div className="flex h-[42px] flex-none items-center gap-[8px] px-[12px]">
          {canvas.controls}
        </div>
      )}
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">
        <ViewStateBody
          state={state_}
          rows="card"
          empty={canvas.empty ?? { title: COPY.empty }}
          noun={canvas.title.toLowerCase()}
        >
          {canvas.children}
        </ViewStateBody>
      </div>
    </section>
  );
}

export function AUD06Frame({ state }: { state: Aud06State }): JSX.Element {
  const opens = OPENS[state];
  const session = useSession();
  const now = useNow();
  const tz = session.tz ?? DEFAULT_TZ;
  const northwind = opens.engagementId === NORTHWIND_ENGAGEMENT;
  return (
    <div data-screen="AUD-06" data-state={state} className="flex min-h-0 flex-1 flex-col">
      {/* The gallery's own record of who and when the artboard is drawn for. */}
      <p data-aud06="who" className="sr-only">
        {`${session.user?.displayName ?? ""} · ${dateTime(now, { tz })}${opens.ov === undefined ? "" : ` · ?ov=${opens.ov}`}`}
      </p>
      {northwind ? (
        <AuditCockpitPage
          auditId={NORTHWIND_AUDIT}
          initial={{
            section: "trial_balance",
            dock: "viewer",
            trialBalance: {
              tab: opens.tab,
              layer: opens.layer,
              ...(opens.selected === undefined ? {} : { line: opens.selected }),
            },
          }}
        />
      ) : (
        <div className="flex bg-shell p-[12px]">
          <Pane state={state} />
        </div>
      )}
    </div>
  );
}
