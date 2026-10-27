// F-04-T14 (SPEC-307 AC-8; F-04.29; chapter 04 section 2.6): every designed link is wired or named.
// The route registry is src/routes/manifest/<module>.ts, seeded from the handoff's screen index
// by scripts/seed-manifest.mjs, which also writes handoff-links.json. Four rules hold against the
// handoff that docs/design/HANDOFF_VERSION pins:
//   1. a link whose two ends are fixture or live is wired with to.<ID>() in the source screen's folder;
//   2. every manifest path resolves in the area route tree (and a live entry has a component);
//   3. a screen no designed link targets declares `entry`;
//   4. the record keys AJE-06, BH-26 and SURL-03 map to record routes, not screens.
// While most screens are planned, rule 1 holds vacuously; its checker is exercised on a synthetic
// manifest below so it stays a real check.
import type { LinkProps } from "@tanstack/react-router";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { MANIFEST, type ScreenEntry } from "./manifest";
import { RECORD_ROUTES, recordPrefix } from "./records";
import { appRoute } from "./root";
import { to } from "./to";

interface Link {
  from: string;
  to: string;
  board?: string;
  type: string;
  via: string | null;
}
interface RecordLink {
  from: string;
  key: string;
  type: string;
  via: string | null;
}
interface LinkGraph {
  handoffVersion: string;
  generated: string | null;
  screens: { id: string; name: string }[];
  neverTargeted: string[];
  links: Link[];
  records: RecordLink[];
  unindexed: { from: string; to: string; type: string; via: string | null }[];
}
interface Screen {
  id: string;
  name: string;
  entry: boolean;
}
interface Seeder {
  MARKER: string;
  handoffHash: (content: string) => string;
  pinnedHash: (text: string) => string | null;
  assertVersion: (versionText: string, hash: string) => void;
  indexPath: (env: Record<string, string | undefined>) => string;
  buildLinkGraph: (index: unknown, hash: string) => LinkGraph;
  renderModule: (module: string, screens: Screen[]) => string;
  addNewEntries: (source: string, screens: Screen[]) => { source: string; added: string[] };
  declaredIds: (source: string) => Set<string>;
}
interface RouteNode {
  id: string;
  fullPath: string;
  parentRoute?: RouteNode;
  options: { component?: unknown };
}

const { process } = globalThis as unknown as {
  process: { cwd: () => string; env: Record<string, string | undefined> };
};
const WEB = process.cwd();
const SRC = join(WEB, "src");
const REPO = join(WEB, "..", "..");
const GRAPH = JSON.parse(
  readFileSync(join(SRC, "routes", "handoff-links.json"), "utf8"),
) as LinkGraph;
const VERSION = readFileSync(join(REPO, "docs", "design", "HANDOFF_VERSION"), "utf8");
const ENTRIES: Readonly<Record<string, ScreenEntry>> = MANIFEST;

const seeder = (await import(/* @vite-ignore */ `${WEB}/scripts/seed-manifest.mjs`)) as Seeder;
let routes: RouteNode[];
beforeAll(async () => {
  const { router } = await import("../router");
  routes = Object.values(router.routesById as unknown as Record<string, RouteNode>);
});

const BUILT = new Set(["fixture", "live"]);

/** Every .ts and .tsx file's text under a folder ("" when it does not exist). */
function readTree(folder: string): string {
  if (!existsSync(folder)) return "";
  return readdirSync(folder, { withFileTypes: true })
    .map((d) => {
      const path = join(folder, d.name);
      if (d.isDirectory()) return readTree(path);
      return /\.tsx?$/.test(d.name) ? readFileSync(path, "utf8") : "";
    })
    .join("\n");
}

/** Rule 1's checker: each link between two built screens with no to.<ID>() call in the source. */
function unwiredLinks(
  links: readonly Link[],
  entries: Readonly<Record<string, ScreenEntry>>,
  read: (folder: string) => string,
): string[] {
  const failures: string[] = [];
  for (const link of links) {
    const from = entries[link.from];
    const target = entries[link.to];
    if (from === undefined || target === undefined) continue;
    if (!BUILT.has(from.status) || !BUILT.has(target.status)) continue;
    const call = new RegExp(`\\bto\\.${link.to.replace("-", "")}\\(`);
    if (!call.test(read(from.folder ?? `screens/${link.from}`))) {
      failures.push(`${link.from} → ${link.to} (${link.via ?? link.type}) is not wired`);
    }
  }
  return failures;
}

function trimSlash(path: string): string {
  return path.length > 1 ? path.replace(/\/$/, "") : path;
}

function inFirmWorkspace(route: RouteNode): boolean {
  for (let node: RouteNode | undefined = route; node !== undefined; node = node.parentRoute) {
    if (node.id === appRoute.id) return true;
  }
  return false;
}

describe("route registry against HANDOFF_VERSION", () => {
  it("handoff-links.json was written from the handoff HANDOFF_VERSION pins", () => {
    const pinned = seeder.pinnedHash(VERSION);
    expect(pinned).not.toBeNull();
    expect(GRAPH.handoffVersion.startsWith(pinned ?? "-")).toBe(true);
  });

  const local = seeder.indexPath(process.env);
  const index = existsSync(local) ? local : null; // the handoff is not on CI machines
  it.skipIf(index === null)("the local handoff is the one HANDOFF_VERSION pins", () => {
    const content = readFileSync(index ?? "", "utf8");
    expect(() => {
      seeder.assertVersion(VERSION, seeder.handoffHash(content));
    }).not.toThrow();
  });

  it("the manifest holds exactly the handoff's screen IDs", () => {
    const handoff = GRAPH.screens.map((s) => s.id).sort();
    expect(Object.keys(ENTRIES).sort()).toEqual(handoff);
  });

  it("the never-targeted list matches the link graph", () => {
    const targeted = new Set(GRAPH.links.map((l) => l.to));
    const never = GRAPH.screens.map((s) => s.id).filter((id) => !targeted.has(id));
    expect(GRAPH.neverTargeted).toEqual(never);
  });
});

describe("rule 1: links between built screens are wired with to.<ID>()", () => {
  it("every link whose two ends are fixture or live is wired", () => {
    expect(unwiredLinks(GRAPH.links, ENTRIES, (f) => readTree(join(SRC, f)))).toEqual([]);
  });

  it("the checker names the pair and the tooltip of an unwired link", () => {
    const entries: Record<string, ScreenEntry> = {
      "CLS-01": { name: "a", status: "fixture", path: "/closes" },
      "CLS-09": { name: "b", status: "live", path: "/closes/$closeId/plan" },
      "CLS-02": { name: "c", status: "planned", path: null },
    };
    const links: Link[] = [
      { from: "CLS-01", to: "CLS-09", type: "tooltip-only", via: "Opens CLS-09 · plan editor" },
      { from: "CLS-01", to: "CLS-02", type: "tooltip-only", via: "Opens CLS-02" },
    ];
    expect(unwiredLinks(links, entries, () => "<Link {...to.CLS02()} />")).toEqual([
      "CLS-01 → CLS-09 (Opens CLS-09 · plan editor) is not wired",
    ]);
    expect(unwiredLinks(links, entries, () => "<Link {...to.CLS09({ closeId })} />")).toEqual([]);
  });
});

// POR screens a firm admin edits from settings, not the client portal (DEC-567, DEC-589): they sit
// inside the firm workspace by design. Named one by one, so no other POR screen may.
const FIRM_HOSTED_POR = new Set(["POR-20"]);

describe("rule 2: every path resolves in the area route tree", () => {
  it("each manifest path is a route; portal screens sit outside the firm workspace", () => {
    const byPath = new Map(routes.map((r) => [trimSlash(r.fullPath), r]));
    const problems: string[] = [];
    for (const [id, entry] of Object.entries(ENTRIES)) {
      if (entry.path === null) continue;
      const route = byPath.get(trimSlash(entry.path));
      if (route === undefined) problems.push(`${id}: ${entry.path} is not in the route tree`);
      else if (id.startsWith("POR-") && !FIRM_HOSTED_POR.has(id) && inFirmWorkspace(route)) {
        problems.push(`${id}: ${entry.path} is inside the firm workspace`);
      } else if (entry.status === "live" && route.options.component === undefined) {
        problems.push(`${id}: ${entry.path} has no route component`);
      }
    }
    expect(problems).toEqual([]);
  });

  it("a screen has a builder exactly when it has a path", () => {
    const routed = Object.entries(ENTRIES)
      .filter(([, e]) => e.path !== null)
      .map(([id]) => id.replace("-", ""));
    expect(Object.keys(to).sort()).toEqual(routed.sort());
  });

  it("builders give a <Link> its to and params", () => {
    const record: LinkProps = to.CLI02({ clientId: "c-1" });
    expect(record).toEqual({ to: "/clients/$clientId", params: { clientId: "c-1" } });
    const index: LinkProps = to.CLI01();
    expect(index).toEqual({ to: "/clients" });
  });
});

describe("rule 3: never-targeted screens declare entry", () => {
  it("every screen no designed link targets has entry: true", () => {
    const missing = GRAPH.neverTargeted.filter((id) => ENTRIES[id]?.entry !== true);
    expect(missing).toEqual([]);
  });
});

describe("rule 4: record keys map to record routes", () => {
  it("AJE-06, BH-26 and SURL-03 are record links, not screens", () => {
    const keys = GRAPH.records.map((r) => r.key).sort();
    expect(keys).toEqual(expect.arrayContaining(["AJE-06", "BH-26", "SURL-03"]));
    for (const key of keys) expect(ENTRIES[key]).toBeUndefined();
  });

  it("every record key's prefix has a record route that resolves", () => {
    const byPath = new Set(routes.map((r) => trimSlash(r.fullPath)));
    const routesByPrefix: Readonly<Record<string, { path: string | null } | undefined>> =
      RECORD_ROUTES;
    const screenModules = new Set(Object.keys(ENTRIES).map(recordPrefix));
    const problems: string[] = [];
    for (const { key, from } of GRAPH.records) {
      const prefix = recordPrefix(key);
      const route = routesByPrefix[prefix];
      if (route === undefined) problems.push(`${from} → ${key}: no record route for ${prefix}`);
      else if (screenModules.has(prefix)) problems.push(`${prefix} is also a screen module`);
      else if (route.path !== null && (!route.path.includes("$") || !byPath.has(route.path))) {
        problems.push(`${prefix}: ${route.path} is not a record route in the tree`);
      }
    }
    expect(problems).toEqual([]);
  });
});

/** Screen IDs in the "To" column of each docs/screens/<ID>.md "## Links" table, by contract ID. */
function contractTargets(): Map<string, Set<string>> {
  const dir = join(REPO, "docs", "screens");
  const byScreen = new Map<string, Set<string>>();
  for (const name of readdirSync(dir)) {
    if (!/^[A-Z]+-\d+\.md$/.test(name)) continue;
    const text = readFileSync(join(dir, name), "utf8");
    const section = text.split("\n## Links")[1]?.split("\n## ")[0] ?? "";
    const targets = new Set<string>();
    for (const line of section.split("\n")) {
      if (!line.startsWith("|") || line.startsWith("|---") || line.startsWith("| From")) continue;
      const to = line.split("|")[2] ?? "";
      for (const m of to.matchAll(/\b([A-Z]{2,4}-\d{2})\b/g)) targets.add(m[1] ?? "");
    }
    byScreen.set(name.replace(/\.md$/, ""), targets);
  }
  return byScreen;
}

describe("rule 5: screen contracts and the link graph agree (P-06-T03)", () => {
  const contracts = contractTargets();

  it("every target a screen contract's Links table names is a manifest screen", () => {
    const unknown = [...contracts].flatMap(([id, targets]) =>
      [...targets].filter((t) => ENTRIES[t] === undefined).map((t) => `${id} → ${t}`),
    );
    expect(unknown).toEqual([]);
  });

  it("a screen contract names every designed link of its screen", () => {
    const missing = GRAPH.links
      .filter((l) => contracts.has(l.from) && !contracts.get(l.from)?.has(l.to))
      .map((l) => `${l.from} → ${l.to} (${l.via ?? l.type})`);
    expect(missing).toEqual([]);
  });
});

describe("seed-manifest.mjs adds new IDs only", () => {
  const existing: Screen[] = [{ id: "CLS-01", name: "Closes index", entry: false }];

  it("leaves existing entries untouched and adds only new IDs", () => {
    const built = seeder
      .renderModule("cls", existing)
      .replace(
        '"CLS-01": { name: "Closes index", status: "planned", path: null },',
        '"CLS-01": { name: "Closes, renamed by hand", status: "fixture", path: "/closes" },',
      );
    const fromHandoff: Screen[] = [
      { id: "CLS-01", name: "Closes index (renamed in the handoff)", entry: true },
      { id: "CLS-02", name: "Close record", entry: false },
      { id: "CLS-08", name: "Close settings", entry: true },
    ];
    const once = seeder.addNewEntries(built, fromHandoff);
    expect(once.added).toEqual(["CLS-02", "CLS-08"]);
    expect(once.source).toContain(
      '"CLS-01": { name: "Closes, renamed by hand", status: "fixture", path: "/closes" },',
    );
    expect(once.source).not.toContain("renamed in the handoff");
    expect(once.source).toContain(
      '"CLS-08": { name: "Close settings", status: "planned", path: null, entry: true },',
    );
    expect(once.source.indexOf("CLS-02")).toBeLessThan(once.source.indexOf(seeder.MARKER));
    expect([...seeder.declaredIds(once.source)]).toEqual(["CLS-01", "CLS-02", "CLS-08"]);
    const twice = seeder.addNewEntries(once.source, fromHandoff);
    expect(twice).toEqual({ source: once.source, added: [] });
  });

  it("refuses a module that lost its marker", () => {
    const source = seeder.renderModule("cls", existing).replace(seeder.MARKER, "");
    expect(() =>
      seeder.addNewEntries(source, [{ id: "CLS-02", name: "x", entry: false }]),
    ).toThrow(/marker/);
  });

  it("refuses to run when HANDOFF_VERSION does not pin the handoff's hash", () => {
    const hash = seeder.handoffHash("{}");
    expect(() => {
      seeder.assertVersion(`2026-10-21 sha256:${hash}`, hash);
    }).not.toThrow();
    expect(() => {
      seeder.assertVersion("2026-10-21 sha256:0123456789ab", hash);
    }).toThrow(/HANDOFF_VERSION pins/);
    expect(() => {
      seeder.assertVersion("2026-10-21", hash);
    }).toThrow(/pins no sha256/);
  });

  it("reads the handoff from ACCRUED_HANDOFF_DIR", () => {
    expect(seeder.indexPath({ ACCRUED_HANDOFF_DIR: "/h" })).toBe("/h/handoff/screen-index.json");
  });

  it("builds the link graph: artboards, record keys, unindexed IDs and never-targeted screens", () => {
    const entry = (
      id: string,
      kind: string,
      links: { to: string; type: string; via?: string }[],
    ) => ({
      id,
      name: id,
      kind,
      links,
    });
    const graph = seeder.buildLinkGraph(
      {
        meta: { generated: "2026-10-16" },
        entries: [
          entry("T1", "template", [{ to: "CLS-02", type: "same-canvas" }]),
          entry("CLS-01", "screen", [
            { to: "CLS-02a", type: "same-canvas", via: "Row" },
            { to: "CLS-03 (section top)", type: "same-canvas" },
            { to: "AJE-06", type: "tooltip-only", via: "Opens AJE-06" },
            { to: "CLS-99", type: "tooltip-only", via: "Opens CLS-99" },
          ]),
          entry("CLS-02", "screen", []),
          entry("CLS-03", "screen", []),
        ],
      },
      "abc",
    );
    expect(graph.links).toEqual([
      { from: "CLS-01", to: "CLS-02", board: "CLS-02a", type: "same-canvas", via: "Row" },
      {
        from: "CLS-01",
        to: "CLS-03",
        board: "CLS-03 (section top)",
        type: "same-canvas",
        via: null,
      },
    ]);
    expect(graph.records).toEqual([
      { from: "CLS-01", key: "AJE-06", type: "tooltip-only", via: "Opens AJE-06" },
    ]);
    expect(graph.unindexed).toEqual([
      { from: "CLS-01", to: "CLS-99", type: "tooltip-only", via: "Opens CLS-99" },
    ]);
    expect(graph.neverTargeted).toEqual(["CLS-01"]);
    expect(graph.handoffVersion).toBe("abc");
  });
});
