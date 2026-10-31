import { AppShell } from "@abacus/ui";
import type { JSX } from "react";
import { useSession } from "../../app-core/session";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { AuditCockpitPage } from "../AUD-02";
import { type Aud11State, NORTHWIND_AUDIT } from "./scenarios";

// AUD-11's artboards (A-03-T11): the AUD-02 cockpit with Fieldwork › Sample Selection open on
// Northwind, inside the app shell at 1440 × 860 as AUD-02 and AUD-06 draw theirs. The dock opens
// on the Viewer (DV-A2). d opens the size edit at 20 (the person's edit, held for the board).

export function AUD11Frame({ state }: { state: Aud11State }): JSX.Element {
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
          data-screen="AUD-11"
          data-state={state}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <AuditCockpitPage
            auditId={NORTHWIND_AUDIT}
            initial={{
              section: "sample_selection",
              dock: "viewer",
              ...(state === "d" ? { sampleSelection: { editSize: 20 } } : {}),
            }}
          />
        </div>
      </AppShell>
    </div>
  );
}
