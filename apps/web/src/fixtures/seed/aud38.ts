// AUD-38 and TXP-13 d (T-06-T45; TASK-8935; DEC-5937): Granite Peak's FY2026 hand-off previews
// (a ready, b needs review, d not available, e superseded) and the 1120's landing, exported from
// the Python slice (`tb_handoff_slice.aud38_rows`, `scenario.aud38.json`). Every count, figure
// and name is the code's there; this file only hands them to the scenarios.
import type {
  TbHandoffLandingOut,
  TbHandoffOut,
  TbHandoffPreviewOut,
  TbHandoffTargetsOut,
} from "@abacus/api-client";
import exported from "./scenario.aud38.json";
import { stableId } from "./prng";

const DATA = exported as unknown as {
  preview_ready: TbHandoffPreviewOut;
  preview_needs_review: TbHandoffPreviewOut;
  preview_not_available: TbHandoffPreviewOut;
  preview_superseded: TbHandoffPreviewOut;
  landing: TbHandoffLandingOut;
  target: { target_work_item_id: string; return_label: string; tax_year: number };
  handed_off_at: string;
};

export type Aud38Preview = "ready" | "needs_review" | "not_available" | "superseded";

export const AUD38_TARGET = DATA.target.target_work_item_id;
export const AUD38_LANDING = DATA.landing;

export function targets(): TbHandoffTargetsOut {
  return { items: [DATA.target], total: 1 };
}

export function preview(which: Aud38Preview): TbHandoffPreviewOut {
  return {
    ready: DATA.preview_ready,
    needs_review: DATA.preview_needs_review,
    not_available: DATA.preview_not_available,
    superseded: DATA.preview_superseded,
  }[which];
}

/** What the create returns (c): one version, the issues toggled on, the accounts left to map. */
export function created(taxItems: readonly string[]): TbHandoffOut {
  const counts = DATA.preview_ready.counts;
  return {
    handoff_id: stableId("granite-peak-fy2026-tb-v1"),
    version_no: 1,
    source_kind: "audit_release",
    status: "handed_off",
    handed_off_at: DATA.handed_off_at,
    tax_issues_created: taxItems.length,
    accounts_to_map: counts.suggested + counts.review,
    supersedes_id: null,
  };
}
