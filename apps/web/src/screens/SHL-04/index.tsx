import { AppShell } from "@abacus/ui";
import type { JSX } from "react";
import { useSession } from "../../app-core/session";
import { type FeedTab, NotificationsDrawer } from "../../shell/firm/NotificationsDrawer";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import type { Shl04State } from "./scenarios";

// SHL-04 · Notifications panel (P-01-T10). The drawer is the `?ov=notifications` layer over every
// firm screen (shell/firm/NotificationsDrawer.tsx); this is its artboard, as fixture mode and the
// gallery draw it: the toolbar with the bell pressed and the 480 drawer held open at the right.
// Each frame is its data, and b, b′ and b_raj open on the Approvals tab:
//
//   a      rows a–i, 4 unread, Today and Friday, September 11
//   b      Approvals: rows a, b and d (count 3), then "Open approvals queue →"
//   bp     Approvals with nothing waiting
//   b_raj  Raj Malhotra: Approvals adds the Copperleaf AJE proposal (deep link only)
//   c      after Accept: row d's receipt line; PBC 12 of 24 under it
//   d      all read: no dots
//   e      a new user: "You're all caught up."
//   f      loading: 5 skeleton rows
//   g      R2 kinds at Thu Oct 1: a to-do, a template update, two trigger runs

const APPROVALS: readonly Shl04State[] = ["b", "bp", "b_raj"];

export function SHL04({ state = "a" }: { state?: Shl04State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/" },
    firm,
    bellOpen: true,
    navigate: () => undefined,
    hotkeys: false,
  });
  const tab: FeedTab = APPROVALS.includes(state) ? "approvals" : "all";
  return (
    <div data-artboard={state} className="relative">
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay} />
      <div className="absolute top-[10px] right-[10px] bottom-[10px]">
        <NotificationsDrawer
          open
          onOpenChange={() => undefined}
          navigate={() => undefined}
          held={{ tab }}
        />
      </div>
    </div>
  );
}
