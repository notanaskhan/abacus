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
import { EntitySection } from "./tax-returns";

// The return's review workspace (T-04-T12; T-04 §5): new routes in new files, each behind the
// `tax_returns` entitlement (T-06-T69: `tax.review_workspace` retired into it); without it every
// one shows F-05's off state and T-02's screens are unchanged. The sections' bodies are their screens' own
// (TAX-04 Review from T-04-T13; TAX-06 Issues, TAX-07 Activity, TXI-02 K-1 resolver and TXI-03
// residency after it); until then a fixture build draws "Not built yet". `?ov=assistant` opens
// TAX-08's panel over any section (P-10's dock).
//
//   /tax-returns/$returnId/review/$section     TAX-04 (prepare preset) / TAX-05 (review preset)
//   /tax-returns/$returnId/issues              TAX-06
//   /tax-returns/$returnId/activity            TAX-07
//   /tax-returns/$returnId/k1-resolver/$activityId   TXI-02
//   /tax-returns/$returnId/residency           TXI-03

// T-06-T69 (DEC-6024): the review workspace and T-07's sections are the `tax_returns`
// entitlement's (the retired `tax.review_workspace`, `tax.fiduciary_*` and `tax.estate_workpapers`
// flags); the workspace's one gate below covers every section.
export const REVIEW_ENTITLEMENT = "tax_returns";
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
type WorkspaceSearch = { ov?: string; ws?: string; clause?: string; row?: string };
// T-07-T21: TXT-01 `?clause=` lights a clause (a TXT-02 chip's link); TXT-02 `?row=` lights a row
// (TXT-01's Cited by). Both are labels, never paths: a short pattern, never the raw text.
const CLAUSE = /^[A-Za-z0-9 .()]{1,24}$/;
const ROW = /^[a-z0-9_.-]{1,60}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// `?ov=` keeps every overlay the host knows (SHL-10, SHL-12, SHL-15 from the live sections, and
// TAX-08's "assistant"); `?ws=<worksheet id>` opens TXI-01 on one worksheet (T-04-T29).
function validateSearch(search: Record<string, unknown>): WorkspaceSearch {
  return {
    ...(typeof search.ov === "string" && search.ov !== "" ? { ov: search.ov } : {}),
    // A worksheet id goes into an API path: a UUID only, never the URL's raw text.
    ...(typeof search.ws === "string" && UUID.test(search.ws) ? { ws: search.ws } : {}),
    ...(typeof search.clause === "string" && CLAUSE.test(search.clause)
      ? { clause: search.clause }
      : {}),
    ...(typeof search.row === "string" && ROW.test(search.row) ? { row: search.row } : {}),
  };
}

// T-04-T29 (TASK-6828): a live build hosts each section's live screen inside the frame; a
// fixture build keeps the artboards (TAX-04's Prepare preset above, "Not built yet" elsewhere).
const ReviewLive = lazyScreen(async () => (await import("../../screens/TAX-04/live")).ReviewLive);
const WorksheetsLive = lazyScreen(
  async () => (await import("../../screens/TAX-05/live")).WorksheetsLive,
);
const IssuesLive = lazyScreen(async () => (await import("../../screens/TAX-06/live")).IssuesLive);
// T-04-T40: TXI-02 in fixture mode.
const K1Resolver = lazyScreen(async () => (await import("../../screens/TXI-02")).K1Resolver);
// T-04-T41: TXI-03 in fixture mode.
const ResidencyAllocation = lazyScreen(
  async () => (await import("../../screens/TXI-03")).ResidencyAllocation,
);
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

// T-08-T22 (DEC-5938): TAX-10, the review's 2-Year Comparison sheet, behind `tax.two_year`.
const TwoYear = lazyScreen(async () => (await import("../../screens/TAX-10")).TAX10);

function LiveSection({
  section,
}: {
  section: "review" | "worksheets" | "issues" | "activity" | "two-year";
}): JSX.Element {
  const returnId = useParam("returnId");
  const engagementId = useEngagementOf(returnId);
  const search: WorkspaceSearch = useSearch({ strict: false });
  if (section === "issues") return <IssuesLive returnId={returnId} engagementId={engagementId} />;
  if (section === "activity") {
    return <ActivityLive returnId={returnId} engagementId={engagementId} />;
  }
  if (section === "two-year") {
    return <TwoYearSection returnId={returnId} />;
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

function TwoYearSection({ returnId }: { returnId: string }): JSX.Element {
  const navigate = useNavigate();
  return (
    <FeatureGate
      flag="tax.two_year"
      fallback={<FlagOffState flag="tax.two_year" label="2-Year Comparison" />}
    >
      <TwoYear
        returnId={returnId}
        onSheet={(sheet) => {
          if (sheet === "Worksheets") {
            void navigate({
              to: "/tax-returns/$returnId/review/$section",
              params: { returnId, section: "worksheets" },
            });
          } else if (sheet === "Leadsheets") {
            void navigate({
              to: "/tax-returns/$returnId/review/$section",
              params: { returnId, section: "leadsheets" },
            });
          }
        }}
      />
    </FeatureGate>
  );
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
    </div>
  );
}

// TXT-01 (T-07-T15): the trust's instrument under the 1041's Review (the workspace's
// `tax_returns` gate; T-06-T69); `?ov=signoff` opens SHL-12 at L3 on the interpretation.
const InstrumentScreen = lazyScreen(async () => (await import("../../screens/TXT-01")).TXT01);

export const taxInstrumentRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/instrument",
  validateSearch,
  component: function TaxInstrumentPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    const search: WorkspaceSearch = useSearch({ strict: false });
    return (
      <Workspace tab="review" title="Instrument">
        <InstrumentScreen
          returnId={returnId}
          {...(search.clause ? { clause: search.clause } : {})}
          onApprove={() => {
            void navigate({ to: ".", search: { ov: "signoff" } });
          }}
          onCitedBy={(target, ref) => {
            if (target === "trust_calculation") {
              void navigate({
                to: "/tax-returns/$returnId/review/trust-calculation",
                params: { returnId },
                search: { row: ref },
              });
            }
          }}
        />
      </Workspace>
    );
  },
});

// TXT-02 (T-07-T17): the fiduciary calc tree under the 1041's Review; a clause chip opens TXT-01
// with the clause lit (`?clause=`); Sign off… opens SHL-12 at L2.
const TrustCalculationScreen = lazyScreen(
  async () => (await import("../../screens/TXT-02")).TXT02,
);

export const taxTrustCalculationRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/trust-calculation",
  validateSearch,
  component: function TaxTrustCalculationPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    const search: WorkspaceSearch = useSearch({ strict: false });
    return (
      <Workspace tab="review" title="Trust Calculation">
        <TrustCalculationScreen
          returnId={returnId}
          {...(search.row ? { row: search.row } : {})}
          onSignOff={() => {
            void navigate({ to: ".", search: { ov: "signoff" } });
          }}
          onClause={(clause) => {
            void navigate({
              to: "/tax-returns/$returnId/review/instrument",
              params: { returnId },
              search: { clause },
            });
          }}
        />
      </Workspace>
    );
  },
});

// TXT-03 (S47, TASK-8352): beneficiaries, K-1s and the 65-day election under the 1041's Review;
// a package opens TXP-12, Release K-1s… goes to TXP-12's release.
const BeneficiariesScreen = lazyScreen(
  async () => (await import("../../screens/TXT-03/live")).TXT03,
);

export const taxBeneficiariesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/beneficiaries",
  validateSearch,
  component: function TaxBeneficiariesPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    const toPackages = (): void => {
      void navigate(to.TXP12({ returnId }));
    };
    return (
      <Workspace tab="review" title="Beneficiaries">
        <BeneficiariesScreen returnId={returnId} onRelease={toPackages} onPackage={toPackages} />
      </Workspace>
    );
  },
});

// TXT-04 (S47, TASK-8353): the estate workpapers (706 / 709) under the return's Review.
const EstateScreen = lazyScreen(async () => (await import("../../screens/TXT-04/live")).TXT04);

export const taxEstateRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/estate",
  validateSearch,
  component: function TaxEstatePage(): JSX.Element {
    const returnId = useParam("returnId");
    return (
      <Workspace tab="review" title="Estate workpapers">
        <EstateScreen returnId={returnId} />
      </Workspace>
    );
  },
});

// T-06-T45 (DEC-5937): TXP-13 d, the 1120 workpapers fed by an audit hand-off, behind
// `tax.tb_handoff` (the landing 404s with it off). The static segment outranks `$section`.
const Txp13 = lazyScreen(async () => (await import("../../screens/TXP-13")).TXP13);

export const taxWorkpapers1120Route = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/workpapers",
  component: function TaxWorkpapers1120Page(): JSX.Element {
    const returnId = useParam("returnId");
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          entitlement="tax_returns"
          fallback={<FlagOffState flag="tax_returns" label="Tax Returns" />}
        >
          <FeatureGate
            flag="tax.tb_handoff"
            fallback={<FlagOffState flag="tax.tb_handoff" label="Hand-off workpapers" />}
          >
            <Txp13 returnId={returnId} />
          </FeatureGate>
        </FeatureGate>
      </div>
    );
  },
});

export const taxReviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/$section",
  validateSearch,
  component: function TaxReviewPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    const section = useParam("section");
    if (Prepare !== null) {
      // T-05-T68: a fixture build dispatches a 1065 to its entity screen too (J08's fixture walk);
      // a 1040 or 1041, or the entity workspace off, keeps TAX-04's artboard.
      const prepare = (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate
            entitlement="tax_returns"
            fallback={<FlagOffState flag="tax_returns" label="Tax Returns" />}
          >
            <Suspense fallback={null}>
              <Prepare
                onIssue={() => {
                  void navigate({ to: "/tax-returns/$returnId/issues", params: { returnId } });
                }}
              />
            </Suspense>
          </FeatureGate>
        </div>
      );
      return (
        <EntitySection returnId={returnId} slug="review" review={section} fallback={prepare} />
      );
    }
    return (
      <EntitySection
        returnId={returnId}
        slug="review"
        review={section}
        fallback={
          <Workspace tab="review" title="Review">
            <LiveSection
              section={
                section === "worksheets"
                  ? "worksheets"
                  : section === "two-year"
                    ? "two-year"
                    : "review"
              }
            />
          </Workspace>
        }
      />
    );
  },
});

export const taxIssuesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/issues",
  validateSearch,
  component: function TaxIssuesPage(): JSX.Element {
    const returnId = useParam("returnId");
    return (
      <EntitySection
        returnId={returnId}
        slug="issues"
        fallback={
          <Workspace tab="issues" title="Issues">
            {FIXTURES ? undefined : <LiveSection section="issues" />}
          </Workspace>
        }
      />
    );
  },
});

export const taxActivityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/activity",
  validateSearch,
  component: function TaxActivityPage(): JSX.Element {
    const returnId = useParam("returnId");
    return (
      <EntitySection
        returnId={returnId}
        slug="activity"
        fallback={
          <Workspace tab="activity" title="Activity">
            {FIXTURES ? undefined : <LiveSection section="activity" />}
          </Workspace>
        }
      />
    );
  },
});

export const taxK1ResolverRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/k1-resolver/$activityId",
  validateSearch,
  component: function TaxK1ResolverPage(): JSX.Element {
    // T-04-T40: the resolver in fixture mode (TXI-02 a); the live host lands with T-04-T38.
    return (
      <Workspace tab="review" title="K-1 treatment">
        {FIXTURES ? <K1Resolver frame="a" /> : undefined}
      </Workspace>
    );
  },
});

export const taxResidencyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/residency",
  validateSearch,
  component: function TaxResidencyPage(): JSX.Element {
    // T-04-T41: TXI-03 in fixture mode (a); the live host reads GET …/residency (T-04-T39).
    return (
      <Workspace tab="review" title="Residency">
        {FIXTURES ? <ResidencyAllocation frame="a" /> : undefined}
      </Workspace>
    );
  },
});

export const taxReviewRoutes = [
  taxEstateRoute,
  taxBeneficiariesRoute,
  taxInstrumentRoute,
  taxTrustCalculationRoute,
  taxWorkpapers1120Route,
  taxReviewRoute,
  taxIssuesRoute,
  taxActivityRoute,
  taxK1ResolverRoute,
  taxResidencyRoute,
] as const;
