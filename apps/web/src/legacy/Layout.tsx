import { meOptions } from "@abacus/api-client/query";
import { Alert, AppShell, Button, Card, Spinner } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { App } from "../App";
import { isForbidden } from "../shell/mfa";
import { NoFirm } from "./Signup";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, chosenTenant, signIn, signOut } from "../auth/session";
import { FirmMenu } from "../shell/firm/FirmMenu";
import { useFirmToolbar } from "../shell/firm/ToolbarData";
import { useOverlays } from "../app-core/overlay-host";
import { NOTIFICATIONS_OVERLAY } from "../shell/firm/NotificationsDrawer";

/** The signed-in firm workspace (F-05-T23): the design system's AppShell and Toolbar around the
 * legacy screens, the firm pill's menu (SHL-03), notifications, and the page. */
export function Layout(): JSX.Element {
  const signedIn = accessToken() !== null;
  useEffect(() => {
    if (!signedIn) void signIn();
  }, [signedIn]);
  if (!signedIn) {
    return <App status="Redirecting to sign-in…" />;
  }
  return <SignedIn />;
}

function SignedIn(): JSX.Element {
  const queryClient = useQueryClient();
  const me = useQuery(meOptions());
  // React state, so choosing a firm re-renders (the API reports no active firm for users in
  // several; the choice is also kept for the client's X-Abacus-Tenant header).
  const [picked, setPicked] = useState<string | null>(chosenTenant);
  const [menu, setMenu] = useState(false);
  // P-01-T10: the notifications drawer is the `?ov=notifications` layer (SHL-04), so Back closes
  // it and a link can open it.
  const overlays = useOverlays();
  const bell = overlays.refs.findIndex((r) => r.key === NOTIFICATIONS_OVERLAY);
  const navigate = useNavigate();
  const path = useRouterState({ select: (r) => r.location.pathname });
  // P-01-T02: the toolbar's data, routing and hotkeys (SHL-01).
  const bar = useFirmToolbar({
    at: { pathname: path },
    firm: "",
    firmMenuOpen: menu,
    bellOpen: bell >= 0,
    onBell: () => {
      if (bell >= 0) overlays.close(bell);
      else overlays.open(NOTIFICATIONS_OVERLAY);
    },
    onFirm: () => {
      setMenu((open) => !open);
    },
    navigate: (to) => void navigate({ to }),
  });

  if (me.isPending) {
    return (
      <main className="p-8">
        <Spinner label="Loading your account…" />
      </main>
    );
  }
  // SPEC-024: a verified sign-in that belongs to no firm at all.
  if (me.isError && isForbidden(me.error)) return <NoFirm />;
  if (me.isError) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Alert
          title="Couldn't load your account"
          action={
            <Button size="sm" variant="secondary" onClick={() => void me.refetch()}>
              Retry
            </Button>
          }
        >
          {errorMessage(me.error)}
        </Alert>
      </main>
    );
  }

  const staff = me.data.memberships.filter((m) => m.kind !== "client");
  if (me.data.memberships.length === 0) return <NoFirm />;
  // Amendment 3 (TASK-040): someone who is only a client contact goes to their client home.
  if (staff.length === 0) return <Navigate to="/client" />;
  const tenant = me.data.active_tenant_id ?? picked;
  const firm = staff.find((m) => m.tenant_id === tenant);
  if (firm === undefined) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Card>
          <h1 className="mb-3 text-title">Choose a firm</h1>
          <ul className="flex flex-col gap-2">
            {staff.map((m) => (
              <li key={m.tenant_id}>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => {
                    chooseTenant(m.tenant_id);
                    setPicked(m.tenant_id);
                    void queryClient.invalidateQueries();
                  }}
                >
                  {m.firm_name}
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      </main>
    );
  }

  return (
    <AppShell
      toolbar={{ ...bar.toolbar, firm: firm.firm_name, firmTitle: firm.firm_name }}
      overlay={
        <>
          {bar.overlay}
          <FirmMenu
            open={menu}
            onOpenChange={setMenu}
            activeTenantId={firm.tenant_id}
            navigate={(to) => void navigate({ to })}
            onShortcuts={bar.openGo}
            onNotificationPreferences={() => {
              if (bell < 0) overlays.open(NOTIFICATIONS_OVERLAY);
            }}
            onSwitch={(m) => {
              chooseTenant(m.tenant_id);
              setPicked(m.tenant_id);
            }}
            onSignedOut={() => {
              // The SPA's auth client (P-01-T11) moves this to the BFF's hosted sign-in.
              signOut();
              queryClient.clear();
              void signIn("/");
            }}
          />
        </>
      }
    >
      <div className="flex min-h-0 flex-1">
        <main className="mx-auto w-full max-w-[1400px] min-w-0 flex-1 px-3 pt-3 pb-8">
          <Outlet />
        </main>
      </div>
    </AppShell>
  );
}
