// P-03-T07: SHL-07 has a scenario for every artboard (a–e), each as Hannah Leclerc at 9:41 AM CT,
// answering the C4 citation reads through the generated client in the OpenAPI shapes.
import { type CitationV2Out, getCitation, listCitations } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { validateResponse } from "../schema-check";
import { KEYSTONE_CELL, SERVICE_ORGS_SECTION, SERVICE_ORGS_WORKPAPER } from "../seed/trust";
import { OPENS, scenarios } from "./SHL-07";

let restore: (() => void) | null = null;
let saved: ReturnType<typeof client.getConfig>;
beforeEach(() => {
  saved = client.getConfig();
  client.setConfig({ baseUrl: "http://fixture.test", throwOnError: true });
});
afterEach(() => {
  restore?.();
  restore = null;
  client.setConfig({ baseUrl: saved.baseUrl ?? "", throwOnError: false });
});

async function stack(scenario: Scenario): Promise<CitationV2Out[]> {
  restore?.();
  restore = installFixtureMode(scenario);
  const { data } = await listCitations({
    query: {
      anchor_type: "workpaper",
      anchor_id: SERVICE_ORGS_WORKPAPER,
      anchor_ref: KEYSTONE_CELL,
    },
  });
  expect(validateResponse("GET", "/v1/citations", data)).toEqual([]);
  return data?.items ?? [];
}

describe("SHL-07 scenarios", () => {
  it("cover every artboard letter as Hannah at Mon Sep 14, 9:41 AM CT", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e"]);
    for (const s of Object.values(scenarios)) {
      expect(s.persona).toBe("hannah-leclerc");
      expect(s.clock).toBe("2026-09-14T09:41:00-05:00");
    }
    expect(OPENS.c.variant).toBe("guidance");
    expect(OPENS.d.interact).toBe("hover");
  });

  it("a: one citation, BH-EBP-110 step 4, verified", async () => {
    const [one, ...rest] = await stack(scenarios.a);
    expect(rest).toEqual([]);
    expect(one?.title).toBe("BH-EBP-110: General Planning Procedures");
    expect(one?.quote?.startsWith("4. Identify each service organization")).toBe(true);
    expect(one?.verified).toBe(true);
  });

  it("b: three sources in order, the SOC 1 page 3 and the SPD page 14", async () => {
    const found = await stack(scenarios.b);
    expect(found.map((c) => [c.n, c.loc])).toEqual([
      [1, "Step 4"],
      [2, "Section I, p. 3"],
      [3, "p. 14"],
    ]);
    expect(found[1]?.title).toBe("Keystone SOC 1 Type 2 report, Oct 1 2024 – Sep 30 2025");
    expect(found[1]?.source.page).toBe(3);
  });

  it("c: the guidance citation answers by id", async () => {
    restore = installFixtureMode(scenarios.c);
    const [guidance] =
      (await listCitations({ query: { anchor_type: "workpaper", kind: "methodology_step" } })).data
        ?.items ?? [];
    const { data } = await getCitation({ path: { citation_id: guidance?.id ?? "" } });
    expect(validateResponse("GET", "/v1/citations/{citation_id}", data)).toEqual([]);
    expect(data?.title).toBe("Risk Assessment — overall risks and fraud");
  });

  it("e: the moved citation offers Re-link and says what superseded it", async () => {
    const [moved] = await stack(scenarios.e);
    expect(moved?.state).toBe("moved");
    expect(moved?.source.version).toBe("2");
    expect(moved?.moved?.successor_ref).toBe("EBP v3");
    expect(moved?.allowed_actions).toEqual(["citation.relink"]);
  });

  it("the section list answers the footer chips", async () => {
    restore = installFixtureMode(scenarios.b);
    const { data } = await listCitations({
      query: { host_ref: `workpaper:${SERVICE_ORGS_WORKPAPER}`, section_id: SERVICE_ORGS_SECTION },
    });
    expect(data?.total).toBe(3);
    const procedures = (
      await listCitations({
        query: {
          host_ref: `workpaper:${SERVICE_ORGS_WORKPAPER}`,
          section_id: SERVICE_ORGS_SECTION,
          kind: "methodology_step",
        },
      })
    ).data?.items;
    expect(procedures?.map((c) => c.title)).toEqual(["BH-EBP-110: General Planning Procedures"]);
  });

  it("an unknown citation is 404, as a walled one is", async () => {
    restore = installFixtureMode(scenarios.a);
    await expect(getCitation({ path: { citation_id: "missing" } })).rejects.toBeDefined();
  });
});
