import { AppShell } from "@abacus/ui";
import type { JSX } from "react";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { useSession } from "../../app-core/session";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { AuditCockpitPage } from "../AUD-02";
import type { Aud07State } from "./scenarios";

// AUD-07's artboards (A-04-T10): the AUD-02 cockpit with Planning › Materiality open on Northwind
// PY2025, inside the app shell at 1440 × 860 as AUD-02, AUD-06 and AUD-11 draw theirs. The dock
// opens on the Agent view: the recommender's reasons and the SHL-11 e card.

export function AUD07Frame({ state }: { state: Aud07State }): JSX.Element {
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
          data-screen="AUD-07"
          data-state={state}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <AuditCockpitPage auditId={NORTHWIND_AUDIT} initial={{ section: "materiality" }} />
        </div>
      </AppShell>
    </div>
  );
}
