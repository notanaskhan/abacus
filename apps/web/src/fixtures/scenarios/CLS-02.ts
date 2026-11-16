// The close shell and CLS-02 Overview fixture scenarios (C-01-T12, C-01-T34): Copperleaf August
// with `closes.engine` on (and off, the C-20 flag-off state inside the frame), and the Overview's
// five frames: A Run 2 running at 9:24 AM (6 of 9, 3 at once), B complete with exceptions at 9:40
// AM (9 of 9, 7 open), C idle (September, not started, "Ready to run 22 tasks"), D waiting on the
// Square transfer's treatment card, E the Shopify task stopped. Every figure is the figure book's
// (fixtures/seed/close-book.ts, C-01-T13).
import type { CloseRunOut, CloseRunsOut, CloseSummaryOut } from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { copperleafRun2, copperleafRuns } from "../seed/close-book";
import { copperleafAugust } from "../seed/closes";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function frame(
  state: string,
  on: boolean,
  run?: () => CloseRunOut | null,
  runs?: () => CloseRunsOut,
  summary?: () => CloseSummaryOut,
): Scenario {
  return {
    ...E0,
    state,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? E0.persona ?? "");
          return json({ ...base, flags: { ...base.flags, "closes.engine": on } });
        },
        ...(summary ? { "GET /v1/closes/{close_id}": () => json(summary()) } : {}),
        ...(runs ? { "GET /v1/closes/{close_id}/runs": () => json(runs()) } : {}),
        ...(run ? { "GET /v1/closes/{close_id}/runs/{run_no}": () => json(run()) } : {}),
      };
    },
  };
}

/** B: 9:40 AM, every task finished; the Amex, Shopify and fixed-asset rows settle. */
export function completeRun(): CloseRunOut {
  const r = copperleafRun2();
  const settle: Record<string, [string, number]> = {
    "Amex Business Card ••1009": ["1 open · Reconciled with feed through Aug 31", 1],
    Shopify: ["No issues · Reconciled", 0],
    "Fixed asset register": ["1 open · capitalization question pending client answer", 1],
  };
  const groups = r.groups.map((g) => ({
    ...g,
    procedures: g.procedures.map((p) => {
      if (p.status !== "running") return p;
      const [meta, open] = settle[p.label] ?? ["No issues", 0];
      return {
        ...p,
        status: open > 0 ? ("needs_attention" as const) : ("done" as const),
        meta,
        open_count: open,
      };
    }),
  }));
  return {
    ...r,
    status: "complete_with_exceptions",
    finished_at: "2026-09-14T09:40:00-05:00",
    done: r.total,
    running: 0,
    groups,
  };
}

/** D: the Square group holds on its treatment card. */
export function waitingRun(): CloseRunOut {
  const r = copperleafRun2();
  return {
    ...r,
    status: "needs_input",
    running: 0,
    groups: r.groups.map((g) =>
      g.key === "third_party_sales"
        ? {
            ...g,
            procedures: g.procedures.map((p) =>
              p.label === "Square"
                ? {
                    ...p,
                    status: "needs_attention" as const,
                    meta: "Waiting on 1 answer",
                    decision_card_id: "00000000-0000-4000-8000-00000000d0c1",
                  }
                : { ...p, status: "queued" as const, meta: null },
            ),
          }
        : g,
    ),
  };
}

/** E: Shopify stopped: the payout report misses Aug 30–31. */
export function failedRun(): CloseRunOut {
  const r = copperleafRun2();
  return {
    ...r,
    status: "failed",
    running: 0,
    groups: r.groups.map((g) => ({
      ...g,
      procedures: g.procedures.map((p) =>
        p.label === "Shopify"
          ? {
              ...p,
              status: "failed" as const,
              failure: "The payout report covers Aug 1–29; Aug 30–31 payouts are missing",
            }
          : p.status === "running"
            ? { ...p, status: "done" as const, meta: "No issues" }
            : p,
      ),
    })),
  };
}

/** C: September, not started, before BD1. */
function september(): CloseSummaryOut {
  return {
    ...copperleafAugust(),
    period: "2026-09",
    status: "not_started",
    open_issues: 0,
    documents_in_binder: 0,
    accounts_reconciled: 0,
    due_on: "2026-10-12",
    days_past_due: null,
    requests_publish_on: "2026-10-01",
    run_no: 0,
    portal: { ...copperleafAugust().portal, requests_pending: 8 },
  };
}

export const scenarios = defineScenarios({
  shell: frame("shell", true),
  off: frame("off", false),
  "overview-a": frame("overview-a", true),
  "overview-b": frame("overview-b", true, completeRun, () => ({
    ...copperleafRuns(),
    items: copperleafRuns().items.map((i) =>
      i.run_no === 2 ? { ...i, status: "complete_with_exceptions" as const } : i,
    ),
  })),
  "overview-c": frame(
    "overview-c",
    true,
    () => null,
    () => ({ items: [], ready_to_run: 22 }),
    september,
  ),
  "overview-d": frame("overview-d", true, waitingRun, () => ({
    ...copperleafRuns(),
    items: copperleafRuns().items.map((i) =>
      i.run_no === 2 ? { ...i, status: "needs_input" as const } : i,
    ),
  })),
  "overview-e": frame("overview-e", true, failedRun, () => ({
    ...copperleafRuns(),
    items: copperleafRuns().items.map((i) =>
      i.run_no === 2 ? { ...i, status: "failed" as const } : i,
    ),
  })),
});

export type ShellState = keyof typeof scenarios;
