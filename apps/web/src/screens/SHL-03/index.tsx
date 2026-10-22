import { meOptions } from "@abacus/api-client/query";
import { AppShell } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useSession } from "../../app-core/session";
import { FirmMenu } from "../../shell/firm/FirmMenu";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import type { Shl03State } from "./scenarios";

// SHL-03 · Firm switcher and profile menu (P-01-T08). The tray is chrome over every firm screen
// (legacy/Layout.tsx mounts shell/firm/FirmMenu under the firm pill); this is its artboard, as
// fixture mode and the gallery draw it: Home's empty T2 body under a pressed firm pill and the
// tray held open at x90 y52. Each frame differs only in its data, never in a prop:
//
//   a  Grace Holloway: Firm settings, Users & roles, Audit log (nav write/write/read)
//   b  Hannah Leclerc: no admin section (every nav key none); default office Chicago
//   c  Daniel Reyes: Firm settings "View only" (read) and Audit log
//   d  Felix Andersen: Security center, Developer & API, Audit log
//   e  Grace with a second membership, the training sandbox
//   f  Grace with the Default office filter's 200 menu open

export function SHL03({ state = "a" }: { state?: Shl03State }): JSX.Element {
  const me = useQuery(meOptions()).data;
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/" },
    firm,
    firmMenuOpen: true,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state} className="relative">
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay} />
      <FirmMenu
        open
        onOpenChange={() => undefined}
        activeTenantId={me?.active_tenant_id ?? null}
        navigate={() => undefined}
        onShortcuts={bar.openGo}
        onNotificationPreferences={() => undefined}
        onSwitch={() => undefined}
        onSignedOut={() => undefined}
        held={{ officeMenu: state === "f" }}
      />
    </div>
  );
}
