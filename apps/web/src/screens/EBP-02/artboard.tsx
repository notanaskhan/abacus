import { AppShell } from "@abacus/ui";
import type { JSX } from "react";
import { useSession } from "../../app-core/session";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { AuditCockpitPage } from "../AUD-02";
import type { Ebp02State } from "./scenarios";

// EBP-02's artboards (A-05-T17): the AUD-02 cockpit with Fieldwork › Plan Review open on
// Northwind PY2025, inside the app shell at 1440 × 860, as EBP-01 draws its own; b2 opens the
// earlier review (`?version=1`).

export function EBP02Frame({ state }: { state: Ebp02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/audits" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <div
          data-screen-frame="EBP-02"
          data-state={state}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <AuditCockpitPage
            auditId={NORTHWIND_AUDIT}
            initial={{ section: "ebp_02", ...(state === "b2" ? { planReviewVersion: 1 } : {}) }}
          />
        </div>
      </AppShell>
    </div>
  );
}
