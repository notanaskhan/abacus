// P-01-T07 footings for SHL-04: "The fixture footings hold (PBC 11 → 12 of 24, $16,812,400.00)".
// Every figure the spec, the revision and the README call out is tied to the seed here, with
// format.ts and bigint decimals, never floats.
import { longDate, prose, time } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { getSeed } from "./seed";
import {
  ACCEPT_RECEIPT,
  PREFERENCE_KINDS,
  R2_ROWS,
  RAJ_ROW,
  ROWS,
  ROW_D_REQUEST,
  SHL04_INSTANT,
  SHL04_R2_INSTANT,
  pageOf,
  requestIdOf,
  toWire,
} from "./seed/notifications";

const seed = getSeed();
const A1 = seed.engagementIds.A1 ?? "";
const northwind = seed.requestItems[A1] ?? [];
const row = (key: string) => ROWS.find((r) => r.row === key);
const received = (items: readonly { status: string }[]) =>
  items.filter((r) => r.status === "received").length;

describe("PBC 11 → 12 of 24", () => {
  it("E0 reads 11 of 24 received, with the certified trust report Uploaded – needs review", () => {
    expect([received(northwind), northwind.length]).toEqual([11, 24]);
    const trust = northwind.find((r) => r.description === ROW_D_REQUEST);
    expect(trust?.status).toBe("uploaded");
    expect(row("d")?.context).toContain(`‘${ROW_D_REQUEST}’`);
    expect(row("d")?.context).toContain("Uploaded – needs review");
  });

  it("row d points at that request, and accepting it makes 12 of 24", () => {
    const d = row("d");
    if (d === undefined) throw new Error("no row d");
    const wire = toWire(seed, d);
    expect(wire.facts.request_item_id).toBe(requestIdOf(seed, ROW_D_REQUEST));
    const after = northwind.map((r) =>
      r.id === wire.facts.request_item_id ? { ...r, status: "received" } : r,
    );
    expect([received(after), after.length]).toEqual([12, 24]);
  });
});

describe("$16,812,400.00", () => {
  it("row c agrees to Harborline net trust assets, the seed's unadjusted net assets to the cent", () => {
    const figure = seed.figures.northwind.netAssetsUnadjusted ?? "";
    expect(prose(figure)).toBe("$16,812,400.00");
    expect(row("c")?.context).toContain(`net trust assets ${prose(figure)}`);
  });
});

describe("times and day groups", () => {
  it("every row's time label is its instant in the firm's zone", () => {
    for (const r of [...ROWS, ...R2_ROWS, RAJ_ROW]) {
      expect(time(r.createdAt, { tz: seed.firm.timeZone }), r.row).toBe(r.timeLabel);
    }
  });

  it("Today is the clock's day; Friday, September 11 and Monday, September 28 are theirs", () => {
    const dayOf = (iso: string) => longDate(iso, { tz: seed.firm.timeZone });
    for (const r of ROWS) {
      const expected = r.day === "Today" ? dayOf(SHL04_INSTANT) : "September 11, 2026";
      expect(dayOf(r.createdAt), r.row).toBe(expected);
    }
    for (const r of R2_ROWS) {
      const expected = r.day === "Today" ? dayOf(SHL04_R2_INSTANT) : "September 28, 2026";
      expect(dayOf(r.createdAt), r.row).toBe(expected);
    }
  });

  it("TPL-02 ties: TB complete 9:26, Keystone 8:47 Received ✓, Harborline 8:52", () => {
    expect(row("c")?.timeLabel).toBe("9:26 AM");
    expect(row("g")?.timeLabel).toBe("8:47 AM");
    expect(row("g")?.context).toContain("Received ✓");
    expect(row("d")?.timeLabel).toBe("8:52 AM");
  });

  it("the report target is 28 days out: report Oct 9, Form 5500 due Oct 15", () => {
    const i = row("i");
    const days =
      (Date.parse("2026-10-09T09:00:00-05:00") - Date.parse(i?.createdAt ?? "")) / 86_400_000;
    expect(days).toBe(28);
    expect(i?.title).toBe("Report target in 28 days");
    expect(i?.context).toContain("report Oct 9");
    expect(i?.context).toContain("due Oct 15");
  });
});

describe("tabs, counts and unread", () => {
  const hannah = ROWS.map((r) => toWire(seed, r));

  it("a: 4 unread; Approvals 3 (rows a, b and d); Mentions 1", () => {
    const page = pageOf(hannah, "all");
    expect(page.items).toHaveLength(9);
    expect(page.unread_count).toBe(4);
    expect(page.counts).toEqual({ approvals: 3, mentions: 1, client_activity: 0 });
    const approvals = pageOf(hannah, "approvals").items.map((n) => n.facts.title);
    expect(approvals).toEqual([row("a")?.title, row("b")?.title, row("d")?.title]);
  });

  it("c: row d becomes the receipt, drops out of Approvals and is read", () => {
    const after = ROWS.map((r) => toWire(seed, r, { accepted: true }));
    const d = after.find((n) => n.facts.receipt !== undefined);
    expect(d?.facts.receipt).toBe(ACCEPT_RECEIPT);
    expect(d?.inline_actions).toEqual([]);
    expect(pageOf(after, "all").counts.approvals).toBe(2);
    expect(pageOf(after, "all").unread_count).toBe(3);
  });

  it("g: one row of each R2 kind, 2 unread; trigger rows say a trigger started them", () => {
    const page = pageOf(
      R2_ROWS.map((r) => toWire(seed, r)),
      "all",
    );
    expect(page.unread_count).toBe(2);
    expect(new Set(R2_ROWS.map((r) => r.kind))).toEqual(
      new Set(["todo_assigned", "template_update_available", "trigger_run_finished"]),
    );
    for (const r of R2_ROWS.filter((x) => x.kind === "trigger_run_finished")) {
      expect(r.context.startsWith("Auto-started by trigger ·"), r.row).toBe(true);
    }
    expect(R2_ROWS.find((r) => r.row === "t2")?.button).toBe("Review update…");
  });

  it("the Raj variant adds the Copperleaf proposal to Approvals (count 4)", () => {
    const raj = [...hannah, toWire(seed, RAJ_ROW)];
    expect(pageOf(raj, "approvals").items).toHaveLength(4);
    expect(RAJ_ROW.title).toBe(
      "Accrued Agent proposed 4 entries within BH AJE thresholds v2 — Copperleaf August close",
    );
  });
});

describe("INV-1: the agent never decides", () => {
  it("only accept_document, return_document and open_sign_off are inline, never on an agent row", () => {
    for (const r of [...ROWS, ...R2_ROWS, RAJ_ROW]) {
      for (const action of r.inlineActions) {
        expect(["accept_document", "return_document", "open_sign_off"]).toContain(action);
      }
      if (r.actorKind === "agent") expect(r.inlineActions, r.row).toEqual([]);
    }
    expect(ROWS.flatMap((r) => r.inlineActions)).toEqual([
      "open_sign_off",
      "accept_document",
      "return_document",
    ]);
  });
});

describe("Notification settings", () => {
  it("lists the four R2 kinds, each in Accrued, with Mention email on", () => {
    expect(PREFERENCE_KINDS.map((k) => k.label)).toEqual([
      "Mention",
      "To-do assigned",
      "Template update available",
      "Trigger run finished",
    ]);
    expect(PREFERENCE_KINDS.every((k) => k.in_app)).toBe(true);
    expect(PREFERENCE_KINDS.find((k) => k.kind === "mention")?.email).toBe(true);
  });
});
