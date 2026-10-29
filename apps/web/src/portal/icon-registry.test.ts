// @vitest-environment node
// DEC-1006: the portal build ships the UI kit's portal icon subset (vite.config.ts `portalIcons`).
// It must hold every icon name portal-reachable code can render, each as the same glyph the full
// registry draws, or a portal page would break on a name it lacks. "Portal-reachable" is the UI kit
// (every component a portal screen may use) plus the portal's own code; a string literal there that
// is a registered icon name counts as rendered, so the subset is a superset of what is used.
import { ICONS, type IconName } from "@abacus/ui";
import { ICONS as PORTAL_ICONS, PORTAL_ICON_NAMES } from "@abacus/ui/icons/portal-registry";
import { beforeAll, describe, expect, it } from "vitest";

type Dirent = { name: string; isDirectory: () => boolean };
type Fs = {
  existsSync: (path: string) => boolean;
  readdirSync: (path: string, options: { withFileTypes: true }) => Dirent[];
  readFileSync: (path: string, encoding: "utf8") => string;
};
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
const SKIP_DIRS = new Set(["icons", "specimens", "node_modules"]);
let fs: Fs;

beforeAll(async () => {
  const fsModule = "node:fs";
  fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
});

function sources(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) sources(full, out);
    } else if (/\.tsx?$/.test(entry.name) && !/\.(test|stories)\./.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function portalReachableNames(): Set<IconName> {
  const known = new Set(Object.keys(ICONS));
  const screens = fs
    .readdirSync(`${cwd}/src/screens`, { withFileTypes: true })
    .filter((e) => e.name.startsWith("POR-"))
    .map((e) => `${cwd}/src/screens/${e.name}`);
  const dirs = [
    `${cwd}/../../packages/ui/src`,
    `${cwd}/src/portal`,
    `${cwd}/src/domain/portal`,
    `${cwd}/src/routes/portal`,
    `${cwd}/src/entries`,
    `${cwd}/src/app-core`,
    ...screens,
  ];
  const found = new Set<IconName>();
  for (const file of dirs.flatMap((d) => sources(d))) {
    for (const match of fs.readFileSync(file, "utf8").matchAll(/["'`]([a-z0-9-]+)["'`]/g)) {
      const name = match[1];
      if (name !== undefined && known.has(name)) found.add(name as IconName);
    }
  }
  return found;
}

describe("the portal icon subset (DEC-1006)", () => {
  it("holds every icon name portal-reachable code can render", () => {
    const missing = [...portalReachableNames()].filter((n) => !PORTAL_ICON_NAMES.includes(n));
    expect(missing).toEqual([]);
  });

  it("draws each name with the full registry's glyph", () => {
    for (const name of PORTAL_ICON_NAMES) {
      expect(PORTAL_ICONS[name], name).toBe(ICONS[name]);
    }
  });
});
