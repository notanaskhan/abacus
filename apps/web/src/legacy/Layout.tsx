import { meOptions } from "@abacus/api-client/query";
import {
  Alert,
  AppShell,
  Building2,
  Button,
  Card,
  LogOut,
  Spinner,
  type ToolbarNavItem,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { type JSX, useEffect, useState } from "react";
import { App } from "../App";
import { isForbidden } from "../shell/mfa";
import { NoFirm } from "./Signup";
import { errorMessage } from "../api";
import { accessToken, chooseTenant, chosenTenant, signIn, signOut } from "../auth/session";
import { NotificationDrawer } from "../shell/NotificationDrawer";
import { useUnreadCount } from "../shell/NotificationPanel";
import { Palette } from "../shell/Palette";

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
  const [panel, setPanel] = useState(false);
  const [menu, setMenu] = useState(false);
  const [go, setGo] = useState(false);
  const navigate = useNavigate();
  const unread = useUnreadCount();
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

  const isAdmin = firm.firm_role === "firm_admin" || firm.firm_role === "practice_leader";
  const area = areaOf(path);
  return (
    <AppShell
      toolbar={{
        nav: NAV,
        active: area,
        firm: firm.firm_name,
        firmTitle: firm.firm_name,
        firmPressed: menu || path.startsWith("/admin"),
        bellPressed: panel,
        unread: unread > 0,
        onGo: () => {
          setGo((open) => !open);
        },
        onNavigate: (label) => {
          const to = NAV_PATHS[label];
          if (to !== undefined) void navigate({ to });
        },
        onBell: () => {
          setPanel((open) => !open);
        },
        onFirm: () => {
          setMenu((open) => !open);
        },
      }}
      overlay={
        <>
          <Palette
            isAdmin={isAdmin}
            open={go}
            onOpenChange={setGo}
            onNotifications={() => {
              setPanel(true);
            }}
          />
          {menu && (
            <FirmMenu
              person={me.data.display_name}
              firm={firm.firm_name}
              isAdmin={isAdmin}
              onClose={() => {
                setMenu(false);
              }}
              onSignOut={() => {
                signOut();
                queryClient.clear();
                void signIn("/");
              }}
            />
          )}
        </>
      }
    >
      <div className="flex min-h-0 flex-1">
        <main className="mx-auto w-full max-w-[1400px] min-w-0 flex-1 px-3 pt-3 pb-8">
          <Outlet />
        </main>
        <NotificationDrawer open={panel} onOpenChange={setPanel} />
      </div>
    </AppShell>
  );
}

// The legacy screens' areas until the toolbar renders from nav.ts (P-01-T02); the first is Home.
const NAV: readonly ToolbarNavItem[] = [
  { label: "Home" },
  { label: "Clients" },
  { label: "Knowledge" },
];
const NAV_PATHS: Readonly<Record<string, string>> = {
  Home: "/",
  Clients: "/clients",
  Knowledge: "/knowledge",
};

function areaOf(path: string): string {
  if (path.startsWith("/clients")) return "Clients";
  if (path.startsWith("/knowledge")) return "Knowledge";
  if (path.startsWith("/admin")) return "";
  return "Home";
}

/** SHL-03: the firm pill's menu (the toolbar has no avatar): the person, the firm, Firm
 * settings for administrators, and Sign out. */
function FirmMenu({
  person,
  firm,
  isAdmin,
  onClose,
  onSignOut,
}: {
  person: string;
  firm: string;
  isAdmin: boolean;
  onClose: () => void;
  onSignOut: () => void;
}): JSX.Element {
  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  return (
    <div
      role="menu"
      aria-label="Firm and profile"
      className="fixed top-[50px] right-3 z-50 w-[280px] rounded-menu bg-card p-2 shadow-e3"
    >
      <div className="flex items-center gap-2 px-2 py-2">
        <span
          aria-hidden="true"
          className="flex size-[28px] items-center justify-center rounded-full bg-chip text-meta font-medium text-ink-2"
        >
          {initials(person)}
        </span>
        <span className="truncate text-body">
          {person} · {firm}
        </span>
      </div>
      {isAdmin && (
        <Link
          to="/admin/methodology"
          role="menuitem"
          onClick={onClose}
          className="flex h-8 items-center gap-1.5 rounded-pill px-2 text-body text-ink-2 hover:bg-sel-bg hover:text-ink hover:no-underline"
        >
          <Building2 aria-hidden="true" className="size-3.5" />
          Firm settings
        </Link>
      )}
      <button
        type="button"
        role="menuitem"
        onClick={onSignOut}
        className="flex h-8 w-full items-center gap-1.5 rounded-pill px-2 text-body text-ink-2 hover:bg-sel-bg hover:text-ink"
      >
        <LogOut aria-hidden="true" className="size-3.5" />
        Sign out
      </button>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join("");
}
