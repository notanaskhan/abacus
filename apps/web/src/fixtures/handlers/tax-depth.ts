// T-06-T29 to T31: the T-06 entity depth routes in fixture mode over the T-05 workbook handlers
// (TXP-03 fixed assets, TXP-04 book-tax, TXP-08 basis). Reads answer the seed's shapes; writes
// answer 501 as the contract stubs do until their service rows land (the gallery never persists).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "./tax-entity";
import type { Snapshot } from "../seed/tax-entity";
import { type AssetView, type AssetsVariant, fixedAssets, rowsOf } from "../seed/tax-depth-assets";
import { type BookTaxVariant, M1, M3, m2 } from "../seed/tax-depth-booktax";
import type { IssuesState } from "../seed/tax-entity-issues";

const R = "/v1/tax-returns/{return_id}";
const notYet = () => json({ detail: "not_implemented" }, 501);

export interface DepthOptions {
  assets?: AssetsVariant;
  bookTax?: BookTaxVariant;
  /** The T-05 issue queue's state (TXP-10; d: the M-2 fix applied). */
  issues?: IssuesState;
}

const VIEWS: readonly AssetView[] = ["register", "by_property", "dispositions"];

function section(key: string, title: string, signed: boolean) {
  return {
    key,
    title,
    seen_hash: "0".repeat(64),
    signed_levels: signed ? ["l2"] : [],
    stale_levels: [],
    tallies: [],
  };
}

export function taxDepthHandlers(
  snapshot: Snapshot,
  options: DepthOptions = {},
): Record<string, FixtureHandler> {
  const assets = options.assets ?? "e0";
  const bookTax = options.bookTax ?? "e0";
  return {
    ...taxEntityHandlers(snapshot, options.issues === undefined ? {} : { issues: options.issues }),
    [`GET ${R}/schedules/m3`]: () => json(M3),
    [`GET ${R}/schedules/m1`]: () => json(M1),
    [`GET ${R}/schedules/m2`]: (req) =>
      json(m2(req.query.get("variant") === "with_fix" ? "with_fix" : "as_drafted", bookTax)),
    [`GET ${R}/sections`]: () =>
      json({
        items: [
          section("capital-accounts", "Capital Accounts", false),
          section("fixed-assets", "Fixed Assets", assets === "signedOff"),
        ],
      }),
    [`GET ${R}/fixed-assets`]: (req) => {
      const asked = req.query.get("view") as AssetView | null;
      return json(
        fixedAssets(asked !== null && VIEWS.includes(asked) ? asked : "register", assets),
      );
    },
    [`GET ${R}/fixed-assets/{asset_id}`]: (req) => {
      const found = rowsOf(assets).find((r) => r.asset_id === req.params.asset_id);
      return found === undefined ? json({ detail: "not_found" }, 404) : json(found);
    },
    [`POST ${R}/fixed-assets`]: notYet,
    [`POST ${R}/fixed-assets/{asset_id}/changes`]: notYet,
  };
}
