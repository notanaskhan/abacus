import type { DashboardOut } from "@abacus/api-client";
import { engagementDashboardOptions } from "@abacus/api-client/query";
import { Alert, Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";

// SPEC-317 (TASK-460; K-04 ENG-12): the engagement at a glance. Every number comes from the
// server, computed by code from the modules' own facts; "Next up" is what the signed-in person
// can do now, decided by the permission matrix. Each tile and row opens where the work lives.

const GATE: Record<string, string> = {
  G1: "Accepted",
  G2: "Independence",
  G3: "Engagement letter",
  G5: "Review complete",
  G6: "EQR",
  G7: "Representation letter",
  G8: "Released",
  G9: "Archived",
};
const NEXT: Record<DashboardOut["next_up"][number]["kind"], string> = {
  prepare: "Sign as preparer",
  review: "Review and sign",
  answer_note: "Answer a review note",
  clear_note: "Clear an answered note",
  chase_request: "Chase an overdue request",
};
type Tab =
  | "/engagements/$engagementId/sign-offs"
  | "/engagements/$engagementId/requests"
  | "/engagements/$engagementId/trial-balance"
  | "/engagements/$engagementId/fieldwork"
  | "/engagements/$engagementId/findings";
const TILE_TAB: Record<string, Tab> = {
  papers_complete: "/engagements/$engagementId/sign-offs",
  ready_for_review: "/engagements/$engagementId/sign-offs",
  changed: "/engagements/$engagementId/sign-offs",
  open_notes: "/engagements/$engagementId/sign-offs",
  requests_received: "/engagements/$engagementId/requests",
  requests_overdue: "/engagements/$engagementId/requests",
  tb_checks: "/engagements/$engagementId/trial-balance",
  accounts_mapped: "/engagements/$engagementId/trial-balance",
  procedures: "/engagements/$engagementId/fieldwork",
  findings: "/engagements/$engagementId/findings",
  entries_awaiting: "/engagements/$engagementId/findings",
  passed_entries: "/engagements/$engagementId/findings",
};

/** The tab a "next up" row opens ("paper" opens the working paper itself). */
export function nextTab(item: DashboardOut["next_up"][number]): Tab | "paper" {
  if (item.kind === "chase_request") return "/engagements/$engagementId/requests";
  if (item.target_type === "workpaper") return "paper";
  if (item.target_type === "trial_balance" || item.target_type === "mapping_set") {
    return "/engagements/$engagementId/trial-balance";
  }
  return "/engagements/$engagementId/sign-offs";
}

export function EngagementDashboard({ engagementId }: { engagementId: string }): JSX.Element {
  const dashboard = useQuery({
    ...engagementDashboardOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  if (dashboard.isPending) return <Skeleton className="h-96" />;
  if (dashboard.isError) {
    return (
      <Alert title="The dashboard isn't available">
        {errorMessage(dashboard.error) === "forbidden"
          ? "The dashboard is for the engagement team."
          : errorMessage(dashboard.error)}
      </Alert>
    );
  }
  const d = dashboard.data;
  const params = { engagementId };
  const row = "flex items-center gap-3 px-4 py-2 text-[13px] hover:bg-nested";
  return (
    <div className="flex flex-col gap-3">
      <section
        aria-label="Gates"
        className="flex flex-wrap gap-1.5 rounded-pane bg-card p-3 shadow-e2"
      >
        {d.gates.map((g) => (
          <StatusPill key={g.gate} tone={g.met ? "success" : "neutral"}>
            {`${g.gate} · ${GATE[g.gate] ?? g.gate}`}
          </StatusPill>
        ))}
      </section>
      <section
        aria-label="Progress"
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4"
      >
        {d.tiles.map((t) => (
          <Link
            key={t.key}
            to={TILE_TAB[t.key] ?? "/engagements/$engagementId/sign-offs"}
            params={params}
            data-attention={t.attention ? "true" : undefined}
            className={`flex flex-col gap-1 rounded-pane bg-card p-3.5 shadow-e2 hover:shadow-e1 ${t.attention ? "inset-shadow-[inset_3px_0_0_var(--color-amber)]" : ""}`}
          >
            <span className="text-[11.5px] font-medium text-ink-3">{t.label}</span>
            <span className="text-[22px] font-medium tracking-[-0.02em] tabular-nums">
              {String(t.value)}
              {t.total != null && (
                <span className="text-[14px] text-ink-3">{` of ${String(t.total)}`}</span>
              )}
            </span>
          </Link>
        ))}
      </section>
      <section aria-labelledby="next-heading" className="rounded-pane bg-card shadow-e2">
        <div className="flex min-h-[46px] items-center border-b-[0.5px] border-hair px-4">
          <h2 id="next-heading" className="text-[14px] font-medium tracking-[-0.01em]">
            Next up for you
          </h2>
        </div>
        {d.next_up.length === 0 ? (
          <p className="px-4 py-3 text-[13px] text-ink-3">Nothing waits on you right now.</p>
        ) : (
          <ul className="flex flex-col">
            {d.next_up.map((n, i) => {
              const tab = nextTab(n);
              const label = (
                <>
                  <span className="w-[200px] shrink-0 text-ink-3">{NEXT[n.kind]}</span>
                  {n.code != null && <span className="font-medium tabular-nums">{n.code}</span>}
                  <span className="truncate">{n.label}</span>
                </>
              );
              return (
                <li
                  key={`${n.kind}-${n.target_id}-${String(i)}`}
                  className="border-t-[0.5px] border-hair first:border-t-0"
                >
                  {tab === "paper" ? (
                    <Link
                      to="/engagements/$engagementId/workpapers/$workpaperId"
                      params={{ engagementId, workpaperId: n.target_id }}
                      className={row}
                    >
                      {label}
                    </Link>
                  ) : (
                    <Link to={tab} params={params} className={row}>
                      {label}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
