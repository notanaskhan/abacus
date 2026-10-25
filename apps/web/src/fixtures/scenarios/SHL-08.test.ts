// P-03-T07: SHL-08 has a scenario for every artboard P-03 builds (a–f, h), each answering the C4
// viewer and citation reads through the generated client in the OpenAPI shapes.
import { listCitations, viewerManifest, viewerPage, viewerRegions } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { validateResponse } from "../schema-check";
import { ALSO_CITED, LINE_2A } from "../seed/trust";
import { OPENS, type Shl08State, scenarios } from "./SHL-08";

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

function open(state: Shl08State): (typeof OPENS)[Shl08State] {
  restore?.();
  restore = installFixtureMode(scenarios[state]);
  return OPENS[state];
}

async function manifestOf(state: Shl08State) {
  const { versionId } = open(state);
  const { data } = await viewerManifest({ path: { version_id: versionId } });
  expect(validateResponse("GET", "/v1/evidence-versions/{version_id}/viewer", data)).toEqual([]);
  return data;
}

describe("SHL-08 scenarios", () => {
  it("cover a–f and h (g is K-03's), at their personas and clocks", () => {
    expect(Object.keys(scenarios)).toEqual(["a", "b", "c", "d", "e", "f", "h"]);
    expect(scenarios.a.persona).toBe("samuel-ito");
    expect(scenarios.a.clock).toBe("2026-09-14T09:24:00-05:00");
    expect(scenarios.b.persona).toBe("hannah-leclerc");
    expect(scenarios.b.clock).toBe("2026-09-14T09:41:00-05:00");
    expect(scenarios.h.clock).toBe("2026-09-14T14:30:00-05:00");
    expect(OPENS.b.host).toBe("dock");
  });

  it("a: the K-1 manifest is geometry and mask tokens, and box 18A lights", async () => {
    const manifest = await manifestOf("a");
    expect(manifest?.file_name).toBe("Ridgeline_2025_K1_JonahFeld_DRAFT.pdf");
    expect(manifest?.pii_masks.map((m) => m.display)).toEqual(["••-•••0287", "•••-••-4417"]);
    const { data } = await viewerRegions({
      path: { version_id: OPENS.a.versionId },
      query: { match_ids: [OPENS.a.matchId ?? ""] },
    });
    expect(data?.items.map((r) => r.label)).toEqual(["Form 1040 · line 2a 1,550"]);
    expect(ALSO_CITED).toContain("6,200 × 25% = 1,550");
  });

  it("a: the linked figures and the stack come from the line's citations", async () => {
    open("a");
    const figures = (
      await listCitations({
        query: { host_ref: `tax_form_line:${LINE_2A}`, source_version_id: OPENS.a.versionId },
      })
    ).data?.items;
    expect(figures?.map((c) => c.value_text)).toEqual([
      "1,550",
      "307,900",
      "4,600",
      "IL / CO / NY",
    ]);
    const stack = (
      await listCitations({
        query: { anchor_type: "tax_form_line", anchor_id: LINE_2A, anchor_ref: "line_2a" },
      })
    ).data?.items;
    expect(stack?.map((c) => c.id)).toEqual(OPENS.a.stack);
  });

  it("b and h: Harborline page 2 of 3, TOTAL INVESTMENTS and every cited region", async () => {
    const manifest = await manifestOf("b");
    expect(manifest?.page_count).toBe(3);
    const lit = (
      await viewerRegions({
        path: { version_id: OPENS.b.versionId },
        query: { match_ids: [OPENS.b.matchId ?? ""] },
      })
    ).data?.items;
    expect(lit?.map((r) => [r.page, r.label])).toEqual([[2, "16,500,000.00"]]);
    open("h");
    const every = (await viewerRegions({ path: { version_id: OPENS.h.versionId } })).data?.items;
    expect(every).toHaveLength(9);
    expect(every?.find((r) => r.match_id === OPENS.h.hovered)?.label).toBe("2,915,330.00");
  });

  it("c: Claire's W-2 masks box a and lights box 1", async () => {
    const manifest = await manifestOf("c");
    expect(manifest?.pii_masks.map((m) => [m.kind, m.display])).toEqual([["ssn", "•••-••-6081"]]);
    expect(manifest?.allowed_actions).toEqual(["pii.reveal"]);
  });

  it("d: the Halvard 1099 is password-protected", async () => {
    const manifest = await manifestOf("d");
    expect([manifest?.status, manifest?.kind, manifest?.pages]).toEqual([
      "password_protected",
      "none",
      [],
    ]);
  });

  it("e: the draft K-1's manifest answers processing, with no pages yet (AC3.4)", async () => {
    const manifest = await manifestOf("e");
    expect([manifest?.status, manifest?.file_name, manifest?.pages]).toEqual([
      "processing",
      "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
      [],
    ]);
  });

  it("f: source 2 of 3 is the K-1 statement, p. 3", async () => {
    const manifest = await manifestOf("f");
    expect(manifest?.file_name).toBe("Ridgeline 2025 K-1 statement.pdf");
    expect(OPENS.f.index).toBe(1);
  });

  it("a page answers a masked PNG", async () => {
    open("a");
    const { response } = await viewerPage({
      path: { version_id: OPENS.a.versionId, page_no: 1 },
      parseAs: "blob",
    });
    expect(response?.headers.get("Content-Type")).toBe("image/png");
    expect(response?.headers.get("Cache-Control")).toContain("no-store");
  });
});
