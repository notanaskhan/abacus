// T-06-T29 (TASK-8751): the Ridgeline 2025 Form 1065 fixed-asset register in fixture mode, as
// `GET /v1/tax-returns/{id}/fixed-assets` answers it (TXP-03 a–e). Every name, date and figure is
// the T-06-T22 Ridgeline depth slice's (backend abacus_tools/synthetic/scenarios/brightwater_hale/
// ridgeline_depth_slice.py REGISTER, LAND, PROPERTY_OF), which takes them from the TXP-03 handoff.
// The totals are the slice's computed figures; tax-depth-assets.foot.test.ts re-adds the rows, so
// a changed row fails there, never on screen (ADR-050).
import type { TaxDepthAssetRowOut, TaxDepthFixedAssetsOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type AssetView = TaxDepthFixedAssetsOut["view"];
/** e0 (TXP-03 a, a2, b, d), bonusResolved (c, Feb 3, 2025 contract matched) and signedOff (e). */
export type AssetsVariant = "e0" | "bonusResolved" | "signedOff";

export const LARIMER_INVOICE = "Larimer_Parking_Invoice_Feb2025.pdf";
export const BONUS_CUTOFF = "2025-01-19";
export const LARIMER_CONTRACT = "2025-02-03";
export const ROOF_ID = stableId("asset:ridgeline:elm-street-roof");
export const PARKING_ID = stableId("asset:ridgeline:larimer-parking");

type Row = Omit<TaxDepthAssetRowOut, "bonus_check"> & {
  bonus_check?: TaxDepthAssetRowOut["bonus_check"];
};

const row = (key: string, r: Omit<Row, "asset_id">): Row => ({
  asset_id: stableId(`asset:ridgeline:${key}`),
  ...r,
});

const ROWS: readonly Row[] = [
  row("elm-street-building", {
    description: "Elm Street building",
    property_key: "elm-street",
    placed_in_service: "2018-04-01",
    cost: "6240000",
    recovery_class: "39",
    method: "SL",
    convention: "MM",
    bonus_pct: "0",
    prior: "1073333",
    current: "160000",
    accumulated: "1233333",
    bonus_check: "not_eligible",
    cell_ref: "02 Fixed Assets!E8",
  }),
  row("larimer-lofts", {
    description: "Larimer Lofts",
    property_key: "larimer",
    placed_in_service: "2021-06-01",
    cost: "4950000",
    recovery_class: "27.5",
    method: "SL",
    convention: "MM",
    bonus_pct: "0",
    prior: "637500",
    current: "180000",
    accumulated: "817500",
    bonus_check: "not_eligible",
    cell_ref: "02 Fixed Assets!E9",
  }),
  row("bergen-street", {
    description: "Bergen Street",
    property_key: "bergen",
    placed_in_service: "2023-09-01",
    cost: "3850000",
    recovery_class: "27.5",
    method: "SL",
    convention: "MM",
    bonus_pct: "0",
    prior: "180834",
    current: "140000",
    accumulated: "320834",
    bonus_check: "not_eligible",
    cell_ref: "02 Fixed Assets!E10",
  }),
  {
    asset_id: ROOF_ID,
    description: "Elm Street roof replacement",
    property_key: "elm-street",
    placed_in_service: "2025-03-10",
    cost: "468000",
    recovery_class: "39",
    method: "SL",
    convention: "MM",
    bonus_pct: "0",
    prior: "0",
    current: "9500",
    accumulated: "9500",
    bonus_check: "not_eligible",
    flags: 1,
    cell_ref: "02 Fixed Assets!E11",
  },
  {
    asset_id: PARKING_ID,
    description: "Larimer parking lot resurfacing",
    property_key: "larimer",
    placed_in_service: "2025-02-14",
    cost: "180000",
    recovery_class: "15",
    method: "150DB",
    convention: "HY",
    bonus_pct: "100",
    prior: "0",
    current: "180000",
    accumulated: "180000",
    cell_ref: "02 Fixed Assets!E12",
  },
  row("bergen-appliances", {
    description: "Bergen Street appliances",
    property_key: "bergen",
    placed_in_service: "2025-08-01",
    cost: "64000",
    recovery_class: "5",
    method: "200DB",
    convention: "HY",
    bonus_pct: "100",
    prior: "0",
    current: "64000",
    accumulated: "64000",
    bonus_check: "tie",
    cell_ref: "02 Fixed Assets!E13",
  }),
];

/** Form 8825 by property (TXP-03 b): land is not depreciable. */
export const PROPERTIES = [
  {
    property_key: "elm-street",
    name: "Elm Street, Chicago",
    land: "1400000",
    depreciation: "169500",
  },
  {
    property_key: "larimer",
    name: "Larimer Lofts, Denver",
    land: "1300000",
    depreciation: "360000",
  },
  {
    property_key: "bergen",
    name: "Bergen Street, Brooklyn",
    land: "900000",
    depreciation: "204000",
  },
] as const;

export function rowsOf(variant: AssetsVariant): TaxDepthAssetRowOut[] {
  return ROWS.map((r) => ({
    ...r,
    bonus_check:
      r.asset_id === PARKING_ID ? (variant === "e0" ? "check" : "tie") : (r.bonus_check ?? "tie"),
  }));
}

export function fixedAssets(view: AssetView, variant: AssetsVariant): TaxDepthFixedAssetsOut {
  return {
    view,
    rows: view === "dispositions" ? [] : rowsOf(variant),
    by_property: view === "by_property" ? PROPERTIES.map((p) => ({ ...p })) : [],
    depreciable_cost: "15752000",
    land: "3600000",
    current: "733500",
    accumulated: "2625167",
    ties_to_tb: "tie",
    book_equals_tax: "tie",
    bonus_eligibility: variant === "e0" ? "check" : "tie",
    dispositions: 0,
    engine_version: "E3 1.0.0",
    inputs_hash: (variant === "e0" ? "3" : "4").repeat(64),
  };
}
