// L2, the copy registry checks (F-05-T32; plan 04 §8.3): "L2 fails on emoji, exclamation marks in
// agent keys, three dots on dialog openers and Accrued in portal namespaces." The first block runs
// L2 over every copy module in the app; the second proves each rule rejects its deny case, so the
// first cannot pass by checking nothing.
import { describe, expect, it } from "vitest";
import { COMMON_FIRM, COMMON_PORTAL, commonCopy } from "./common";
import {
  type CopyTree,
  defineCopy,
  lintCopy,
  namespaceOf,
  registeredCopy,
  surfaceOf,
} from "./registry";

// Every screen's copy module, eagerly: importing one registers any `defineCopy` namespace in it.
const SCREENS = import.meta.glob<Record<string, unknown>>("../screens/*/copy.ts", { eager: true });

function screenId(path: string): string {
  return /screens\/([^/]+)\/copy\.ts$/.exec(path)?.[1] ?? path;
}

/** A module's exported copy, as one tree (its `COPY`, and any other exported trees or strings). */
function exportedTree(mod: Record<string, unknown>): CopyTree {
  const tree: Record<string, unknown> = {};
  for (const [name, value] of Object.entries(mod)) {
    if (typeof value === "string" || (typeof value === "object" && value !== null)) {
      tree[name] = value;
    }
  }
  return tree as CopyTree;
}

describe("L2 over the app's copy", () => {
  it("finds the screens' copy modules", () => {
    expect(Object.keys(SCREENS).length).toBeGreaterThan(3);
  });

  it("every screen copy module passes", () => {
    const found = Object.entries(SCREENS).flatMap(([path, mod]) =>
      lintCopy(namespaceOf(screenId(path), exportedTree(mod))),
    );
    expect(found).toEqual([]);
  });

  it("every registered namespace passes, the shared ones included", () => {
    const ids = registeredCopy().map((ns) => ns.id);
    expect(ids).toContain("common.firm");
    expect(ids).toContain("common.portal");
    expect(registeredCopy().flatMap(lintCopy)).toEqual([]);
  });

  it("common: the portal namespace is portal and never says the product's name", () => {
    expect(surfaceOf("common.portal")).toBe("portal");
    expect(surfaceOf("POR-01")).toBe("portal");
    expect(surfaceOf("CLI-01")).toBe("firm");
    expect(JSON.stringify(COMMON_PORTAL)).not.toMatch(/accrued/i);
    expect(COMMON_FIRM.errorBody).toMatch(/^Accrued could not reach the server\./);
    expect(COMMON_PORTAL.errorBody).toBe(
      "We could not reach the server. Nothing was lost; try again in a moment.",
    );
    expect(commonCopy("portal")).toBe(COMMON_PORTAL);
    expect("agentRunning" in COMMON_PORTAL).toBe(false);
    expect(COMMON_FIRM.couldntLoad("sessions")).toBe("Couldn’t load sessions.");
  });
});

describe("L2 rejects each deny case", () => {
  const rules = (id: string, copy: CopyTree, extra?: Parameters<typeof namespaceOf>[2]) =>
    lintCopy(namespaceOf(id, copy, extra)).map((f) => `${f.rule}:${f.key}`);

  it("emoji, anywhere", () => {
    expect(rules("X-01", { a: "Done \u{1F389}" })).toEqual(["emoji:a"]);
    expect(rules("X-01", { a: "Done ✓" })).toEqual([]);
  });

  it('"!" in agent keys, by name or by listed path; not elsewhere', () => {
    expect(rules("X-01", { agentNote: "All set!" })).toEqual(["agent-bang:agentNote"]);
    expect(rules("X-01", { card: { agent: { title: "Done!" } } })).toEqual([
      "agent-bang:card.agent.title",
    ]);
    expect(rules("X-01", { run: { line: "Done!" } }, { agent: ["run."] })).toEqual([
      "agent-bang:run.line",
    ]);
    expect(rules("X-01", { banner: "Welcome!" })).toEqual([]);
  });

  it('three dots anywhere, and a dialog opener without "…"', () => {
    expect(rules("X-01", { open: "Sign off..." })).toEqual(["three-dots:open"]);
    expect(rules("X-01", { open: "Sign off" }, { opensDialog: ["open"] })).toEqual([
      "opener-ellipsis:open",
    ]);
    expect(rules("X-01", { open: "Sign off…" }, { opensDialog: ["open"] })).toEqual([]);
  });

  it("the product's name in a portal namespace, and only there", () => {
    expect(rules("POR-99", { footer: "Powered by Accrued" })).toEqual(["portal-name:footer"]);
    expect(rules("x.portal", { f: (firm: string) => `${firm} on Accrued` })).toEqual([
      "portal-name:f",
    ]);
    expect(rules("SHL-99", { title: "Sign in to Accrued" })).toEqual([]);
  });

  it('"task" outside allow-listed close keys, and "Todo" unhyphenated', () => {
    expect(rules("X-01", { add: "+ Task" })).toEqual(["task:add"]);
    expect(rules("CLS-99", { step: "Close task" }, { task: ["step"] })).toEqual([]);
    expect(rules("X-01", { add: "+ Todo" })).toEqual(["todo:add"]);
    expect(rules("X-01", { add: "+ To-do" })).toEqual([]);
  });

  it("defineCopy returns the copy unchanged and records its namespace", () => {
    const copy = { title: "Firm settings", save: "Save" } as const;
    expect(defineCopy("TEST-01", copy)).toBe(copy);
    const ns = registeredCopy().find((n) => n.id === "TEST-01");
    expect(ns?.rules.surface).toBe("firm");
  });
});
