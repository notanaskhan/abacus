import { EmptyState, FlagOffState } from "@abacus/ui";
import { createRoute, redirect, useNavigate, useRouter } from "@tanstack/react-router";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { MANIFEST, type Manifest } from "../manifest";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// The close shell's route subtree (C-01-T12; C-01 §5; SPEC-655 AC-54). Lazy: the close screens
// load with their route, never in the initial bundle. One static route per close tab, so each
// screen has its own builder (link contract rule 2): Overview `/closes/$closeId` (CLS-02), Intake
// (CLS-03), Accounts (CLS-04) and an account's reconciliation (CLS-05), Review (CLS-06) and Flux
// (CLS-10); the plan editor sits at `/close-plans/$clientId` (CLS-09). Any other tab slug is
// validated in beforeLoad and lands on Overview. `/closes` stays the area landing until CLS-01
// (C-01-T33) routes it. Deliverables (CLS-08) is C-02's: its tab renders disabled (DV-6).

const Shell = lazyScreen(async () => (await import("../../screens/CLS-02")).CloseShell);

type Tab = "overview" | "intake" | "accounts" | "review" | "deliverables";

function CloseTabPage({ tab, screen }: { tab: Tab; screen: string }): JSX.Element {
  const closeId = useParam("closeId");
  const navigate = useNavigate();
  const router = useRouter();
  const go = (id: string, next: Tab): void => {
    const path = {
      overview: "/closes/$closeId",
      intake: "/closes/$closeId/intake",
      accounts: "/closes/$closeId/accounts",
      review: "/closes/$closeId/review",
      deliverables: "/closes/$closeId",
    }[next];
    void navigate({ to: path, params: { closeId: id } });
  };
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Shell
        closeId={closeId}
        tab={tab}
        screen={screen}
        onTab={(next) => {
          go(closeId, next);
        }}
        onClose={(id) => {
          go(id, tab);
        }}
        onBack={() => {
          // `/closes` is the area landing until CLS-01 routes it (C-01-T33): an untyped href.
          void router.navigate({ href: "/closes" });
        }}
      />
    </div>
  );
}

export const closeOverviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId",
  component: function CloseOverviewPage(): JSX.Element {
    return <CloseTabPage tab="overview" screen="CLS-02" />;
  },
});

export const closeIntakeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/intake",
  component: function CloseIntakePage(): JSX.Element {
    return <CloseTabPage tab="intake" screen="CLS-03" />;
  },
});

export const closeAccountsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/accounts",
  component: function CloseAccountsPage(): JSX.Element {
    return <CloseTabPage tab="accounts" screen="CLS-04" />;
  },
});

export const closeReconciliationRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/accounts/$accountRef",
  component: function CloseReconciliationPage(): JSX.Element {
    return <CloseTabPage tab="accounts" screen="CLS-05" />;
  },
});

export const closeReviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/review",
  component: function CloseReviewPage(): JSX.Element {
    return <CloseTabPage tab="review" screen="CLS-06" />;
  },
});

export const closeFluxRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/flux",
  component: function CloseFluxPage(): JSX.Element {
    return <CloseTabPage tab="review" screen="CLS-10" />;
  },
});

// Any other slug (a mistyped tab, or Deliverables before C-02) lands on Overview.
export const closeUnknownTabRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/$tab",
  beforeLoad: ({ params }) => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- the router's redirect is thrown by design
    throw redirect({ to: "/closes/$closeId", params: { closeId: params.closeId } });
  },
});

export const closePlanRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/close-plans/$clientId",
  component: function ClosePlanPage(): JSX.Element {
    const enabled = useFlag("closes.engine") === true;
    return (
      <div data-screen="CLS-09" className="flex min-h-0 flex-1 flex-col">
        {enabled ? (
          <EmptyState icon="layers" title={(MANIFEST as Manifest)["CLS-09"]?.name ?? "CLS-09"} />
        ) : (
          <FlagOffState flag="closes.engine" label="Closes" />
        )}
      </div>
    );
  },
});

export const closeRoutes = [
  closeOverviewRoute,
  closeIntakeRoute,
  closeAccountsRoute,
  closeReconciliationRoute,
  closeReviewRoute,
  closeFluxRoute,
  closeUnknownTabRoute,
  closePlanRoute,
] as const;
