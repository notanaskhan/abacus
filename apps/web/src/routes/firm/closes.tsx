import { FlagOffState } from "@abacus/ui";
import { createRoute, redirect, useNavigate, useRouter } from "@tanstack/react-router";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// The close shell's route subtree (C-01-T12; C-01 §5; SPEC-655 AC-54). Lazy: the close screens
// load with their route, never in the initial bundle. One static route per close tab, so each
// screen has its own builder (link contract rule 2): Overview `/closes/$closeId` (CLS-02), Intake
// (CLS-03), Accounts (CLS-04) and an account's reconciliation (CLS-05), Review (CLS-06) and Flux
// (CLS-10); the plan editor sits at `/close-plans/$clientId` (CLS-09). Any other tab slug is
// validated in beforeLoad and lands on Overview. `/closes` is CLS-01 (C-01-T33). Deliverables (CLS-08) is C-02's: its tab renders disabled (DV-6).

const Shell = lazyScreen(async () => (await import("../../screens/CLS-02")).CloseShell);
// C-01-T35: CLS-03's Intake body inside the shell.
const Intake = lazyScreen(async () => (await import("../../screens/CLS-03")).CLS03);
// C-01-T37: CLS-04's Accounts body inside the shell.
const Accounts = lazyScreen(async () => (await import("../../screens/CLS-04")).CLS04);
// C-01-T39: CLS-06's Review body inside the shell.
const Review = lazyScreen(async () => (await import("../../screens/CLS-06")).CLS06);
// C-01-T38: CLS-05, an account's reconciliation, inside the shell's Accounts tab.
const Reconciliation = lazyScreen(async () => (await import("../../screens/CLS-05")).CLS05);

function ReconciliationBody({ closeId, onReview }: { closeId: string; onReview: () => void }) {
  const accountRef = useParam("accountRef");
  const navigate = useNavigate();
  return (
    <Reconciliation
      closeId={closeId}
      accountRef={accountRef}
      onAccount={(ref) => {
        void navigate({
          to: "/closes/$closeId/accounts/$accountRef",
          params: { closeId, accountRef: ref },
        });
      }}
      onIssue={onReview}
    />
  );
}
// C-01-T34: CLS-02's Overview body inside the shell.
const Overview = lazyScreen(async () => (await import("../../screens/CLS-02")).CloseOverview);
const Index = lazyScreen(async () => (await import("../../screens/CLS-01")).CLS01);
// C-01-T36: CLS-09's close plan editor, keyed by the client.
// C-01-T40: CLS-10's flux inside the Review tab.
const Flux = lazyScreen(async () => (await import("../../screens/CLS-10")).CLS10);
const Plan = lazyScreen(async () => (await import("../../screens/CLS-09")).CLS09);

// CLS-01 (C-01-T33): `/closes` behind `closes.engine`. The filters are the search params
// (`period`, `status`, `preparer`, `reviewer`, `attest`, `q`), so a filtered view is a link. The
// words are kept here because routes never reach into a domain.
const PERIODS = ["2026-06", "2026-07", "2026-08", "2026-09"] as const;
const STATUSES = ["not_started", "in_progress", "in_review", "delivered", "past_due"] as const;
const one = <T extends string>(list: readonly T[], v: unknown): v is T =>
  typeof v === "string" && (list as readonly string[]).includes(v);

interface ClosesSearch {
  period?: (typeof PERIODS)[number];
  status?: (typeof STATUSES)[number];
  preparer?: string;
  reviewer?: string;
  attest?: boolean;
  q?: string;
}

function validateClosesSearch(search: Record<string, unknown>): ClosesSearch {
  const text = (v: unknown): string | undefined =>
    typeof v === "string" && v !== "" ? v : undefined;
  const out: ClosesSearch = {};
  if (one(PERIODS, search.period)) out.period = search.period;
  if (one(STATUSES, search.status)) out.status = search.status;
  const preparer = text(search.preparer);
  if (preparer !== undefined) out.preparer = preparer;
  const reviewer = text(search.reviewer);
  if (reviewer !== undefined) out.reviewer = reviewer;
  if (search.attest === true || search.attest === "true") out.attest = true;
  const q = text(search.q);
  if (q !== undefined) out.q = q;
  return out;
}

export const closesIndexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes",
  validateSearch: validateClosesSearch,
  component: function ClosesIndexPage(): JSX.Element {
    const enabled = useFlag("closes.engine") === true;
    const search = closesIndexRoute.useSearch();
    const navigate = useNavigate();
    if (!enabled) {
      return (
        <div data-screen="CLS-01" className="flex min-h-0 flex-1 flex-col">
          <FlagOffState flag="closes.engine" label="Closes" />
        </div>
      );
    }
    const filters = {
      period: search.period ?? "2026-08",
      status: search.status ?? null,
      preparer: search.preparer ?? null,
      reviewer: search.reviewer ?? null,
      attest: search.attest ?? null,
      q: search.q ?? "",
    };
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <Index
          filters={filters}
          onFilters={(next) =>
            void navigate({
              to: "/closes",
              search: {
                ...(next.period === "2026-08" ? {} : { period: next.period }),
                ...(next.status === null ? {} : { status: next.status }),
                ...(next.preparer === null ? {} : { preparer: next.preparer }),
                ...(next.reviewer === null ? {} : { reviewer: next.reviewer }),
                ...(next.attest === null ? {} : { attest: next.attest }),
                ...(next.q.trim() === "" ? {} : { q: next.q }),
              },
              replace: true,
            })
          }
          // C-01-T42: CLS-01 opens CLS-02 and CLS-09 itself (to.CLS02, to.CLS09).
        />
      </div>
    );
  },
});

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
          void router.navigate({ to: "/closes" });
        }}
      >
        {screen === "CLS-02" ? (
          // C-01-T43: CLS-02, CLS-04 and CLS-10 open their designed links themselves (to.<ID>).
          <Overview closeId={closeId} />
        ) : screen === "CLS-03" ? (
          <Intake closeId={closeId} />
        ) : screen === "CLS-06" ? (
          <Review
            closeId={closeId}
            onOpen={(target) => {
              if (target === "CLS-10") {
                void navigate({ to: "/closes/$closeId/flux", params: { closeId } });
              }
            }}
          />
        ) : screen === "CLS-05" ? (
          <ReconciliationBody
            closeId={closeId}
            onReview={() => {
              go(closeId, "review");
            }}
          />
        ) : screen === "CLS-04" ? (
          <Accounts closeId={closeId} />
        ) : screen === "CLS-10" ? (
          <Flux closeId={closeId} />
        ) : undefined}
      </Shell>
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
    const clientId = useParam("clientId");
    const router = useRouter();
    return (
      <div data-screen="CLS-09" className="flex min-h-0 flex-1 flex-col">
        {enabled ? (
          <Plan
            clientId={clientId}
            onBack={() => {
              router.history.back();
            }}
          />
        ) : (
          <FlagOffState flag="closes.engine" label="Closes" />
        )}
      </div>
    );
  },
});

export const closeRoutes = [
  closesIndexRoute,
  closeOverviewRoute,
  closeIntakeRoute,
  closeAccountsRoute,
  closeReconciliationRoute,
  closeReviewRoute,
  closeFluxRoute,
  closeUnknownTabRoute,
  closePlanRoute,
] as const;
