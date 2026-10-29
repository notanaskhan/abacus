// Fixture handlers for the tax-returns v1 reads (T-02-T08): TAX-01's summary as the live route
// will answer it. Rows, records and composites join with each screen's build.
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { TY2025_SUMMARY } from "../seed/tax-returns";

export function taxReturnHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/tax-returns/summary": () => json(TY2025_SUMMARY),
  };
}
