// The bundle budgets (F-05-T17; chapter 04 section 11, FE-17): after a production build, gzip each
// JavaScript file the build manifest names and fail when
//   - the firm app's initial JavaScript (its entry chunk and everything it imports statically) is
//     over 250 KB,
//   - the portal's initial JavaScript is over 150 KB (once a build has a portal entry; today there
//     is one entry, so it is reported as not built), or
//   - one route chunk (a dynamically imported screen, with the static imports it adds to the initial
//     load) is over 120 KB.
// KB is 1000 bytes of gzip output at level 9. Dependency-free: reads dist/.vite/manifest.json
// (`build.manifest` in vite.config.ts) and gzips with node:zlib.
//
//   node scripts/bundle-budget.mjs [distDir]      (stage 1: `make check-fast`, after vite build)
import { existsSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const KB = 1000;
export const BUDGETS = { firm: 250 * KB, portal: 150 * KB, route: 120 * KB };

/** @param {string} dist @param {string} file @returns {number} */
function gzipSize(dist, file) {
  return gzipSync(readFileSync(`${dist}/${file}`), { level: 9 }).length;
}

/**
 * The chunk keys a manifest entry loads statically (itself and its `imports`, transitively).
 * @param {Record<string, {imports?: string[]}>} manifest @param {string} key @returns {Set<string>}
 */
export function staticClosure(manifest, key) {
  const seen = new Set();
  const visit = (k) => {
    if (seen.has(k) || manifest[k] === undefined) return;
    seen.add(k);
    for (const next of manifest[k].imports ?? []) visit(next);
  };
  visit(key);
  return seen;
}

/**
 * Every budget line for a manifest: `{ name, bytes, budget }`.
 * @param {Record<string, {file: string, isEntry?: boolean, isDynamicEntry?: boolean, name?: string, imports?: string[]}>} manifest
 * @param {(file: string) => number} size gzip bytes of a build file
 */
export function budgetLines(manifest, size) {
  const js = (keys) =>
    [...keys].reduce(
      (sum, k) => sum + (manifest[k].file.endsWith(".js") ? size(manifest[k].file) : 0),
      0,
    );
  const entries = Object.entries(manifest).filter(([, chunk]) => chunk.isEntry === true);
  const portal = entries.find(([key]) => /portal/i.test(key));
  const firm = entries.find(([key]) => key !== portal?.[0]);
  const lines = [];
  /** @type {Set<string>} */
  let initial = new Set();
  if (firm !== undefined) {
    initial = staticClosure(manifest, firm[0]);
    lines.push({ name: `firm initial (${firm[0]})`, bytes: js(initial), budget: BUDGETS.firm });
  }
  if (portal !== undefined) {
    lines.push({
      name: `portal initial (${portal[0]})`,
      bytes: js(staticClosure(manifest, portal[0])),
      budget: BUDGETS.portal,
    });
  }
  for (const [key, chunk] of Object.entries(manifest)) {
    if (chunk.isDynamicEntry !== true) continue;
    const added = [...staticClosure(manifest, key)].filter((k) => !initial.has(k));
    lines.push({ name: `route ${key}`, bytes: js(added), budget: BUDGETS.route });
  }
  return { lines, portal: portal !== undefined };
}

function main(dist) {
  const path = `${dist}/.vite/manifest.json`;
  if (!existsSync(path)) {
    console.error(`bundle-budget: ${path} is missing; build with vite first (build.manifest)`);
    return 1;
  }
  const manifest = JSON.parse(readFileSync(path, "utf8"));
  const { lines, portal } = budgetLines(manifest, (file) => gzipSize(dist, file));
  const over = lines.filter((l) => l.bytes > l.budget);
  const kb = (n) => `${(n / KB).toFixed(1)} KB`;
  for (const l of [...lines].sort((a, b) => b.bytes / b.budget - a.bytes / a.budget).slice(0, 6)) {
    console.log(
      `${l.bytes > l.budget ? "OVER" : "ok  "}  ${kb(l.bytes)} of ${kb(l.budget)}  ${l.name}`,
    );
  }
  if (!portal)
    console.log("portal: no portal entry in this build yet; its 150 KB budget is not checked");
  if (over.length > 0) {
    console.error(`bundle-budget: ${over.length} chunk(s) over budget`);
    return 1;
  }
  console.log(`bundle-budget: ${lines.length} budgets met`);
  return 0;
}

const invoked = process.argv[1] ?? "";
if (invoked.endsWith("bundle-budget.mjs")) process.exit(main(process.argv[2] ?? "dist"));
