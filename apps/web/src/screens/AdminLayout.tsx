import { listSupportSessionsOptions, meOptions } from "@abacus/api-client/query";
import { Alert } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";
import type { JSX } from "react";
import { type TabItem, Tabs } from "../shell/Tabs";

/** Firm admin (SPEC-019 Q1): tabs by role; the API stays the authority. */
export function AdminLayout(): JSX.Element {
  const me = useQuery(meOptions());
  const tenant = me.data?.active_tenant_id ?? null;
  const role = me.data?.memberships.find((m) => m.tenant_id === tenant)?.firm_role ?? null;
  const isAdmin = role === "firm_admin";
  const tabs: TabItem[] = [
    { label: "Methodology", to: "/admin/methodology", params: {} },
    { label: "Knowledge documents", to: "/admin/knowledge", params: {} },
    { label: "Budget", to: "/admin/budget", params: {} },
    ...(isAdmin
      ? ([
          { label: "Support access", to: "/admin/support", params: {} },
          { label: "Walls", to: "/admin/walls", params: {} },
        ] satisfies TabItem[])
      : []),
  ];
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl">Firm admin</h1>
      {isAdmin && <EmergencyBanner />}
      <Tabs label="Firm admin" items={tabs} />
      <Outlet />
    </div>
  );
}

/** SPEC-019 Q3: an emergency support session stays visible until a firm admin acknowledges it. */
function EmergencyBanner(): JSX.Element | null {
  const sessions = useQuery(listSupportSessionsOptions());
  const open = (sessions.data ?? []).filter((s) => s.emergency && !s.acknowledged);
  if (open.length === 0) return null;
  return (
    <Alert
      title="Emergency support access needs your review"
      action={
        <Link to="/admin/support" className="text-sm font-semibold text-accent hover:underline">
          Review
        </Link>
      }
    >
      Platform support opened emergency access to your firm. Acknowledge it once you&apos;ve
      reviewed the session.
    </Alert>
  );
}
