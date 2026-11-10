// I-01-T25 (TASK-6726): "Counts are equal on every surface for every persona." Each surface reads
// the fixture server through its own path: HOME-01's header and summary and HOME-02's bands from
// `GET /v1/human-gates/counts`, HOME-02's rows from `GET /v1/human-gates`, the badge (the Approvals
// segment) and SHL-04's Approvals tab from the counts' total (`tabOptions`). Six personas.
import type { HumanGateCountsOut, ListPageHumanGateOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { humanGateHandlers } from "../../fixtures/handlers/human-gates";
import { getSeed } from "../../fixtures/seed";
import { tabOptions } from "../../shell/firm/NotificationsDrawer";
import { BANDS, summaryParts, visibleBands } from "./gateClasses";

const PERSONAS = [
  "daniel-reyes",
  "margaret-okonkwo",
  "samuel-ito",
  "grace-holloway",
  "kevin-osei",
  "hannah-leclerc",
] as const;

function request(path: string, persona: string, query = ""): FixtureRequest {
  return {
    method: "GET",
    path,
    params: {},
    query: new URLSearchParams(query),
    body: undefined,
    persona,
  };
}

async function read<T>(path: string, persona: string, query = ""): Promise<T> {
  const handlers = humanGateHandlers(getSeed());
  const handler = handlers[`GET ${path}`];
  if (handler === undefined) throw new Error(`no fixture for ${path}`);
  return (await (await handler(request(path, persona, query))).json()) as T;
}

describe("HOME counts, every surface, six personas", () => {
  it.each(PERSONAS)(
    "%s: header = badge = summary = bands = rows = SHL-04 Approvals",
    async (persona) => {
      const counts = await read<HumanGateCountsOut>("/v1/human-gates/counts", persona);
      const page = await read<ListPageHumanGateOut>("/v1/human-gates", persona, "limit=200");
      const header = counts.total; // HOME-01's "Waiting on you" count and the Approvals badge
      const bands = BANDS.reduce((n, b) => n + counts.bands[b], 0); // HOME-02's band headers
      const rows = page.items.length; // HOME-02's rows and HOME-01's list
      const byBand = Object.fromEntries(
        BANDS.map((b) => [b, page.items.filter((g) => g.band === b).length]),
      );
      const summary = summaryParts(counts.bands).join(" · ");
      expect(bands).toBe(header);
      expect(rows).toBe(header);
      expect(byBand).toEqual(counts.bands);
      for (const b of visibleBands(counts.bands))
        expect(summary).toContain(String(counts.bands[b]));
      const approvals = tabOptions(undefined, counts.total).find((o) =>
        o.label.startsWith("Approvals"),
      );
      expect(approvals?.count).toBe(header > 0 ? header : undefined);
    },
  );

  it("after a snooze and a reassignment every surface still agrees", async () => {
    const handlers = humanGateHandlers(getSeed());
    const call = async <T>(
      method: string,
      path: string,
      params: Record<string, string> = {},
      body?: unknown,
    ): Promise<T> => {
      const handler = handlers[`${method} ${path}`];
      if (handler === undefined) throw new Error(`no fixture for ${path}`);
      const response = await handler({ ...request(path, "daniel-reyes"), method, params, body });
      return (await response.json()) as T;
    };
    const before = await call<ListPageHumanGateOut>("GET", "/v1/human-gates");
    const [first, second] = before.items;
    if (first === undefined || second === undefined) throw new Error("Daniel holds gates");
    await call(
      "POST",
      "/v1/human-gates/{gate_id}/snooze",
      { gate_id: first.id },
      {
        until: first.due_on ? `${first.due_on}T09:00:00-05:00` : "2026-09-15T09:00:00-05:00",
      },
    );
    const candidates = await call<{ candidates: { user_id: string }[] }>(
      "GET",
      "/v1/human-gates/{gate_id}/reassign-candidates",
      { gate_id: second.id },
    );
    await call(
      "POST",
      "/v1/human-gates/{gate_id}/reassign",
      { gate_id: second.id },
      {
        to_user_id: candidates.candidates[0]?.user_id,
        seen_version: second.version ?? 1,
      },
    );
    const counts = await call<HumanGateCountsOut>("GET", "/v1/human-gates/counts");
    const after = await call<ListPageHumanGateOut>("GET", "/v1/human-gates");
    expect(counts.total).toBe(after.items.length);
    expect(BANDS.reduce((n, b) => n + counts.bands[b], 0)).toBe(counts.total);
    expect(counts.total).toBeLessThanOrEqual(before.items.length - 1);
  });

  it("Daniel's is the demo's 11 = 3 + 6 + 2", async () => {
    const counts = await read<HumanGateCountsOut>("/v1/human-gates/counts", "daniel-reyes");
    expect(counts.total).toBe(11);
    expect([counts.bands.decisions, counts.bands.sign_offs, counts.bands.approvals_sends]).toEqual(
      [3, 6, 2],
    );
  });
});
