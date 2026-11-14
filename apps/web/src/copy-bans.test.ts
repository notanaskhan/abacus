// Copy bans (T-01-T06; T-01 §3.15, R-04; DF-31): Accrued is never an ERO or a transmitter, so no
// string in the SPA or the UI kit says it transmits or e-files a return. The ERO transmits in the
// engine; Accrued records it ("Transmission record").
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const WEB = process.cwd();
const ROOTS = [join(WEB, "src"), join(WEB, "..", "..", "packages", "ui", "src")];
const BANNED =
  /\bAccrued\s+(?:transmits|will\s+transmit|e-files|files\s+(?:your|the)\s+return)\b/iu;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "node_modules" ? [] : files(path);
    return /\.(?:ts|tsx)$/u.test(name) && !name.endsWith("copy-bans.test.ts") ? [path] : [];
  });
}

// T-07-T04 (DV-2; SPEC-656 AC-15.2): the tally word on TXT-02 and TXT-04 is §3.3.1's "tie", never
// the built canvas's "Ties". Scans the two screens and the fiduciary and estate domain folders.
const TIE_ROOTS = [
  join(WEB, "src", "screens", "TXT-02"),
  join(WEB, "src", "screens", "TXT-04"),
  join(WEB, "src", "domain", "tax", "fiduciary"),
  join(WEB, "src", "domain", "tax", "estate"),
];
const TIES = /\bTies\b/u;

function existing(dir: string): string[] {
  try {
    return statSync(dir).isDirectory() ? files(dir) : [];
  } catch {
    return [];
  }
}

describe("copy bans (R-04)", () => {
  it("never says Accrued transmits or e-files a return", () => {
    const hits = ROOTS.flatMap(files).filter((path) => BANNED.test(readFileSync(path, "utf8")));
    expect(hits).toEqual([]);
  });

  it("the ban catches the phrase", () => {
    expect(BANNED.test("Accrued transmits the return")).toBe(true);
    expect(BANNED.test("Transmission record")).toBe(false);
  });
});

describe("copy bans (DV-2)", () => {
  it("TXT-02 and TXT-04 never say Ties", () => {
    const hits = TIE_ROOTS.flatMap(existing).filter((path) =>
      TIES.test(readFileSync(path, "utf8")),
    );
    expect(hits).toEqual([]);
  });

  it("the ban catches the word and spares tie", () => {
    expect(TIES.test("Σ K-1s = DEDUCTION · Ties")).toBe(true);
    expect(TIES.test("Σ K-1s = DEDUCTION · tie")).toBe(false);
  });
});
