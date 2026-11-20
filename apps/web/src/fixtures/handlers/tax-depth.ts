// T-06-T29 to T31: the T-06 entity depth routes in fixture mode over the T-05 workbook handlers
// (TXP-03 fixed assets, TXP-04 book-tax, TXP-08 basis). Reads answer the seed's shapes; writes
// answer 501 as the contract stubs do until their service rows land (the gallery never persists).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "./tax-entity";
import type { Snapshot } from "../seed/tax-entity";
import { type AssetView, type AssetsVariant, fixedAssets, rowsOf } from "../seed/tax-depth-assets";

const R = "/v1/tax-returns/{return_id}";
const notYet = () => json({ detail: "not_implemented" }, 501);

export interface DepthOptions {
  assets?: AssetsVariant;
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
  return {
    ...taxEntityHandlers(snapshot),
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
