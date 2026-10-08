import { meOptions } from "@abacus/api-client/query";
import {
  Alert,
  Bell,
  Building2,
  Button,
  Card,
  FolderOpen,
  LogOut,
  Rail,
  RailButton,
  Spinner,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, Outlet } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { App } from "../App";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, chosenTenant, signIn, signOut } from "../auth/session";
import { NotificationPanel, useUnreadCount } from "../shell/NotificationPanel";

/** The signed-in firm workspace (SPEC-016): rail, header, notifications, and the page. */
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

const RAIL_LINK =
  "flex size-11 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-sunken hover:text-ink data-[status=active]:bg-accent-soft data-[status=active]:text-accent";

function SignedIn(): JSX.Element {
  const queryClient = useQueryClient();
  const me = useQuery(meOptions());
  // React state, so choosing a firm re-renders (the API reports no active firm for users in
  // several; the choice is also kept for the client's X-Abacus-Tenant header).
  const [picked, setPicked] = useState<string | null>(chosenTenant);
  const [panel, setPanel] = useState(false);

  if (me.isPending) {
    return (
      <main className="p-8">
        <Spinner label="Loading your account…" />
      </main>
    );
  }
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

  const tenant = me.data.active_tenant_id ?? picked;
  const firm = me.data.memberships.find((m) => m.tenant_id === tenant);
  if (firm === undefined) {
    return (
      <main className="mx-auto max-w-md p-8">
        <Card>
          <h1 className="mb-3 text-xl">Choose a firm</h1>
          <ul className="flex flex-col gap-2">
            {me.data.memberships.map((m) => (
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
  // SPEC-016 AC-8: client users have their own route tree.
  if (firm.kind === "client") return <Navigate to="/client" />;

  const isAdmin = firm.firm_role === "firm_admin" || firm.firm_role === "practice_leader";
  return (
    <div className="flex min-h-screen flex-col bg-ground sm:flex-row">
      <Rail label="Workspace">
        <Link
          to="/"
          aria-label="Abacus home"
          className="mb-2 flex size-9 items-center justify-center rounded-[var(--radius-control)] bg-accent font-display text-lg font-semibold text-on-accent"
        >
          A
        </Link>
        <Link to="/" aria-label="Engagements" title="Engagements" className={RAIL_LINK}>
          <FolderOpen aria-hidden="true" className="size-5" />
        </Link>
        {isAdmin && (
          <Link
            to="/admin/methodology"
            aria-label="Firm admin"
            title="Firm admin"
            className={RAIL_LINK}
          >
            <Building2 aria-hidden="true" className="size-5" />
          </Link>
        )}
        <span className="flex-1" />
        <NotificationsButton
          active={panel}
          onToggle={() => {
            setPanel((open) => !open);
          }}
        />
        <RailButton
          label="Sign out"
          onClick={() => {
            signOut();
            queryClient.clear();
            void signIn("/");
          }}
        >
          <LogOut aria-hidden="true" className="size-5" />
        </RailButton>
      </Rail>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-6 py-3">
          <Link to="/" className="font-display text-lg font-semibold">
            Abacus
          </Link>
          <span className="text-sm text-muted">
            {me.data.display_name} · {firm.firm_name}
          </span>
        </header>
        <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
          <main className="mx-auto w-full max-w-7xl min-w-0 flex-1 p-6">
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
    </div>
  );
}

function NotificationsButton({
  active,
  onToggle,
}: {
  active: boolean;
  onToggle: () => void;
}): JSX.Element {
  const unread = useUnreadCount();
  return (
    <RailButton label="Notifications" badge={unread} active={active} onClick={onToggle}>
      <Bell aria-hidden="true" className="size-5" />
    </RailButton>
  );
}
