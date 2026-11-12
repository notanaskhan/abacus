// W-02-T08 (TASK-7608): the Workbench subtree resolves in fixture mode. WB-01, WB-02 and WB-03 are
// fixture screens with paths and builders, the list's search params validate, and the family's
// fixture handlers answer the filters and the title-only search.
import { describe, expect, it } from "vitest";
import { workbenchHandlers } from "../fixtures/handlers/workbench";
import { MANIFEST } from "./manifest";
import { hrefOf, to } from "./to";

async function get(path: string, query: Record<string, string> = {}) {
  const handler = workbenchHandlers()[`GET ${path}`]!;
  const res = await handler({
    method: "GET",
    path,
    params: {},
    query: new URLSearchParams(query),
    body: undefined,
    persona: "hannah-leclerc",
  });
  return (await res.json()) as { items: { title: string; running?: boolean }[]; total: number };
}

describe("W-02 Workbench routes", () => {
  it("routes WB-01, WB-02 and WB-03 on fixtures", () => {
    expect(MANIFEST["WB-01"]).toMatchObject({ status: "fixture", path: "/workbench" });
    expect(MANIFEST["WB-02"]).toMatchObject({
      status: "fixture",
      path: "/workbench/sessions/new",
    });
    expect(MANIFEST["WB-03"]).toMatchObject({
      status: "fixture",
      path: "/workbench/sessions/$sessionId",
    });
    expect(MANIFEST["WB-04"]?.status).toBe("planned");
  });

  it("links HOME-01's running pill to the Running filter (AC-L2)", () => {
    expect(hrefOf(to.WB01(), { filter: "running" })).toBe("/workbench?filter=running");
    expect(hrefOf(to.WB02())).toBe("/workbench/sessions/new");
  });

  it("answers the filters and searches titles only (AC-L1, AC-L3)", async () => {
    expect((await get("/v1/workbench/sessions")).total).toBe(8);
    expect((await get("/v1/workbench/sessions", { q: "K-3" })).items).toEqual([]);
    const mine = await get("/v1/workbench/sessions", { filter: "mine" });
    // Mine = owned or initiated (DEC-4601): the weekly run Hannah saved is hers.
    expect(mine.items.map((r) => r.title)).toEqual([
      "TY2025 season progress by office",
      "Season Progress Reporter — weekly run",
      "Granite Peak preliminary analytics",
    ]);
    const via = await get("/v1/workbench/sessions", { filter: "via_agent" });
    expect(via.items.map((r) => r.title)).toEqual([
      "Season Progress Reporter — weekly run",
      "Request Chaser — daily",
    ]);
  });
});
