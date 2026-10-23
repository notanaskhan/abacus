// The names and figures the gallery's specimens show (F-05-T33; F-05 "Fixture scenarios"; plan 04
// lint L10). They are the Brightwater Hale seed's own, at E0 (Mon Sep 14, 2026, 9:24 AM CT): the
// app's seed test (apps/web/src/fixtures/specimen-figures.test.ts) checks every one against the seed
// and that each sum foots. Kit sample data is never ported (DF-35).

/** E0: the demo instant every specimen is drawn at. */
export const E0 = "2026-09-14T09:24:00-05:00";

export const FIRM = "Brightwater Hale";
export const FELD = "Jonah & Claire Feld";
export const RIDGELINE = "Ridgeline Property Partners, LP";
export const COPPERLEAF = "Copperleaf Coffee Roasters, Inc.";
export const NORTHWIND = "Northwind Robotics, Inc.";
export const NORTHWIND_PLAN = "Northwind Robotics 401(k) Plan";
export const GRANITE_PEAK = "Granite Peak Outdoor Supply, Inc.";

/** Staff the specimens name; each is a seat holder in the seed. */
export const STAFF = {
  hannah: "Hannah Leclerc",
  samuel: "Samuel Ito",
  kevin: "Kevin Osei",
  priya: "Priya Raman",
  margaret: "Margaret Okonkwo",
  raj: "Raj Malhotra",
  daniel: "Daniel Reyes",
  olivia: "Olivia Brandt",
} as const;

/** Persona slugs the specimens are seen as (`?as=`), including F-05-T33's two. */
export const PERSONAS = ["hannah-leclerc", "samuel-ito", "jonah-feld", "dana-whitley"] as const;

/**
 * Northwind PY2025 (blueprint 01 §9.4), as decimal strings. Unadjusted plus the contributions
 * receivable foots to the net assets available at Dec 31, 2025.
 */
export const NORTHWIND_FIGURES = {
  netAssetsUnadjusted: "16812400.00",
  contributionsReceivable: "48600.00",
  netAssetsAvailable20251231: "16861000.00",
  netAssetsAvailable20250101: "14228500.00",
} as const;

/**
 * Northwind's change in net assets over PY2025, as a server would send it with a variance cell:
 * the change foots Jan 1 to Dec 31 (FOOTINGS); the ratio is the change over the Jan 1 base.
 */
export const NORTHWIND_CHANGE = {
  netAssetsChange: "2632500.00",
  ratio: "0.1850",
} as const;

/** Request lists a specimen counts (blueprint 01 §9.3): the seed's own items. */
export const REQUEST_COUNTS = {
  northwind: { received: 11, total: 24 },
  feld: { received: 5, total: 7 },
  granitePeak: { sent: 0, total: 41 },
} as const;

/** TY2025 returns by office (TPL-12): Chicago, Denver, New York. */
export const RETURNS_BY_OFFICE = { Chicago: 98, Denver: 64, "New York": 62 } as const;

/** Every footing a specimen draws: `parts` add up to `total` (checked in the seed test). */
export const FOOTINGS: readonly { name: string; parts: readonly string[]; total: string }[] = [
  {
    name: "Northwind net assets at Dec 31, 2025",
    parts: [NORTHWIND_FIGURES.netAssetsUnadjusted, NORTHWIND_FIGURES.contributionsReceivable],
    total: NORTHWIND_FIGURES.netAssetsAvailable20251231,
  },
  {
    name: "Northwind net assets over PY2025",
    parts: [NORTHWIND_FIGURES.netAssetsAvailable20250101, NORTHWIND_CHANGE.netAssetsChange],
    total: NORTHWIND_FIGURES.netAssetsAvailable20251231,
  },
  {
    name: "TY2025 returns by office",
    parts: Object.values(RETURNS_BY_OFFICE).map(String),
    total: "224",
  },
];
