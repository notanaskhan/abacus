// T-05-T13 (SPEC-651; T-05 §5.3): every T-05 artboard has a fixture scenario at its own clock and
// persona, its reads answer from the seed with no network call, and TXP-00 B's scripted run
// freezes on 7 of 10 with three running.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { RunStore, ScriptedRunSource } from "../../domain/agents/runSource";
import { scenarios as txp00 } from "../scenarios/TXP-00";
import { scenarios as txp01 } from "../scenarios/TXP-01";
import { scenarios as txp02 } from "../scenarios/TXP-02";
import { scenarios as txp05 } from "../scenarios/TXP-05";
import { scenarios as txp06 } from "../scenarios/TXP-06";
import { scenarios as txp07 } from "../scenarios/TXP-07";
import { scenarios as txp10 } from "../scenarios/TXP-10";
import { scenarios as txp11 } from "../scenarios/TXP-11";
import { FIGURES, RUN3_RUNNING, run3Script, TASKS, trialBalance } from "./tax-entity";

const SCREENS = {
  "TXP-00": txp00,
  "TXP-01": txp01,
  "TXP-02": txp02,
  "TXP-05": txp05,
  "TXP-06": txp06,
  "TXP-07": txp07,
  "TXP-10": txp10,
  "TXP-11": txp11,
} as const;
const { process } = globalThis as unknown as { process: { cwd: () => string } };
const DOCS = join(process.cwd(), "..", "..", "docs", "screens");

function artboards(id: string): string[] {
  const text = readFileSync(join(DOCS, `${id}.md`), "utf8");
  return [...text.matchAll(/^\| ([a-z][0-9]?) \|/gm)].map((m) => m[1]!);
}

function request(query = "") {
  return {
    method: "GET",
    path: "/v1/tax-returns/x/trial-balance",
    params: { return_id: "x" },
    query: new URLSearchParams(query),
    body: null,
    persona: undefined,
  };
}

describe("T-05 fixture scenarios", () => {
  it.each(Object.entries(SCREENS))("%s has a scenario for every contract artboard", (id, s) => {
    expect(Object.keys(s).sort()).toEqual(artboards(id).sort());
  });

  it("57 artboards in all", () => {
    const total = Object.values(SCREENS).reduce((n, s) => n + Object.keys(s).length, 0);
    expect(total).toBe(57);
  });

  it("every scenario has a persona and a parseable clock", () => {
    for (const s of Object.values(SCREENS)) {
      for (const scenario of Object.values(s)) {
        expect(scenario.persona).toMatch(/^(olivia-brandt|samuel-ito)$/);
        expect(Number.isNaN(Date.parse(scenario.clock))).toBe(false);
      }
    }
  });

  it("reads answer from the seed with no network call", async () => {
    const handler = txp02.a.handlers["GET /v1/tax-returns/{return_id}/trial-balance"]!;
    const body = (await (await handler(request())).json()) as {
      rows: unknown[];
      unmapped: number;
    };
    expect(body.rows).toHaveLength(28);
    expect(body.unmapped).toBe(0);
    const run1 = txp02.e.handlers["GET /v1/tax-returns/{return_id}/trial-balance"]!;
    const e = (await (await run1(request())).json()) as { unmapped: number };
    expect(e.unmapped).toBe(1);
    const line = (await (await handler(request("view=line"))).json()) as { view: string };
    expect(line.view).toBe("line");
  });

  it("writes answer 501 like the contract stubs", async () => {
    const write = txp11.e.handlers["PUT /v1/tax-returns/{return_id}/workbook/cells/{address}"]!;
    expect((await write(request())).status).toBe(501);
  });

  it("the trial balance carries the server's figures (UTB + AJE = tax basis on 2050)", () => {
    const row = trialBalance("run2").rows.find((r) => r.account_code === "2050")!;
    expect(row.tax_basis).toBe(FIGURES.i18);
    expect(FIGURES.openItems.reduce((a, b) => a + b, 0)).toBe(11);
  });

  it("TXP-00 B: the scripted Run 3 freezes on 7 of 10 with three running", () => {
    const store = new RunStore();
    store.connect(new ScriptedRunSource(run3Script(), { freeze: true }));
    const items = store.getSnapshot().items;
    expect(items).toHaveLength(TASKS.length);
    const running = items.filter((i) => i.outcome === null).map((i) => i.detail);
    expect(running).toEqual([...RUN3_RUNNING]);
    expect(items.length - running.length).toBe(7);
  });
});
