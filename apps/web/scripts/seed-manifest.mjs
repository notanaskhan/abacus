// The route registry's seed (F-04-T14; SPEC-307 AC-8; chapter 04 section 2.6; G-B03). Reads the
// design handoff's screen-index.json and
//   - adds a manifest entry for every screen ID not yet in src/routes/manifest/<module>.ts. It never
//     edits or removes an entry: a screen's builder sets `status`, `path` and `folder` by hand.
//   - writes src/routes/handoff-links.json: the designed link graph (source screen, target screen,
//     link type and its tooltip or label), the record-key links (AJE-06, BH-26, SURL-03), the
//     links to IDs the index does not list, and the screens no link targets.
//   - rewrites src/routes/manifest/index.ts, which only gathers the module files.
// It refuses to run when docs/design/HANDOFF_VERSION does not pin this handoff's hash, so both
// founders' registries come from the same handoff. Dependency-free (node:fs, node:crypto).
//
//   node scripts/seed-manifest.mjs        (pnpm -C apps/web routes:seed)
//
// The handoff is read from $ACCRUED_HANDOFF_DIR/handoff/screen-index.json. It stays outside git.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(WEB, "..", "..");
export const MANIFEST_DIR = join(WEB, "src", "routes", "manifest");
export const LINKS_FILE = join(WEB, "src", "routes", "handoff-links.json");
export const VERSION_FILE = join(REPO, "docs", "design", "HANDOFF_VERSION");
const DEFAULT_HANDOFF_DIR = "/Users/ayushkbhatia/Accrued/sources/handoff";

/** The line every manifest module keeps; new entries go directly above it. */
export const MARKER = "  // seed-manifest: new screens are added above this line";
const PRINT_WIDTH = 99; // apps/web/.prettierrc, so a seeded file is already formatted

/** @returns {string} */
export function indexPath(env = process.env) {
  const dir = env.ACCRUED_HANDOFF_DIR || DEFAULT_HANDOFF_DIR;
  return join(dir, "handoff", "screen-index.json");
}

/** sha256 of the screen index's bytes, as hex. @param {string | Uint8Array} content */
export function handoffHash(content) {
  return createHash("sha256").update(content).digest("hex");
}

/** The hash HANDOFF_VERSION pins ("<date> sha256:<hex>"), or null. @param {string} text */
export function pinnedHash(text) {
  const match = /sha256:([0-9a-f]{12,64})\b/.exec(text);
  return match === null ? null : match[1];
}

/** Throws unless the pinned hash names this handoff. @param {string} versionText @param {string} hash */
export function assertVersion(versionText, hash) {
  const pinned = pinnedHash(versionText);
  if (pinned === null) {
    throw new Error("docs/design/HANDOFF_VERSION pins no sha256: write '<date> sha256:<hash>'.");
  }
  if (!hash.startsWith(pinned)) {
    throw new Error(
      `The handoff's screen-index.json is sha256:${hash.slice(0, 12)}, but HANDOFF_VERSION pins ` +
        `sha256:${pinned.slice(0, 12)}. Find out why before seeding (docs/plan/08-collaboration.md).`,
    );
  }
}

/** "CLI-01" -> "cli". @param {string} id */
export function moduleOf(id) {
  return id.split("-")[0].toLowerCase();
}

/** "CLI-01" -> "CLI01", the builder's name on `to`. @param {string} id */
export function builderName(id) {
  return id.replace("-", "");
}

/**
 * The screen a link's `to` names: the ID itself, an artboard of it ("SHL-12a", "TAX-03a2") or a
 * part of it ("SHL-03 (section top)"). Null when it names no indexed screen.
 * @param {string} raw @param {Set<string>} screens
 */
export function targetScreen(raw, screens) {
  const id = raw.replace(/\s*\(.*\)\s*$/, "").trim();
  if (screens.has(id)) return id;
  const board = /^([A-Z]+-\d+)[a-z]\d*$/.exec(id);
  return board !== null && screens.has(board[1]) ? board[1] : null;
}

/**
 * The link graph of a screen index. Only screens are sources (template, component and journey
 * entries are not routes). A target that is no indexed screen is either a link to a screen the
 * index does not list (its prefix is a screen module's) or a record key such as AJE-06.
 * @param {{meta?: {generated?: string}, entries: Array<{id: string, name: string, kind: string, links: Array<{to: string, type: string, via?: string}>}>}} index
 * @param {string} hash
 */
export function buildLinkGraph(index, hash) {
  const screenEntries = index.entries.filter((e) => e.kind === "screen");
  const screens = new Set(screenEntries.map((e) => e.id));
  const prefixes = new Set(screenEntries.map((e) => e.id.split("-")[0]));
  const links = [];
  const records = [];
  const unindexed = [];
  const targeted = new Set();
  for (const entry of screenEntries) {
    for (const link of entry.links) {
      const via = link.via ?? null;
      const to = targetScreen(link.to, screens);
      if (to !== null) {
        targeted.add(to);
        const board = link.to === to ? {} : { board: link.to };
        links.push({ from: entry.id, to, ...board, type: link.type, via });
      } else if (/^[A-Z]+-\d+/.test(link.to) && !prefixes.has(link.to.split("-")[0])) {
        records.push({ from: entry.id, key: link.to, type: link.type, via });
      } else {
        unindexed.push({ from: entry.id, to: link.to, type: link.type, via });
      }
    }
  }
  return {
    handoffVersion: hash,
    generated: index.meta?.generated ?? null,
    screens: screenEntries.map((e) => ({ id: e.id, name: e.name })),
    neverTargeted: screenEntries.filter((e) => !targeted.has(e.id)).map((e) => e.id),
    links,
    records,
    unindexed,
  };
}

/** handoff-links.json, one link per line so a handoff bump diffs by link. @param {ReturnType<typeof buildLinkGraph>} graph */
export function renderLinks(graph) {
  const rows = (items) => items.map((item) => `    ${JSON.stringify(item)}`).join(",\n");
  return [
    "{",
    `  "handoffVersion": ${JSON.stringify(graph.handoffVersion)},`,
    `  "generated": ${JSON.stringify(graph.generated)},`,
    `  "screens": [\n${rows(graph.screens)}\n  ],`,
    `  "neverTargeted": ${JSON.stringify(graph.neverTargeted)},`,
    `  "links": [\n${rows(graph.links)}\n  ],`,
    `  "records": [\n${rows(graph.records)}\n  ],`,
    `  "unindexed": [\n${rows(graph.unindexed)}\n  ]`,
    "}",
    "",
  ].join("\n");
}

/** One manifest entry, laid out as prettier would. @param {{id: string, name: string, entry: boolean}} screen */
export function renderEntry(screen) {
  const fields = [`name: ${JSON.stringify(screen.name)}`, 'status: "planned"', "path: null"];
  if (screen.entry) fields.push("entry: true");
  const line = `  ${JSON.stringify(screen.id)}: { ${fields.join(", ")} },`;
  if (line.length <= PRINT_WIDTH) return line;
  return [`  ${JSON.stringify(screen.id)}: {`, ...fields.map((f) => `    ${f},`), "  },"].join(
    "\n",
  );
}

/** The IDs a manifest module's source declares. @param {string} source */
export function declaredIds(source) {
  return new Set([...source.matchAll(/^ {2}"([A-Z]+-\d+)": \{/gm)].map((m) => m[1]));
}

/** A new manifest module. @param {string} module @param {Array<{id: string, name: string, entry: boolean}>} screens */
export function renderModule(module, screens) {
  return [
    `// ${module.toUpperCase()} screens of the design handoff (F-04-T14), seeded by scripts/seed-manifest.mjs.`,
    "// It adds new IDs above the marker and never edits an entry; a screen's builder sets status,",
    "// path and folder when the screen is built.",
    'import type { Manifest } from "./types";',
    "",
    `export const ${module}Screens = {`,
    ...screens.map(renderEntry),
    MARKER,
    "} as const satisfies Manifest;",
    "",
  ].join("\n");
}

/**
 * The generator's core: `source` with an entry added for each screen it does not declare yet.
 * Existing entries are never touched, whatever the handoff now says about them.
 * @param {string} source @param {Array<{id: string, name: string, entry: boolean}>} screens
 * @returns {{source: string, added: string[]}}
 */
export function addNewEntries(source, screens) {
  const have = declaredIds(source);
  const fresh = screens.filter((s) => !have.has(s.id));
  if (fresh.length === 0) return { source, added: [] };
  const at = source.indexOf(`${MARKER}\n`);
  if (at < 0) throw new Error(`The manifest module has lost its marker line:\n${MARKER}`);
  const insert = fresh.map((s) => `${renderEntry(s)}\n`).join("");
  return {
    source: source.slice(0, at) + insert + source.slice(at),
    added: fresh.map((s) => s.id),
  };
}

/** manifest/index.ts for the module files present. @param {string[]} modules */
export function renderIndex(modules) {
  const sorted = [...modules].sort();
  return [
    "// Written by scripts/seed-manifest.mjs from the module files in this folder; do not edit.",
    ...sorted.map((m) => `import { ${m}Screens } from "./${m}";`),
    "",
    "/** Every screen of the design handoff, by screen ID (F-04-T14). */",
    "export const MANIFEST = {",
    ...sorted.map((m) => `  ...${m}Screens,`),
    "} as const;",
    "",
    'export type { Manifest, ScreenEntry, ScreenStatus } from "./types";',
    "",
  ].join("\n");
}

/** Seeds the manifests and the link graph from the handoff. Returns the IDs it added. */
export function seed({ env = process.env, log = console.log } = {}) {
  const file = indexPath(env);
  if (!existsSync(file)) throw new Error(`No screen index at ${file} (set ACCRUED_HANDOFF_DIR).`);
  const content = readFileSync(file);
  const hash = handoffHash(content);
  assertVersion(existsSync(VERSION_FILE) ? readFileSync(VERSION_FILE, "utf8") : "", hash);
  const graph = buildLinkGraph(JSON.parse(content.toString("utf8")), hash);
  const never = new Set(graph.neverTargeted);
  /** @type {Map<string, Array<{id: string, name: string, entry: boolean}>>} */
  const byModule = new Map();
  for (const { id, name } of graph.screens) {
    const module = moduleOf(id);
    if (!byModule.has(module)) byModule.set(module, []);
    byModule.get(module).push({ id, name, entry: never.has(id) });
  }
  for (const screens of byModule.values()) {
    screens.sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
  }
  mkdirSync(MANIFEST_DIR, { recursive: true });
  const added = [];
  for (const [module, screens] of byModule) {
    const path = join(MANIFEST_DIR, `${module}.ts`);
    if (existsSync(path)) {
      const result = addNewEntries(readFileSync(path, "utf8"), screens);
      if (result.added.length > 0) writeFileSync(path, result.source, "utf8");
      added.push(...result.added);
    } else {
      writeFileSync(path, renderModule(module, screens), "utf8");
      added.push(...screens.map((s) => s.id));
    }
  }
  const modules = readdirSync(MANIFEST_DIR)
    .filter((f) => f.endsWith(".ts") && !["index.ts", "types.ts"].includes(f))
    .map((f) => f.slice(0, -3));
  writeFileSync(join(MANIFEST_DIR, "index.ts"), renderIndex(modules), "utf8");
  writeFileSync(LINKS_FILE, renderLinks(graph), "utf8");
  log(
    `seed-manifest: handoff sha256:${hash.slice(0, 12)}, ${String(graph.screens.length)} screens, ` +
      `${String(graph.links.length)} links; added ${String(added.length)} new ID(s)` +
      (added.length === 0 ? "." : added.length <= 20 ? `: ${added.join(", ")}` : "."),
  );
  return added;
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    seed();
  } catch (error) {
    console.error(`seed-manifest: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  }
}
