// The local screen parity report's rows (F-04-T33; F-04.34): one row per artboard of every screen
// the route registry marks `fixture` or `live`, with the tier and lock its screen contract's
// "## Parity" table gives it (docs/screens/<ID>.md). Pure, so vitest can check it
// (screen-rows.test.ts); screens.spec.ts renders and measures the rows, and the parity reporter
// writes parity-report/screens/parity.json and index.html. No PNG is ever committed: baselines are
// the handoff's own pixels, fetched into the git-ignored .visual/ (D-DS-12).

export type ScreenTier = "A" | "B" | "C" | "D";
export type Gate = "blocking" | "report-only";

export interface ScreenRow {
  /** `CLI-01a`; a Tier D row is the screen's host frame: `CLI-01 host`. */
  artboard: string;
  screen: string;
  /** The scenario letter (`a`, `a2`), or `host` for the Tier D frame. */
  state: string;
  tier: ScreenTier;
  locked: boolean;
  gate: Gate;
  /** The parity-manifest key whose cropped baseline this row is compared with. */
  baselineKey: string;
}

export interface ScreenResult extends ScreenRow {
  diffPercent: number | null;
  /** passed, failed, unmeasured (no baseline, or Tier D measured by tier-d.spec.ts). */
  status: "passed" | "failed" | "unmeasured";
  note: string | null;
}

const LETTERS = "abcdefghijklmnopqrstuvwxyz";

/** `a–g`, `a, b, d`, `a b c g`, `a2`, `host` → the states the cell names. */
export function statesOf(cell: string): string[] {
  const out: string[] = [];
  for (const part of cell.split(/[,\s]+/).filter((p) => p.length > 0)) {
    const range = /^([a-z])[–-]([a-z])$/.exec(part);
    if (range?.[1] !== undefined && range[2] !== undefined) {
      const from = LETTERS.indexOf(range[1]);
      const to = LETTERS.indexOf(range[2]);
      for (let i = from; i <= to; i += 1) out.push(LETTERS.charAt(i));
    } else if (/^([a-z]\d?|host)$/.test(part)) {
      out.push(part);
    }
  }
  return out;
}

/** Locked now, not scheduled: "C (locked)" is; "C (locked before M8)", "locked by Fri Apr 30" and
 * "P0 lock before M8" are not yet. */
export function isLocked(text: string): boolean {
  return /\blocked\b(?!\s+(before|by|at|in|from)\b)/i.test(text);
}

export function gateOf(tier: ScreenTier, locked: boolean): Gate {
  return tier === "A" || tier === "D" || (tier === "B" && locked) ? "blocking" : "report-only";
}

/** The `## Parity` table of a screen contract: `| Artboard | Tier | Diff % | Notes |` rows. */
export function contractRows(screen: string, markdown: string): ScreenRow[] {
  const section = /^## Parity\s*$([\s\S]*?)(?=^## |(?![\s\S]))/m.exec(markdown)?.[1] ?? "";
  const rows: ScreenRow[] = [];
  for (const line of section.split("\n")) {
    const cells = line.split("|").map((c) => c.trim());
    if (cells.length < 4) continue;
    const [, artboards = "", tierCell = "", , notes = ""] = cells;
    const tier = /^([ABCD])\b/.exec(tierCell)?.[1] as ScreenTier | undefined;
    if (tier === undefined) continue; // the header, the rule, and deferred rows ("—")
    const locked = isLocked(tierCell) || isLocked(notes);
    for (const state of statesOf(artboards)) {
      const host = state === "host";
      rows.push({
        artboard: host ? `${screen} host` : `${screen}${state}`,
        screen,
        state,
        tier,
        locked,
        gate: gateOf(tier, locked),
        baselineKey: `${screen.toLowerCase()}${host ? "" : state}.window`,
      });
    }
  }
  return rows;
}

/** The route registry's statuses read from its source files (src/routes/manifest/<area>.ts), as
 * scripts/seed-manifest.mjs reads them: e2e code does not import the app's modules.
 * screen-parity.test.ts checks the result equals the registry itself. */
export function statusesFromSource(
  sources: readonly string[],
): Record<string, { status: string }> {
  const out: Record<string, { status: string }> = {};
  for (const source of sources) {
    const starts = [...source.matchAll(/^ {2}"([A-Z]+-\d+)": \{/gm)];
    starts.forEach((start, i) => {
      const id = start[1];
      const end = starts[i + 1]?.index ?? source.length;
      const status = /\bstatus: "(planned|fixture|live)"/.exec(
        source.slice(start.index, end),
      )?.[1];
      if (id !== undefined && status !== undefined) out[id] = { status };
    });
  }
  return out;
}

/** Every artboard of every `fixture` or `live` screen, in screen then state order. Screens whose
 * contract has no parity table are listed by `missing`. */
export function screenRows(
  manifest: Readonly<Record<string, { status: string }>>,
  contractOf: (screen: string) => string | null,
): { rows: ScreenRow[]; missing: string[] } {
  const rows: ScreenRow[] = [];
  const missing: string[] = [];
  for (const screen of Object.keys(manifest).sort()) {
    const status = manifest[screen]?.status;
    if (status !== "fixture" && status !== "live") continue;
    const markdown = contractOf(screen);
    const found = markdown === null ? [] : contractRows(screen, markdown);
    if (found.length === 0) missing.push(screen);
    rows.push(...found);
  }
  return { rows, missing };
}

/** A row's outcome: a blocking row fails over its tier's ratio; unmeasured never fails. */
export function judge(
  row: ScreenRow,
  diffPercent: number | null,
  maxPercent: number,
  note: string | null = null,
): ScreenResult {
  if (diffPercent === null) return { ...row, diffPercent, status: "unmeasured", note };
  const over = diffPercent > maxPercent;
  return {
    ...row,
    diffPercent,
    status: over && row.gate === "blocking" ? "failed" : "passed",
    note,
  };
}

function escape(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

/** The HTML report: artboard → diff % → tier → locked, blocking failures first. */
export function renderHtml(
  results: readonly ScreenResult[],
  handoffVersion: string,
  missing: readonly string[] = [],
): string {
  const order = { failed: 0, unmeasured: 1, passed: 2 } as const;
  const sorted = [...results].sort(
    (a, b) => order[a.status] - order[b.status] || a.artboard.localeCompare(b.artboard),
  );
  const rows = sorted
    .map(
      (r) =>
        `<tr class="${r.status}"><td>${escape(r.artboard)}</td>` +
        `<td>${r.diffPercent === null ? "—" : `${r.diffPercent.toFixed(2)} %`}</td>` +
        `<td>${r.tier}</td><td>${r.locked ? "locked" : "—"}</td><td>${r.gate}</td>` +
        `<td>${r.status}</td><td>${escape(r.note ?? "")}</td></tr>`,
    )
    .join("\n");
  const failed = results.filter((r) => r.status === "failed").length;
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Screen parity</title>
<style>body{font:13px system-ui,sans-serif;margin:24px}table{border-collapse:collapse}
td,th{border-bottom:1px solid;padding:4px 10px;text-align:left}
tr.failed td{font-weight:600}tr.unmeasured td{opacity:.6}</style></head>
<body><h1>Screen parity</h1>
<p>Handoff ${escape(handoffVersion)} · ${String(results.length)} artboards · ${String(failed)} blocking failure(s).
Tier A and D block; B blocks once locked; C is report-only.</p>
${missing.length === 0 ? "" : `<p>Built screens whose contract has no Parity table (not measured): ${escape(missing.join(", "))}.</p>\n`}<table><thead><tr><th>Artboard</th><th>Diff</th><th>Tier</th><th>Locked</th><th>Gate</th><th>Status</th><th>Note</th></tr></thead>
<tbody>
${rows}
</tbody></table></body></html>
`;
}
