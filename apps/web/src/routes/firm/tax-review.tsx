import { EmptyState, FlagOffState } from "@abacus/ui";
import { returnRecordOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { type JSX, type ReactNode, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";
import { to } from "../to";

// The return's review workspace (T-04-T12; T-04 §5): new routes in new files, each behind the
// `tax_returns` entitlement and `tax.review_workspace`; with the flag off every one shows F-05's
// flag-off state and T-02's screens are unchanged. The sections' bodies are their screens' own
// (TAX-04 Review from T-04-T13; TAX-06 Issues, TAX-07 Activity, TXI-02 K-1 resolver and TXI-03
// residency after it); until then a fixture build draws "Not built yet". `?ov=assistant` opens
// TAX-08's panel over any section (P-10's dock).
//
//   /tax-returns/$returnId/review/$section     TAX-04 (prepare preset) / TAX-05 (review preset)
//   /tax-returns/$returnId/issues              TAX-06
//   /tax-returns/$returnId/activity            TAX-07
//   /tax-returns/$returnId/k1-resolver/$activityId   TXI-02
//   /tax-returns/$returnId/residency           TXI-03

export const REVIEW_FLAG = "tax.review_workspace";
type WorkspaceTab = "overview" | "intake" | "review" | "issues" | "activity";
const WorkspaceScreen = lazyScreen(
  async () => (await import("../../screens/TAX-04/workspace")).Workspace,
);

// T-04-T13: TAX-04's Prepare preset is fixture mode (the review tree and regions read T-04-T05's
// routes, still 501), so a production build drops it and keeps the frame (SPEC-048 AC-10).
const FIXTURES = import.meta.env.MODE === "test" || import.meta.env.VITE_FIXTURES === "1";
const Prepare = FIXTURES
  ? lazy(async () => ({ default: (await import("../../screens/TAX-04")).TAX04 }))
  : null;
type WorkspaceSearch = { ov?: string; ws?: string };
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// `?ov=` keeps every overlay the host knows (SHL-10, SHL-12, SHL-15 from the live sections, and
// TAX-08's "assistant"); `?ws=<worksheet id>` opens TXI-01 on one worksheet (T-04-T29).
function validateSearch(search: Record<string, unknown>): WorkspaceSearch {
  return {
    ...(typeof search.ov === "string" && search.ov !== "" ? { ov: search.ov } : {}),
    // A worksheet id goes into an API path: a UUID only, never the URL's raw text.
    ...(typeof search.ws === "string" && UUID.test(search.ws) ? { ws: search.ws } : {}),
  };
}

// T-04-T29 (TASK-6828): a live build hosts each section's live screen inside the frame; a
// fixture build keeps the artboards (TAX-04's Prepare preset above, "Not built yet" elsewhere).
const ReviewLive = lazyScreen(async () => (await import("../../screens/TAX-04/live")).ReviewLive);
const WorksheetsLive = lazyScreen(
  async () => (await import("../../screens/TAX-05/live")).WorksheetsLive,
);
const IssuesLive = lazyScreen(async () => (await import("../../screens/TAX-06/live")).IssuesLive);
const ActivityLive = lazyScreen(
  async () => (await import("../../screens/TAX-07/live")).ActivityLive,
);
// TASK-7323: TAX-08's live drawer on `?ov=assistant` (a fixture build keeps the artboards).
const AssistantLive = lazyScreen(
  async () => (await import("../../screens/TAX-08/live")).AssistantLive,
);

/** The return's engagement (the frame's own record read; one cache entry). */
function useEngagementOf(returnId: string): string | undefined {
  return useQuery(returnRecordOptions({ path: { return_id: returnId } })).data?.engagement_id;
}

function LiveSection({
  section,
}: {
  section: "review" | "worksheets" | "issues" | "activity";
}): JSX.Element {
  const returnId = useParam("returnId");
  const engagementId = useEngagementOf(returnId);
  const search: WorkspaceSearch = useSearch({ strict: false });
  if (section === "issues") return <IssuesLive returnId={returnId} engagementId={engagementId} />;
  if (section === "activity") {
    return <ActivityLive returnId={returnId} engagementId={engagementId} />;
  }
  if (section === "worksheets") {
    return (
      <WorksheetsLive
        returnId={returnId}
        engagementId={engagementId}
        {...(search.ws === undefined ? {} : { worksheetId: search.ws })}
      />
    );
  }
  return <ReviewLive returnId={returnId} engagementId={engagementId} />;
}

function Workspace({
  tab,
  title,
  children,
}: {
  tab: WorkspaceTab;
  title: string;
  children?: ReactNode;
}): JSX.Element {
  const returnId = useParam("returnId");
  const navigate = useNavigate();
  const search: WorkspaceSearch = useSearch({ strict: false });
  const go = (next: WorkspaceTab): void => {
    if (next === "overview") void navigate(to.TAX02({ returnId }));
    else if (next === "intake") void navigate(to.TAX03({ returnId }));
    else if (next === "review")
      void navigate({
        to: "/tax-returns/$returnId/review/$section",
        params: { returnId, section: "documents" },
      });
    else if (next === "issues")
      void navigate({ to: "/tax-returns/$returnId/issues", params: { returnId } });
    else void navigate({ to: "/tax-returns/$returnId/activity", params: { returnId } });
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FeatureGate
        entitlement="tax_returns"
        fallback={<FlagOffState flag="tax_returns" label="Tax Returns" />}
      >
        <FeatureGate
          flag={REVIEW_FLAG}
          fallback={<FlagOffState flag={REVIEW_FLAG} label="Return review" />}
        >
          <WorkspaceScreen
            returnId={returnId}
            tab={tab}
            title={title}
            onTab={go}
            onAssistant={() => {
              void navigate({
                to: ".",
                search: search.ov === "assistant" ? {} : { ov: "assistant" },
              });
            }}
          >
            {children ?? (PLANNED_VISIBLE ? <EmptyState title="Not built yet" /> : null)}
          </WorkspaceScreen>
          {!FIXTURES && search.ov === "assistant" ? (
            <AssistantLive
              returnId={returnId}
              open
              onClose={() => {
                void navigate({ to: ".", search: {} });
              }}
            />
          ) : null}
        </FeatureGate>
      </FeatureGate>
    </div>
  );
}

export const taxReviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/$section",
  validateSearch,
  component: function TaxReviewPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    if (Prepare !== null) {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate
            entitlement="tax_returns"
            fallback={<FlagOffState flag="tax_returns" label="Tax Returns" />}
          >
            <FeatureGate
              flag={REVIEW_FLAG}
              fallback={<FlagOffState flag={REVIEW_FLAG} label="Return review" />}
            >
              <Suspense fallback={null}>
                <Prepare
                  onIssue={() => {
                    void navigate({ to: "/tax-returns/$returnId/issues", params: { returnId } });
                  }}
                />
              </Suspense>
            </FeatureGate>
          </FeatureGate>
        </div>
      );
    }
    const section = useParam("section");
    return (
      <Workspace tab="review" title="Review">
        <LiveSection section={section === "worksheets" ? "worksheets" : "review"} />
      </Workspace>
    );
  },
});

export const taxIssuesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/issues",
  validateSearch,
  component: function TaxIssuesPage(): JSX.Element {
    return (
      <Workspace tab="issues" title="Issues">
        {FIXTURES ? undefined : <LiveSection section="issues" />}
      </Workspace>
    );
  },
});

export const taxActivityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/activity",
  validateSearch,
  component: function TaxActivityPage(): JSX.Element {
    return (
      <Workspace tab="activity" title="Activity">
        {FIXTURES ? undefined : <LiveSection section="activity" />}
      </Workspace>
    );
  },
});

export const taxK1ResolverRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/k1-resolver/$activityId",
  validateSearch,
  component: function TaxK1ResolverPage(): JSX.Element {
    return <Workspace tab="review" title="K-1 treatment" />;
  },
});

export const taxResidencyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/residency",
  validateSearch,
  component: function TaxResidencyPage(): JSX.Element {
    return <Workspace tab="review" title="Residency" />;
  },
});

export const taxReviewRoutes = [
  taxReviewRoute,
  taxIssuesRoute,
  taxActivityRoute,
  taxK1ResolverRoute,
  taxResidencyRoute,
] as const;
