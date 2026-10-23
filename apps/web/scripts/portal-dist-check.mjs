// The portal build's acceptance (P-08-T07; DEC-59, ADR-163, INV-4): after `vite build --mode
// portal`, dist/portal holds
//   - no firm chunk: no chunk built from the firm shell, the firm's routes, a firm screen, a legacy
//     screen or the gallery (read from the build manifest's source keys);
//   - no product name: no "Accrued" in any emitted text file, whatever its case;
//   - no fixture string: no "Brightwater", "Northwind" or "scenario" (the seed and its scenarios
//     never ship; F-04's production-dist rule).
// Dependency-free.
//
//   node scripts/portal-dist-check.mjs [dist/portal]      (after `pnpm build:portal`)
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const FIRM_SOURCE =
  /(?:^|\/)src\/(?:shell|routes\/firm|routes\/root|legacy|gallery|screens\/(?!POR-)[A-Z]{2,4}-\d+)(?:\/|\.|$)/;
const PRODUCT = /accrued/i;
// The one sanctioned occurrence: the wordmark's accessible name, which renders only inside the
// "Secured by" footer a firm may turn on (DEC-15, ADR-163; F-05-T39's crawl exempts the same
// footer at run time). It is the default of `Wordmark`'s `label` prop, minified as
// `label:x=\`Accrued\``. Moving the footer into a chunk loaded only when `secured_footer` is on
// removes it (docs/screens/POR-01.md, Open gaps); until then nothing else may match.
const SECURED_FOOTER_LABEL = /label:[\w$]+=`Accrued`/g;
const FIXTURE = /Brightwater|Northwind|scenario/;
const TEXT = /\.(?:js|mjs|css|html|json|map|txt|svg)$/;

/** Every file under `dir`, relative paths. @param {string} dir @returns {string[]} */
function walk(dir, prefix = "") {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    const rel = prefix === "" ? name : `${prefix}/${name}`;
    return statSync(path).isDirectory() ? walk(path, rel) : [rel];
  });
}

/**
 * The problems in a built portal: firm chunks, product-name hits and fixture-string hits.
 * @param {Record<string, {file: string, src?: string}>} manifest
 * @param {Record<string, string>} files relative path → text
 */
export function portalProblems(manifest, files) {
  const problems = [];
  for (const [key, chunk] of Object.entries(manifest)) {
    const source = chunk.src ?? key;
    if (FIRM_SOURCE.test(source)) problems.push(`firm chunk: ${source} → ${chunk.file}`);
  }
  for (const [path, text] of Object.entries(files)) {
    if (path.startsWith(".vite/")) continue;
    const labels = text.match(SECURED_FOOTER_LABEL) ?? [];
    if (labels.length > 1)
      problems.push(`product name in ${path} (${String(labels.length)} labels)`);
    if (PRODUCT.test(text.replace(SECURED_FOOTER_LABEL, ""))) {
      problems.push(`product name in ${path}`);
    }
    const fixture = FIXTURE.exec(text);
    if (fixture !== null) problems.push(`fixture string "${fixture[0]}" in ${path}`);
  }
  return problems;
}

function main(dist) {
  const manifestPath = `${dist}/.vite/manifest.json`;
  if (!existsSync(manifestPath)) {
    console.error(`portal-dist-check: ${manifestPath} is missing; run pnpm build:portal first`);
    return 1;
  }
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  const files = Object.fromEntries(
    walk(dist)
      .filter((f) => TEXT.test(f))
      .map((f) => [f, readFileSync(join(dist, f), "utf8")]),
  );
  const problems = portalProblems(manifest, files);
  for (const p of problems) console.error(`portal-dist-check: ${p}`);
  if (problems.length === 0) {
    console.log(`portal-dist-check: ${String(Object.keys(files).length)} files clean`);
  }
  return problems.length === 0 ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1] ?? ""}`) {
  process.exitCode = main(process.argv[2] ?? "dist/portal");
}
