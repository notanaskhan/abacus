// The console build's acceptance (G-04-T14; G-04 §5.3): after `vite build --mode console`,
// dist/console holds
//   - no firm or portal chunk: nothing built from the firm shell, the firm's or the portal's routes,
//     a firm or portal screen, a legacy screen or the gallery (the build manifest's source keys);
//     PLT-01 is the console's own screen and ships only in a fixture build;
//   - no fixture string: no "Brightwater", "Northwind" or "scenario" (the seed and its scenarios
//     never ship; F-04's production-dist rule), so the fixture-mode PLT-01 is absent too;
//   - the console CSP on console.html (default-src 'self', no framing).
// Dependency-free.
//
//   node scripts/console-dist-check.mjs [dist/console]      (after `pnpm build:console`)
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const FOREIGN_SOURCE =
  /(?:^|\/)src\/(?:shell|routes|legacy|gallery|portal|screens\/[A-Z]{2,4}-\d+)(?:\/|\.|$)/;
const FIXTURE = /Brightwater|Northwind|scenario/;
const TEXT = /\.(?:js|mjs|css|html|json|map|txt|svg)$/;
// Vite writes the policy's quotes as &#39;.
const CSP =
  /http-equiv="Content-Security-Policy" content="default-src (?:'|&#39;)self(?:'|&#39;);[^"]*frame-ancestors (?:'|&#39;)none(?:'|&#39;)/;

/** Every file under `dir`, relative paths. @param {string} dir @returns {string[]} */
function walk(dir, prefix = "") {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    const rel = prefix === "" ? name : `${prefix}/${name}`;
    return statSync(path).isDirectory() ? walk(path, rel) : [rel];
  });
}

/**
 * The problems in a built console: foreign chunks, fixture-string hits and a missing CSP.
 * @param {Record<string, {file: string, src?: string}>} manifest
 * @param {Record<string, string>} files relative path → text
 */
export function consoleProblems(manifest, files) {
  const problems = [];
  for (const [key, chunk] of Object.entries(manifest)) {
    const source = chunk.src ?? key;
    if (FOREIGN_SOURCE.test(source)) problems.push(`foreign chunk: ${source} → ${chunk.file}`);
  }
  for (const [path, text] of Object.entries(files)) {
    if (path.startsWith(".vite/")) continue;
    const fixture = FIXTURE.exec(text);
    if (fixture !== null) problems.push(`fixture string "${fixture[0]}" in ${path}`);
  }
  const page = files["console.html"];
  if (page === undefined) problems.push("console.html is missing");
  else if (!CSP.test(page)) problems.push("console.html has no Content-Security-Policy");
  return problems;
}

function main(dist) {
  const manifestPath = `${dist}/.vite/manifest.json`;
  if (!existsSync(manifestPath)) {
    console.error(`console-dist-check: ${manifestPath} is missing; run pnpm build:console first`);
    return 1;
  }
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const files = Object.fromEntries(
    walk(dist)
      .filter((f) => TEXT.test(f))
      .map((f) => [f, readFileSync(join(dist, f), "utf8")]),
  );
  const problems = consoleProblems(manifest, files);
  for (const p of problems) console.error(`console-dist-check: ${p}`);
  if (problems.length === 0) {
    console.log(`console-dist-check: ${String(Object.keys(files).length)} files clean`);
  }
  return problems.length === 0 ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1] ?? ""}`) {
  process.exit(main(process.argv[2] ?? "dist/console"));
}
