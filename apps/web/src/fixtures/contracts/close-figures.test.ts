// C-01-T13 (TASK-8031; SPEC-655; C-01 §5.3): the Copperleaf CAS figure book against the screens'
// fixtures. The book is backend/tests/golden/scenario/brightwater_hale/copperleaf_close_figures.json,
// transcribed from the epic and the handoff; backend/tests/golden/scenario/test_c01t13_close_figures.py
// foots the synthetic close slice against the same book, so a figure that drifts on either side
// fails. The reconciled percentage is code's (half up), never the artboard's cell (DEC-5019).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  closeRows,
  closesPortfolio,
  copperleafFlux,
  copperleafIssues,
  copperleafPlanV3,
  copperleafPortalQuestions,
  copperleafReconciliation4410,
  copperleafRun2,
  copperleafRuns,
  PEOPLE,
  runningCloses,
} from "../seed/close-book";
import { copperleafAugust } from "../seed/closes";

type BookRow = [
  string,
  string,
  number,
  number,
  number,
  string,
  number | null,
  string,
  string,
  boolean,
];

interface Book {
  client: string;
  portfolio: {
    closes: number;
    tiles: Record<string, number>;
    open_issues: number;
    past_due: number;
    running: number;
    rows: BookRow[];
    initials: Record<string, string>;
  };
  record: Record<string, number | string>;
  runs: {
    run_1: { total: number; done: number };
    run_2: {
      total: number;
      done: number;
      running: number;
      open_items: number;
      groups: [string, string, number, number][];
    };
  };
  issues: {
    open: number;
    medium: number;
    low: number;
    notes: number;
    items: [string, string, string, string, boolean][];
  };
  reconciliation_4410: Record<string, string | number | unknown[]>;
  flux: {
    tested: number;
    over: number;
    lines: [string, string, string, string, string][];
    payroll_drivers: [string, string][];
    net_income: [string, string];
  };
  plan: {
    procedures: number;
    manager: number;
    senior: number;
    requests_per_month: number;
    rows: [string, string, string, string, string][];
    request_templates: string[];
  };
  portal: { questions: number };
}

const here = dirname(fileURLToPath(import.meta.url));
const BOOK = JSON.parse(
  readFileSync(
    join(
      here,
      "..",
      "..",
      "..",
      "..",
      "..",
      "backend",
      "tests",
      "golden",
      "scenario",
      "brightwater_hale",
      "copperleaf_close_figures.json",
    ),
    "utf-8",
  ),
) as Book;
const cents = (s: string | null | undefined) => Math.round(Number(s) * 100);

describe("CLS-01 portfolio", () => {
  const list = closesPortfolio();

  it("22 closes in tiles 3 · 11 · 5 · 3", () => {
    expect(list.items).toHaveLength(BOOK.portfolio.closes);
    expect(list.tiles).toEqual(BOOK.portfolio.tiles);
  });

  it("22 closes · 51 open issues · 2 past due · 3 running", () => {
    expect(list.summary).toEqual({
      open_issues: BOOK.portfolio.open_issues,
      past_due: BOOK.portfolio.past_due,
      running: BOOK.portfolio.running,
    });
    expect(runningCloses().items).toHaveLength(BOOK.portfolio.running);
  });

  it("every row matches the book", () => {
    closeRows().forEach((row, i) => {
      const [client, status, rec, total, issues, due, pastDue, prep, rev, running] =
        BOOK.portfolio.rows[i]!;
      expect([row.client_name, row.status, row.accounts_reconciled, row.accounts_total]).toEqual([
        client,
        status,
        rec,
        total,
      ]);
      expect([row.open_issues, row.due_on, row.days_past_due ?? null]).toEqual([
        issues,
        due,
        pastDue,
      ]);
      expect([row.preparer?.initials, row.reviewer?.initials, row.running]).toEqual([
        prep,
        rev,
        running,
      ]);
      expect(row.reconciled_pct).toBe(Math.round((rec * 100) / total));
      expect(row.attest).toBe(false);
    });
    expect(PEOPLE).toEqual(BOOK.portfolio.initials);
  });

  it("filters: In progress 11, past due C1 and C11, no attest clients", () => {
    expect(closesPortfolio((r) => r.status === "in_progress").items).toHaveLength(11);
    expect(
      closesPortfolio((r) => r.days_past_due != null).items.map((r) => r.client_name),
    ).toEqual([BOOK.client, "Bluebird Bakery Co."]);
    expect(closesPortfolio((r) => r.attest).items).toHaveLength(0);
  });
});

describe("CLS-02 record and runs", () => {
  it("the record bar reads 7 · 58 · 43% (9 / 21) · 4 days", () => {
    const rec = copperleafAugust();
    expect(rec.client_name).toBe(BOOK.client);
    expect(rec.open_issues).toBe(BOOK.record.open_issues);
    expect(rec.documents_in_binder).toBe(BOOK.record.documents_in_binder);
    expect([rec.accounts_reconciled, rec.accounts_total]).toEqual([
      BOOK.record.accounts_reconciled,
      BOOK.record.accounts_total,
    ]);
    expect(rec.days_past_due).toBe(BOOK.record.days_past_due);
    expect(closeRows()[0]!.reconciled_pct).toBe(BOOK.record.reconciled_pct);
  });

  it("Run 2 = 2 + 3 + 2 + 1 + 1 = 9, 6 done, 3 at once, 4 open items", () => {
    const run = copperleafRun2();
    const book = BOOK.runs.run_2;
    expect(run.groups.map((g) => [g.key, g.label, g.procedures.length])).toEqual(
      book.groups.map(([k, l, n]) => [k, l, n]),
    );
    expect([run.total, run.done, run.running]).toEqual([book.total, book.done, book.running]);
    expect(
      run.groups.flatMap((g) => g.procedures).reduce((n, p) => n + (p.open_count ?? 0), 0),
    ).toBe(book.open_items);
    expect(copperleafRuns().items.map((r) => r.total)).toEqual([
      book.total,
      BOOK.runs.run_1.total,
    ]);
  });
});

describe("CLS-05 ••4410", () => {
  const rec = copperleafReconciliation4410();
  const book = BOOK.reconciliation_4410;

  it("balance per bank + deposit in transit − outstanding checks = adjusted bank", () => {
    const bank = rec.items
      .filter((i) => i.side === "bank")
      .reduce((n, i) => n + cents(i.amount), 0);
    expect(cents(rec.balance_per_bank) + bank).toBe(cents(rec.adjusted_bank));
    expect(cents(rec.adjusted_bank)).toBe(cents(book.adjusted_bank as string));
    const checks = rec.items.filter((i) => i.kind === "outstanding_check");
    expect(-checks.reduce((n, i) => n + cents(i.amount), 0)).toBe(
      cents(book.outstanding_checks as string),
    );
  });

  it("books + the unrecorded refund = adjusted books; difference 0.00, tie", () => {
    const book_ = rec.items
      .filter((i) => i.side === "book")
      .reduce((n, i) => n + cents(i.amount), 0);
    expect(cents(rec.book_balance) + book_).toBe(cents(rec.adjusted_book));
    expect(cents(rec.adjusted_bank) - cents(rec.adjusted_book)).toBe(0);
    expect([rec.difference, rec.tally]).toEqual([book.difference, "tie"]);
  });

  it("#2281 is 193 days and the only stale item; two open items", () => {
    expect(rec.items.filter((i) => i.stale).map((i) => [i.ref, i.days_at_period_end])).toEqual([
      ["#2281", 193],
    ]);
    expect(rec.items.filter((i) => i.issue_id != null)).toHaveLength(book.open_items as number);
  });
});

describe("CLS-06 review", () => {
  it("Medium 2 + Low 5 = 7; 4 notes uncounted", () => {
    const issues = copperleafIssues();
    expect(issues.open).toBe(BOOK.issues.open);
    expect(issues.by_severity).toEqual({ medium: BOOK.issues.medium, low: BOOK.issues.low });
    expect(issues.notes).toBe(BOOK.issues.notes);
    expect(
      issues.items.map((i) => [i.severity, i.issue_class, i.title, i.waiting_on_client]),
    ).toEqual(BOOK.issues.items.map(([s, c, t, , w]) => [s, c, t, w]));
    expect(issues.open).toBe(copperleafAugust().open_issues);
  });
});

describe("CLS-10 flux", () => {
  const flux = copperleafFlux();

  it("13 lines tested, 2 over both thresholds", () => {
    expect(flux.tested).toBe(BOOK.flux.tested);
    expect(flux.lines.filter((l) => l.test === "over_both")).toHaveLength(BOOK.flux.over);
    flux.lines.forEach((line, i) => {
      const [key, caption, prior, current, test] = BOOK.flux.lines[i]!;
      expect([
        line.line_key,
        line.caption,
        cents(line.prior),
        cents(line.current),
        line.test,
      ]).toEqual([key, caption, cents(prior), cents(current), test]);
    });
  });

  it("Payroll +7,670 (12.5%) = 4,350 + 1,850 + 1,470; Repairs +2,560 (400.0%)", () => {
    const payroll = flux.lines.find((l) => l.line_key === "payroll")!;
    expect([cents(payroll.change), payroll.change_pct]).toEqual([767_000, "12.5"]);
    expect(payroll.drivers!.reduce((n, d) => n + cents(d.amount), 0)).toBe(cents(payroll.change));
    expect(payroll.drivers!.map((d) => [d.label, String(cents(d.amount) / 100)])).toEqual(
      BOOK.flux.payroll_drivers,
    );
    const repairs = flux.lines.find((l) => l.line_key === "repairs_maintenance")!;
    expect([cents(repairs.change), repairs.change_pct, repairs.status]).toEqual([
      256_000,
      "400.0",
      "unexplained",
    ]);
    expect(flux.unexplained).toBe(1);
  });

  it("net income 31,455 → 27,795", () => {
    const by = (key: "prior" | "current", pick: (k: string) => boolean) =>
      flux.lines.filter((l) => pick(l.line_key)).reduce((n, l) => n + cents(l[key]), 0);
    const net = (key: "prior" | "current") =>
      by(key, (k) => k === "revenue") - by(key, (k) => k !== "revenue");
    expect([net("prior"), net("current")]).toEqual(BOOK.flux.net_income.map(cents));
  });
});

describe("CLS-09 plan and POR-11", () => {
  it("v3: 23 = Manager 8 + Senior 15; 8 requests a month", () => {
    const plan = copperleafPlanV3();
    expect(plan.tally).toEqual({
      procedures: BOOK.plan.procedures,
      manager: BOOK.plan.manager,
      senior: BOOK.plan.senior,
      requests_per_month: BOOK.plan.requests_per_month,
    });
    const key = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    expect(
      plan.rows.map((r) => [
        key(r.account_class),
        r.account_name,
        r.procedure,
        r.source,
        r.review_level,
      ]),
    ).toEqual(BOOK.plan.rows);
    expect(plan.request_templates.map((t) => t.title)).toEqual(BOOK.plan.request_templates);
  });

  it("three transaction questions, client words only", () => {
    const qs = copperleafPortalQuestions();
    expect(qs.items).toHaveLength(BOOK.portal.questions);
    for (const q of qs.items) expect(q.client_wording).not.toMatch(/Accrued|severity|agent/i);
  });
});
