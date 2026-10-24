// R-01-T05 seed footing (docs/screens/POR-03.md, POR-04.md, POR-14.md, Figures): the portal PBC
// figures from the seed, never restated. 21 = 19 + 2 = Intake 2 and 37 sorted are POR-02's binder;
// Keystone's room is POR-01's 9 delegated items, 4 uploaded then 5; Claire's drop is 3 = 2 + 1;
// Ridgeline's §754 figures are computed. Every scenario answers its screen's read in the schema,
// names a persona the seed signs in, and never says "Accrued" or a firm status word.
import { describe, expect, it } from "vitest";
import type { FixtureHandler } from "../app-core/fixture-mode";
import { validateResponse } from "./schema-check";
import { scenarios as por02, feldOpenUploads } from "./scenarios/POR-02";
import { ARTBOARD as POR03_ARTBOARD, scenarios as por03 } from "./scenarios/POR-03";
import { ARTBOARD as POR04_ARTBOARD, scenarios as por04 } from "./scenarios/POR-04";
import { scenarios as por14 } from "./scenarios/POR-14";
import { getSeed, meFor } from "./seed";
import { FELD_BINDER, PORTAL_SHELLS } from "./seed/portal-home";
import {
  DANA_OWN_REQUESTS,
  FELD_DROP,
  FELD_ROWS_A,
  FELD_ROWS_C,
  FELD_ROWS_C2,
  HARBORLINE_D,
  KEYSTONE_A,
  KEYSTONE_B,
  KEYSTONE_C,
  KEYSTONE_E,
  KEYSTONE_ITEMS,
  RIDGELINE_754,
  RIDGELINE_DECISION,
  danaBinder,
  feldBinder,
} from "./seed/portal-documents";

const seed = getSeed();

async function call(
  handlers: Record<string, FixtureHandler>,
  route: string,
  params: Record<string, string> = {},
  body?: unknown,
  persona = "claire-feld",
): Promise<{ status: number; body: unknown }> {
  const handler = handlers[route];
  if (handler === undefined) throw new Error(`no handler for ${route}`);
  const [method = "GET", path = ""] = route.split(" ");
  const response = await handler({
    method,
    path,
    params,
    query: new URLSearchParams(),
    body,
    persona,
  });
  return { status: response.status, body: await response.json() };
}

describe("the Feld binder foots to POR-02 and TAX-03", () => {
  const a = feldBinder(FELD_ROWS_A);

  it("21 requests = 19 done + 2 open = Intake 2, with 37 files sorted", () => {
    expect(a.total).toBe(FELD_BINDER.total);
    expect(a.done_count).toBe(FELD_BINDER.done);
    expect(a.open_count).toBe(feldOpenUploads());
    expect(a.open_count).toBe(2);
    expect(a.done_count + a.open_count).toBe(a.total);
    expect(a.sorted_count).toBe(FELD_BINDER.sorted);
    expect(por02.a.persona).toBe(por03.a.persona);
  });

  it("ticks four categories in a, leaves Health and Other open, and mutes three", () => {
    const ticked = a.categories.filter((c) => c.complete).map((c) => c.label);
    expect(ticked).toEqual([
      "Personal & Household Information",
      "Income Sources",
      "Home & Property",
      "Charitable & Donations",
    ]);
    const muted = a.categories.filter((c) => c.requested === 0).map((c) => c.label);
    expect(muted).toEqual(["Education & Student", "Retirement", "Business & Self-Employment"]);
    expect(a.categories.reduce((n, c) => n + c.requested, 0)).toBe(FELD_BINDER.total);
    expect(a.mark_done.state).toBe("tonal");
  });

  it("ticks Other Activity after the sort (c) and Health & Medical after the email (c2)", () => {
    const tick = (rows: typeof FELD_ROWS_A, label: string) =>
      feldBinder(rows).categories.find((c) => c.label === label)?.complete;
    expect(tick(FELD_ROWS_C, "Other Activity")).toBe(true);
    expect(tick(FELD_ROWS_C, "Health & Medical")).toBe(false);
    expect(tick(FELD_ROWS_C2, "Health & Medical")).toBe(true);
    expect(feldBinder(FELD_ROWS_C).mark_done.state).toBe("tonal");
    expect(feldBinder(FELD_ROWS_C2).mark_done.state).toBe("ready");
    expect(feldBinder(FELD_ROWS_C2).open_count).toBe(0);
  });

  it("sorts Claire's three files into two rule links and one for the firm (c, d)", () => {
    const outcomes = FELD_DROP.files.map((f) => f.outcome);
    expect(outcomes).toEqual(["rule_linked", "rule_linked", "waiting"]);
    const estimates = FELD_ROWS_C.estimates.files ?? [];
    expect(estimates.map((f) => f.receipt.kind)).toEqual([
      "rule_linked_pending",
      "rule_linked_pending",
    ]);
  });

  it("shows only Dana's own requests and names the other parties by organisation", () => {
    const dana = danaBinder();
    const rows = (dana.bands ?? []).flatMap((b) => b.rows);
    expect(rows.length).toBeLessThanOrEqual(DANA_OWN_REQUESTS);
    expect(dana.other_parties).toEqual(["Keystone", "Harborline", "PayGrid", "Summit"]);
    expect(rows.filter((r) => r.client_status === "done")).toHaveLength(1);
  });
});

describe("the third-party rooms foot", () => {
  it("Keystone: 9 delegated, 4 uploaded at a, 5 at b, 9 at e", () => {
    for (const room of [KEYSTONE_A, KEYSTONE_B, KEYSTONE_C, KEYSTONE_E]) {
      expect(room.total).toBe(KEYSTONE_ITEMS);
      expect(room.bands.reduce((n, b) => n + b.total, 0)).toBe(room.total);
    }
    expect(KEYSTONE_A.uploaded_count).toBe(4);
    expect(
      KEYSTONE_A.bands.map((b) => `${b.label} · ${String(b.uploaded)} of ${String(b.total)}`),
    ).toEqual(["Recordkeeper reports · 3 of 5", "SOC 1 & fees · 1 of 4"]);
    expect(KEYSTONE_B.uploaded_count).toBe(5);
    expect(KEYSTONE_C.uploaded_count).toBe(4);
    expect(KEYSTONE_E.complete).toBe(true);
  });

  it("Harborline: the certification in review and the trust statement due", () => {
    expect(HARBORLINE_D.uploaded_count).toBe(1);
    expect(HARBORLINE_D.total).toBe(2);
    expect(HARBORLINE_D.intro).toContain("ERISA section 103(a)(3)(C)");
  });
});

describe("Ridgeline's §754 decision computes its figures", () => {
  it("5/35 × 2,319,835 = 331,405 and 360,000 − 331,405 = 28,595", () => {
    expect(RIDGELINE_754).toEqual({ share: 331_405n, stepUp: 28_595n });
    expect(RIDGELINE_DECISION.explanation).toContain("$331,405");
    expect(RIDGELINE_DECISION.explanation).toContain("$28,595");
  });
});

describe("every artboard opens on its data", () => {
  it.each(Object.entries(por03))(
    "POR-03 %s answers its binder in the schema",
    async (state, s) => {
      const { binderId } = POR03_ARTBOARD[state as keyof typeof POR03_ARTBOARD];
      const res = await call(s.handlers, "GET /v1/portal/binders/{binder_id}", {
        binder_id: binderId,
      });
      expect(res.status).toBe(200);
      expect(validateResponse("get", "/v1/portal/binders/{binder_id}", res.body)).toEqual([]);
      const list = await call(s.handlers, "GET /v1/portal/binders");
      expect(validateResponse("get", "/v1/portal/binders", list.body)).toEqual([]);
    },
  );

  it.each(Object.entries(por04).filter(([k]) => !["e", "f"].includes(k)))(
    "POR-04 %s answers its request in the schema",
    async (state, s) => {
      const { requestId } = POR04_ARTBOARD[state as keyof typeof POR04_ARTBOARD];
      const res = await call(s.handlers, "GET /v1/portal/request-items/{item_id}", {
        item_id: requestId,
      });
      expect(res.status).toBe(200);
      expect(validateResponse("get", "/v1/portal/request-items/{item_id}", res.body)).toEqual([]);
    },
  );

  it("POR-04 e and f carry their slot data and one action each", () => {
    expect(POR04_ARTBOARD.e.question?.options).toHaveLength(3);
    expect(POR04_ARTBOARD.f.decision?.options).toHaveLength(3);
  });

  it.each(Object.entries(por14))("POR-14 %s answers the room or 404", async (state, s) => {
    const res = await call(s.handlers, "GET /v1/portal/room", {}, undefined, s.persona);
    if (state === "f") {
      expect(res.status).toBe(404);
      return;
    }
    expect(res.status).toBe(200);
    expect(validateResponse("get", "/v1/portal/room", res.body)).toEqual([]);
  });

  it("every scenario's persona signs in to a portal shell", () => {
    for (const s of [...Object.values(por03), ...Object.values(por04), ...Object.values(por14)]) {
      const who = s.persona ?? "";
      expect(meFor(seed, who), who).toBeDefined();
      expect(PORTAL_SHELLS[who], who).toBeDefined();
    }
  });

  it("third parties get the reduced shell and land on their room", () => {
    expect(PORTAL_SHELLS["sam-ortiz"]?.landing).toBe("requests");
    expect(PORTAL_SHELLS["harborline-certifications"]?.landing).toBe("requests");
  });
});

describe("the fixtures stay white-label and in client words", () => {
  const everything = JSON.stringify({
    binders: [feldBinder(FELD_ROWS_A), feldBinder(FELD_ROWS_C2), danaBinder()],
    rooms: [KEYSTONE_A, KEYSTONE_B, KEYSTONE_C, HARBORLINE_D, KEYSTONE_E],
    decision: RIDGELINE_DECISION,
  });

  it("never names the product, the agent or a firm status word", () => {
    for (const word of [
      "Accrued",
      "Agent",
      "Uploaded – needs review",
      "Received ✓",
      "In review",
      "confidence",
    ]) {
      expect(everything).not.toContain(word);
    }
  });
});

describe("the fixture writes behave as the live routes will", () => {
  it("Ignore then Undo returns the 1095-C to To do", async () => {
    const { handlers } = por03.f;
    const params = { item_id: POR03_ARTBOARD.f.ignoreOpenOn ?? "" };
    const ignored = await call(
      handlers,
      "POST /v1/portal/request-items/{item_id}/ignore",
      params,
      {
        reason: "not_this_year",
        note: "We switched plans in January.",
      },
    );
    expect(ignored.status).toBe(200);
    const binderId = { binder_id: POR03_ARTBOARD.f.binderId };
    const after = (await call(handlers, "GET /v1/portal/binders/{binder_id}", binderId)).body as {
      open_count: number;
    };
    expect(after.open_count).toBe(1);
    const undone = await call(
      handlers,
      "POST /v1/portal/request-items/{item_id}/ignore/undo",
      params,
    );
    expect(
      validateResponse("post", "/v1/portal/request-items/{item_id}/ignore/undo", undone.body),
    ).toEqual([]);
    const back = (await call(handlers, "GET /v1/portal/binders/{binder_id}", binderId)).body as {
      open_count: number;
    };
    expect(back.open_count).toBe(2);
  });

  it("Mark as Done then Undo, and a second Undo is refused", async () => {
    const { handlers } = por03.c2;
    const params = { binder_id: POR03_ARTBOARD.c2.binderId };
    expect(
      (await call(handlers, "POST /v1/portal/binders/{binder_id}/mark-done", params)).status,
    ).toBe(200);
    const undo = await call(
      handlers,
      "POST /v1/portal/binders/{binder_id}/mark-done/undo",
      params,
    );
    expect(undo.body).toMatchObject({ mark_done: "ready" });
    const again = await call(
      handlers,
      "POST /v1/portal/binders/{binder_id}/mark-done/undo",
      params,
    );
    expect(again.status).toBe(409);
  });

  it("Withdraw takes Claire's own file off; an emailed file answers 409", async () => {
    const { handlers } = por03.a;
    const own = FELD_ROWS_A.donations.files?.[0]?.id ?? "";
    const emailed = FELD_ROWS_A.w2.files?.[0]?.id ?? "";
    const route = "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw";
    const ok = await call(handlers, route, { engagement_id: "e", version_id: own });
    expect(ok.status).toBe(200);
    const refused = await call(handlers, route, { engagement_id: "e", version_id: emailed });
    expect(refused.status).toBe(409);
  });
});
