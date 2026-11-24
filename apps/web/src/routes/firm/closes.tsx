import { closeSummaryOptions } from "@abacus/api-client/query";
import { FlagOffState, monthYear } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
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
// C-02-T17: CLS-07, the close's proposed entries, inside the shell's Review tab.
const Adjustments = lazyScreen(async () => (await import("../../screens/CLS-07")).CLS07);
// C-01-T38: CLS-05, an account's reconciliation, inside the shell's Accounts tab.
const Reconciliation = lazyScreen(async () => (await import("../../screens/CLS-05")).CLS05);

/** CLS-07 on the close's own work item (a close is one work item: `closes.work_item_id`). */
function AdjustmentsBody({
  closeId,
  onIssues,
  onFlux,
}: {
  closeId: string;
  onIssues: () => void;
  onFlux: () => void;
}): JSX.Element {
  const summary = useQuery(closeSummaryOptions({ path: { close_id: closeId } }));
  const navigate = useNavigate();
  const data = summary.data;
  return (
    <Adjustments
      workItemId={closeId}
      periodLabel={data ? monthYear(data.period) : ""}
      onIssues={onIssues}
      onFlux={onFlux}
      // C-02-T35: CLS-07d "View in ledger sync ›" opens CLS-11 for the close's entity.
      onLedgerSync={
        data?.client_entity_id
          ? () => {
              void navigate({
                to: "/clients/$clientId/entities/$entityId/ledger",
                params: { clientId: data.client_id, entityId: data.client_entity_id ?? "" },
                search: { close: closeId },
              });
            }
          : undefined
      }
    />
  );
}

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
// C-02-T23 (S51 partials): CLS-08's package inside the Deliverables tab.
const Deliverables = lazyScreen(async () => (await import("../../screens/CLS-08")).CLS08);

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
      deliverables: "/closes/$closeId/deliverables",
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
        ) : screen === "CLS-07" ? (
          <AdjustmentsBody
            closeId={closeId}
            onIssues={() => {
              go(closeId, "review");
            }}
            onFlux={() => {
              void navigate({ to: "/closes/$closeId/flux", params: { closeId } });
            }}
          />
        ) : screen === "CLS-10" ? (
          <Flux closeId={closeId} />
        ) : screen === "CLS-08" ? (
          <Deliverables closeId={closeId} />
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

export const closeAdjustmentsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/adjustments",
  component: function CloseAdjustmentsPage(): JSX.Element {
    return <CloseTabPage tab="review" screen="CLS-07" />;
  },
});

export const closeFluxRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/flux",
  component: function CloseFluxPage(): JSX.Element {
    return <CloseTabPage tab="review" screen="CLS-10" />;
  },
});

export const closeDeliverablesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/closes/$closeId/deliverables",
  component: function CloseDeliverablesPage(): JSX.Element {
    return <CloseTabPage tab="deliverables" screen="CLS-08" />;
  },
});

// Any other slug (a mistyped tab) lands on Overview.
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

// C-02-T35: CLS-11, a client entity's ledger sync console, in the Closes area behind
// `closes.gl_console`. `?close=` names the close it was opened from (the back chip), `?log=events`
// opens the Sync events segment (a2) and `?reconnect=1` the reconnect confirm (d2).
const LedgerConsole = lazyScreen(async () => (await import("../../screens/CLS-11")).CLS11);

interface LedgerSearch {
  close?: string;
  log?: "events";
  reconnect?: true;
}

function validateLedgerSearch(search: Record<string, unknown>): LedgerSearch {
  const out: LedgerSearch = {};
  if (typeof search.close === "string" && search.close !== "") out.close = search.close;
  if (search.log === "events") out.log = "events";
  if (search.reconnect === true || search.reconnect === "1" || search.reconnect === 1) {
    out.reconnect = true;
  }
  return out;
}

export const ledgerConsoleRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/entities/$entityId/ledger",
  validateSearch: validateLedgerSearch,
  component: function LedgerConsolePage(): JSX.Element {
    const enabled = useFlag("closes.gl_console") === true;
    const { clientId, entityId } = ledgerConsoleRoute.useParams();
    const search = ledgerConsoleRoute.useSearch();
    const navigate = useNavigate();
    if (!enabled) {
      return (
        <div data-screen="CLS-11" className="flex min-h-0 flex-1 flex-col">
          <FlagOffState flag="closes.gl_console" label="Ledger sync" />
        </div>
      );
    }
    const close = search.close;
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <LedgerConsole
          clientEntityId={entityId}
          closeId={close}
          log={search.log === "events" ? "events" : "batches"}
          reconnectOpen={search.reconnect === true}
          onLog={(log) => {
            void navigate({
              to: "/clients/$clientId/entities/$entityId/ledger",
              params: { clientId, entityId },
              search: {
                ...(close === undefined ? {} : { close }),
                ...(log === "events" ? { log } : {}),
              },
              replace: true,
            });
          }}
        />
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
  closeAdjustmentsRoute,
  closeFluxRoute,
  closeDeliverablesRoute,
  closeUnknownTabRoute,
  closePlanRoute,
  ledgerConsoleRoute,
] as const;
