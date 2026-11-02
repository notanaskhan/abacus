import { AppShell } from "@abacus/ui";
import type { JSX } from "react";
import { useSession } from "../../app-core/session";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { AuditCockpitPage } from "../AUD-02";
import type { Ebp01State } from "./scenarios";

// EBP-01's artboards (A-05-T11): the AUD-02 cockpit with Overview › Plan profile open on
// Northwind PY2025, inside the app shell at 1440 × 860, as AUD-07 draws its own. No dock (T2).

export function EBP01Frame({ state }: { state: Ebp01State }): JSX.Element {
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
          data-screen-frame="EBP-01"
          data-state={state}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <AuditCockpitPage
            auditId={NORTHWIND_AUDIT}
            initial={{ section: "ebp_01", ...(state === "d" ? { planEditing: true } : {}) }}
          />
        </div>
      </AppShell>
    </div>
  );
}
