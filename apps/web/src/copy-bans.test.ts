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

// A-08-T01 (SPEC-657 AC-8.7; A-08 §4.9): SSARS surfaces say "conclusion", never "opinion" (AR-C 90).
const SSARS_ROOTS = [
  join(WEB, "src", "screens", "AUD-26"),
  join(WEB, "src", "domain", "audits", "fieldwork", "ssars"),
];
const OPINION = /\bopinions?\b/iu;

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

describe("copy bans (A-08 SSARS)", () => {
  it("AUD-26 never says opinion", () => {
    const hits = SSARS_ROOTS.flatMap(existing).filter((path) =>
      OPINION.test(readFileSync(path, "utf8")),
    );
    expect(hits).toEqual([]);
  });

  it("the ban catches opinion and spares conclusion", () => {
    expect(OPINION.test("Review opinion")).toBe(true);
    expect(OPINION.test("No conclusion yet")).toBe(false);
  });
});

// A-09-T04 (SPEC-658 AC-0.2): SAS 149 has no "significant component", and nothing is ever posted to
// a client system (ADR-040). Scans the group screens and the group-audit domain folder.
const GROUP_ROOTS = ["AUD-32", "AUD-33", "AUD-34", "AUD-35", "POR-23"]
  .map((id) => join(WEB, "src", "screens", id))
  .concat([join(WEB, "src", "domain", "group-audit")]);
const GROUP_BANNED = /\bsignificant components?\b|\bpost to netsuite\b/iu;

describe("copy bans (A-09 group audit)", () => {
  it("group screens never say significant component or Post to NetSuite", () => {
    const hits = GROUP_ROOTS.flatMap(existing).filter((path) =>
      GROUP_BANNED.test(readFileSync(path, "utf8")),
    );
    expect(hits).toEqual([]);
  });

  it("the ban catches both phrases and spares component", () => {
    expect(GROUP_BANNED.test("Significant component")).toBe(true);
    expect(GROUP_BANNED.test("Post to NetSuite")).toBe(true);
    expect(GROUP_BANNED.test("Component: Harlow & Pike Distribution, Inc.")).toBe(false);
  });
});
