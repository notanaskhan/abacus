import { listSupportSessionsOptions, meOptions } from "@abacus/api-client/query";
import { Alert } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, type LinkProps, Outlet } from "@tanstack/react-router";
import type { JSX } from "react";

interface Section {
  label: string;
  to: NonNullable<LinkProps["to"]>;
}

/** Firm settings (SPEC-019 Q1; TASK-098, the plan's T12): a section list in groups on the left,
 * the section on the right. Sections by role; the API stays the authority. */
export function AdminLayout(): JSX.Element {
  const me = useQuery(meOptions());
  const tenant = me.data?.active_tenant_id ?? null;
  const role = me.data?.memberships.find((m) => m.tenant_id === tenant)?.firm_role ?? null;
  const isAdmin = role === "firm_admin";
  const groups: [string, Section[]][] = [
    [
      "Firm",
      [
        { label: "Setup", to: "/admin/setup" },
        // G-01-T17 (DEC-594): People and Walls are ADM-02 and ADM-03 in Settings.
        ...(isAdmin
          ? [
              { label: "People", to: "/settings/people" } as Section,
              { label: "Walls", to: "/settings/offices" } as Section,
            ]
          : []),
      ],
    ],
    [
      "Methodology",
      [
        { label: "Methodology", to: "/admin/methodology" },
        { label: "Knowledge documents", to: "/admin/knowledge" },
        { label: "FS groupings", to: "/admin/fs-groupings" }, // SPEC-316 (TASK-345)
      ],
    ],
    [
      "AI and automation",
      [
        { label: "Autonomy", to: "/admin/autonomy" },
        { label: "Budget", to: "/admin/budget" },
      ],
    ],
    [
      "Security",
      [
        ...(isAdmin ? [{ label: "Support access", to: "/admin/support" } as Section] : []),
        { label: "Audit log", to: "/admin/audit-log" }, // SPEC-304 (TASK-305)
      ],
    ],
  ];
  return (
    <div className="grid items-start gap-3 lg:grid-cols-[240px_minmax(0,1fr)]">
      <nav
        aria-label="Firm settings"
        className="flex flex-col gap-3 rounded-pane bg-card p-2 shadow-e2 lg:sticky lg:top-[58px]"
      >
        <h1 className="px-2.5 pt-1.5 text-[15px] font-medium tracking-[-0.012em]">
          Firm settings
        </h1>
        {groups.map(([group, sections]) => (
          <div key={group} className="flex flex-col gap-px">
            <p className="px-2.5 pb-1 text-[10px] font-medium tracking-[0.07em] text-ink-3 uppercase">
              {group}
            </p>
            {sections.map((section) => (
              <Link
                key={section.to}
                to={section.to}
                className="flex h-[30px] items-center rounded-tile px-2.5 text-[13px] text-ink-2 hover:bg-nav-fill hover:text-ink hover:no-underline data-[status=active]:bg-sel-bg data-[status=active]:font-medium data-[status=active]:text-ink"
              >
                {section.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
      <div className="flex min-w-0 flex-col gap-3">
        {isAdmin && <EmergencyBanner />}
        <Outlet />
      </div>
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
        <Link to="/admin/support" className="text-[12.5px] font-medium text-ink underline">
          Review
        </Link>
      }
    >
      Platform support opened emergency access to your firm. Acknowledge it once you&apos;ve
      reviewed the session.
    </Alert>
  );
}
