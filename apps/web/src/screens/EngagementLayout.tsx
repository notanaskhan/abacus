import { engagementGraphOptions } from "@abacus/api-client/query";
import { Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";
import type { JSX } from "react";
import { Tabs } from "../shell/Tabs";
import { IndependenceBanner } from "./MyConfirmations";

/** An engagement's header and tabs (SPEC-016): Overview · Requests · Map · Contacts. */
export function EngagementLayout({ engagementId }: { engagementId: string }): JSX.Element {
  const graph = useQuery(engagementGraphOptions({ path: { engagement_id: engagementId } }));
  const e = graph.data?.engagement;
  const params = { engagementId };
  return (
    <div className="flex flex-col gap-4">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-muted">
        <Link to="/" className="hover:underline">
          Engagements
        </Link>
        <span aria-hidden="true">/</span>
        <span className="font-semibold text-ink">
          {e === undefined ? "Engagement" : `${e.client_name} · ${e.name}`}
        </span>
      </nav>
      <div className="flex flex-wrap items-center gap-3">
        {e === undefined ? (
          <Skeleton className="h-8 w-80" />
        ) : (
          <>
            <h1 className="text-3xl">{e.name}</h1>
            <StatusPill tone={e.status === "archived" ? "neutral" : "info"}>
              {e.status === "archived" ? "Archived" : "Active"}
            </StatusPill>
            <span className="text-sm text-muted tabular-nums">
              {e.fiscal_period_start} – {e.fiscal_period_end}
            </span>
          </>
        )}
      </div>
      <IndependenceBanner engagementId={engagementId} />
      <Tabs
        label="Engagement"
        items={[
          { label: "Overview", to: "/engagements/$engagementId", params, exact: true },
          { label: "Requests", to: "/engagements/$engagementId/requests", params },
          { label: "Map", to: "/engagements/$engagementId/map", params },
          { label: "People", to: "/engagements/$engagementId/people", params },
          { label: "Review", to: "/engagements/$engagementId/review", params },
        ]}
      />
      <Outlet />
    </div>
  );
}
