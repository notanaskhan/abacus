// F-05-T33 acceptance: "Every specimen figure foots in a seed test, jonah-feld and dana-whitley
// exist as fixture personas for TPL-15 and T15a, and no kit sample data such as Elena Ruiz or
// Ridgeview Partners appears in gallery data." Plus lint L10 (plan 04): canonical seed names, and a
// scan for the variant spellings gaps.md §4 lists.
import { SPECIMEN_SEED } from "@abacus/ui/specimens";
import { parseDecimal } from "@abacus/ui";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { getSeed, meFor } from "./seed";

const seed = getSeed();

describe("every specimen figure is the seed's", () => {
  it("names: the firm, the clients and the staff", () => {
    expect(seed.firm.shortName).toBe(SPECIMEN_SEED.FIRM);
    const clients = new Set(seed.clients.map((c) => c.name));
    for (const name of [
      SPECIMEN_SEED.FELD,
      SPECIMEN_SEED.RIDGELINE,
      SPECIMEN_SEED.COPPERLEAF,
      SPECIMEN_SEED.NORTHWIND,
      SPECIMEN_SEED.GRANITE_PEAK,
    ]) {
      expect(clients.has(name), name).toBe(true);
    }
    const northwind = seed.clients.find((c) => c.name === SPECIMEN_SEED.NORTHWIND);
    expect(northwind?.entities).toContain(SPECIMEN_SEED.NORTHWIND_PLAN);
    const staff = new Set(seed.staff.map((s) => s.display_name));
    for (const name of Object.values(SPECIMEN_SEED.STAFF))
      expect(staff.has(name), name).toBe(true);
  });

  it("the clock is E0", () => {
    expect(seed.clock.instant).toBe(SPECIMEN_SEED.E0);
  });

  it("the Northwind figures are the seed's, to the cent", () => {
    for (const [key, value] of Object.entries(SPECIMEN_SEED.NORTHWIND_FIGURES)) {
      expect(seed.figures.northwind[key], key).toBe(value);
    }
  });

  it("every footing a specimen draws adds up (bigint cents, never floats)", () => {
    const cents = (v: string): bigint => {
      const { units, scale } = parseDecimal(v);
      return scale >= 2 ? units / 10n ** BigInt(scale - 2) : units * 10n ** BigInt(2 - scale);
    };
    for (const f of SPECIMEN_SEED.FOOTINGS) {
      const sum = f.parts.reduce((acc, p) => acc + cents(p), 0n);
      expect(sum, f.name).toBe(cents(f.total));
    }
  });
});

describe("request counts a specimen shows are the seed's", () => {
  const items = (label: string) => seed.requestItems[seed.engagementIds[label] ?? ""] ?? [];
  it("Northwind 11 of 24 received, Feld 5 of 7, Granite Peak 0 of 41 sent", () => {
    const received = (label: string): number =>
      items(label).filter((r) => r.status === "received").length;
    expect([received("A1"), items("A1").length]).toEqual([
      SPECIMEN_SEED.REQUEST_COUNTS.northwind.received,
      SPECIMEN_SEED.REQUEST_COUNTS.northwind.total,
    ]);
    expect([received("feld"), items("feld").length]).toEqual([
      SPECIMEN_SEED.REQUEST_COUNTS.feld.received,
      SPECIMEN_SEED.REQUEST_COUNTS.feld.total,
    ]);
    const sent = items("A2").filter((r) => r.status !== "draft").length;
    expect([sent, items("A2").length]).toEqual([
      SPECIMEN_SEED.REQUEST_COUNTS.granitePeak.sent,
      SPECIMEN_SEED.REQUEST_COUNTS.granitePeak.total,
    ]);
  });
});

describe("personas", () => {
  it("every persona a specimen is seen as exists, including jonah-feld and dana-whitley", () => {
    const slugs = new Set(seed.people.map((p) => p.slug));
    for (const slug of SPECIMEN_SEED.PERSONAS) expect(slugs.has(slug), slug).toBe(true);
    expect(meFor(seed, "jonah-feld")).toBeDefined();
    expect(meFor(seed, "dana-whitley")).toBeDefined();
  });
});

// --- L10: kit sample data and variant spellings ---------------------------------------------------

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const SCANNED = ["packages/ui/src/specimens", "apps/web/src/fixtures", "apps/web/src/gallery"];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(ts|tsx|json)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

/** Kit sample data (plan 04 §… "Never port kit sample data"; F-05 DF-35). */
const KIT_SAMPLES: readonly RegExp[] = [
  /Elena Ruiz/,
  // The kit's Whitcombe household and its binder; Thomas Whitcombe is a seed partner.
  /Whitcombes\b|Whitcombe ›/,
  /Ridgeview Partners/,
  /brightwater-hale@inbox\.accrued\.app/,
  /17% \(4 \/ 24\)/,
  /86 of the 119 returns/,
  /\b21 integrations\b/,
  /13-task close run/,
];

/** Variant spellings of canonical names (handoff gaps.md §4). */
const VARIANTS: readonly RegExp[] = [
  /Claire & Jonah Feld/,
  /Ridgeline Property Partners(?!, LP)/,
  /Harborview Dental Properties(?!, LP)/,
];

describe("L10: gallery and fixture data", () => {
  const sources = SCANNED.flatMap((d) => files(join(ROOT, d))).map((path) => ({
    path: path.slice(ROOT.length + 1),
    text: readFileSync(path, "utf8"),
  }));

  it("scans something", () => {
    expect(sources.length).toBeGreaterThan(20);
  });

  it("ports no kit sample data", () => {
    const found = sources.flatMap(({ path, text }) =>
      KIT_SAMPLES.filter((re) => re.test(text)).map((re) => `${path}: ${re.source}`),
    );
    expect(found).toEqual([]);
  });

  it("spells canonical names one way", () => {
    const found = sources.flatMap(({ path, text }) =>
      VARIANTS.filter((re) => re.test(text)).map((re) => `${path}: ${re.source}`),
    );
    expect(found).toEqual([]);
  });
});
