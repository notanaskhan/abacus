import { meOptions } from "@abacus/api-client/query";
import { Alert, Bell, Building2, Button, Card, LogOut, Spinner } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, Outlet, useRouterState } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { App } from "../App";
import { isForbidden } from "../shell/mfa";
import { NoFirm } from "./Signup";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, chosenTenant, signIn, signOut } from "../auth/session";
import { NotificationPanel, useUnreadCount } from "../shell/NotificationPanel";

/** The signed-in firm workspace: the toolbar (TASK-092), notifications, and the page. */
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
  const [panel, setPanel] = useState(false);
  const path = useRouterState({ select: (r) => r.location.pathname });

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
            <Button size="sm" variant="outline" onClick={() => void me.refetch()}>
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
          <h1 className="mb-3 text-xl">Choose a firm</h1>
          <ul className="flex flex-col gap-2">
            {staff.map((m) => (
              <li key={m.tenant_id}>
                <Button
                  variant="outline"
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

  const isAdmin = firm.firm_role === "firm_admin" || firm.firm_role === "practice_leader";
  return (
    <div className="flex min-h-screen flex-col bg-shell">
      <header className="sticky top-0 z-30 flex h-[46px] shrink-0 items-center gap-2 border-b-[0.5px] border-hair bg-card px-3">
        <Link
          to="/"
          aria-label="Abacus home"
          className="mr-1 flex items-center gap-2 rounded-full pr-2 text-[14.5px] font-medium tracking-[-0.02em] text-ink hover:no-underline"
        >
          <span
            aria-hidden="true"
            className="flex size-[22px] items-center justify-center rounded-[6px] bg-espresso text-[12px] font-medium text-on-dark"
          >
            A
          </span>
          Abacus
        </Link>
        <nav aria-label="Workspace" className="ml-3 flex items-center gap-px">
          <Link
            to="/"
            data-current={path === "/" || path.startsWith("/engagements") ? "true" : undefined}
            className={NAV_LINK}
          >
            Engagements
          </Link>
          <Link
            to="/knowledge"
            data-current={path.startsWith("/knowledge") ? "true" : undefined}
            className={NAV_LINK}
          >
            Knowledge
          </Link>
        </nav>
        <span className="flex-1" />
        {isAdmin && (
          <Link
            to="/admin/methodology"
            data-current={path.startsWith("/admin") ? "true" : undefined}
            className={NAV_LINK}
          >
            <Building2 aria-hidden="true" className="mr-1.5 size-3.5" />
            Firm settings
          </Link>
        )}
        <NotificationsButton
          active={panel}
          onToggle={() => {
            setPanel((open) => !open);
          }}
        />
        <span className="flex h-[30px] items-center gap-2 rounded-full bg-nav-fill pr-3 pl-1 text-[13px] shadow-e1">
          <span
            aria-hidden="true"
            className="flex size-[22px] items-center justify-center rounded-full bg-chip text-[10.5px] font-medium text-ink-2"
          >
            {initials(me.data.display_name)}
          </span>
          <span className="max-w-[260px] truncate">
            {me.data.display_name} · {firm.firm_name}
          </span>
        </span>
        <button
          type="button"
          aria-label="Sign out"
          title="Sign out"
          onClick={() => {
            signOut();
            queryClient.clear();
            void signIn("/");
          }}
          className="flex size-[30px] items-center justify-center rounded-full text-ink-2 hover:bg-nav-fill hover:text-ink"
        >
          <LogOut aria-hidden="true" className="size-[15px]" />
        </button>
      </header>
      <div className="flex min-h-0 flex-1">
        <main className="mx-auto w-full max-w-[1400px] min-w-0 flex-1 px-3 pt-3 pb-8">
          <Outlet />
        </main>
        {panel && (
          <NotificationPanel
            onClose={() => {
              setPanel(false);
            }}
          />
        )}
      </div>
    </div>
  );
}

const NAV_LINK =
  "flex h-8 items-center rounded-full px-3 text-[13.5px] tracking-[-0.005em] text-ink-2 hover:bg-sel-bg hover:text-ink hover:no-underline data-[current=true]:bg-nav-fill data-[current=true]:font-medium data-[current=true]:text-ink";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join("");
}

function NotificationsButton({
  active,
  onToggle,
}: {
  active: boolean;
  onToggle: () => void;
}): JSX.Element {
  const unread = useUnreadCount();
  // A dot, never a count (the plan's bell); the count stays in the accessible name.
  return (
    <button
      type="button"
      aria-label={unread > 0 ? `Notifications, ${String(unread)} unread` : "Notifications"}
      aria-pressed={active}
      title="Notifications"
      onClick={onToggle}
      className="relative flex size-[30px] items-center justify-center rounded-full bg-nav-fill text-ink-2 shadow-e1 hover:bg-sel-bg hover:text-ink aria-pressed:bg-sel-bg aria-pressed:text-ink"
    >
      <Bell aria-hidden="true" className="size-[15px]" />
      {unread > 0 && (
        <span
          aria-hidden="true"
          className="absolute top-[6px] right-[7px] size-1.5 rounded-full bg-red ring-[1.5px] ring-nav-fill"
        />
      )}
    </button>
  );
}
