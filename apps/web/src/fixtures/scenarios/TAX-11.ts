// TAX-11 fixture scenarios (T-06-T23, DEC-5636; T-06-T53, DEC-6035; docs/screens/TAX-11.md): one per
// artboard, with the contract's persona and demo clock. The pages, page 1's and Schedule K's typed
// values, the diagnostics in code's words and the K-1 list are the Python scenario's
// (`seed/scenario.tax11-preview.json`, `make fixtures`, never hand written): a, b and c at E0 (two
// blocking diagnostics and the M-2 warning), d after the fix and the §754 decision (all clear),
// e while the pages are still rendering. The return record is E0's.
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { taxEntityHandlers } from "../handlers/tax-entity";
import { taxReturnHandlers } from "../handlers/tax-returns";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { RIDGELINE_RETURN } from "../seed/k1-packages";
import { stableId } from "../seed/prng";
import exported from "../seed/scenario.tax11-preview.json";
import { capabilitiesFor } from "../seed/shell";
import type { Snapshot } from "../seed/tax-entity";

export { RIDGELINE_RETURN };
const E0 = seedScenario();
const CHECKPOINT = stableId("checkpoint:ridgeline:2025:approved");

type Moment = "e0" | "after_fix";

function diagnostics(moment: Moment) {
  const items = exported.diagnostics[moment].map((d) => ({
    ...d,
    severity: d.severity as "blocking" | "warning" | "clear",
    // A failing rule links the open issue raised under its reference (T-06-T50).
    issue_id: d.severity === "clear" ? null : stableId(`issue:ridgeline:2025:${d.rule_key}`),
  }));
  return { items, blocking: items.filter((d) => d.severity === "blocking").length };
}

function pages(moment: Moment) {
  const found = diagnostics(moment).items;
  return {
    checkpoint_id: CHECKPOINT,
    watermark: "Draft — not for filing" as const,
    pages: exported.pages.map((p) => ({
      page_key: p.page_key,
      caption: p.caption,
      blocking: found.filter((d) => d.severity === "blocking" && d.page_key === p.page_key).length,
      rendered: !p.placeholder,
      placeholder: p.placeholder,
    })),
  };
}

function fields(pageKey: string) {
  const typed =
    (exported.fields as Record<string, { field_key: string; label: string; value: string }[]>)[
      pageKey
    ] ?? [];
  // The face's boxes are the template's; the preview's values list does not draw them.
  return { items: typed.map((f) => ({ ...f, rect: ["0", "0", "0", "0"] })) };
}

function at(
  state: string,
  clock: string,
  snapshot: Snapshot,
  moment: Moment,
  loading = false,
): Scenario {
  return {
    state,
    persona: "daniel-reyes",
    clock,
    get handlers() {
      const own: Record<string, FixtureHandler> = {
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? "daniel-reyes");
          return json({ ...base, flags: { ...base.flags, "tax.form_preview": true } });
        },
        "GET /v1/tax-returns/{return_id}/form-pages": () =>
          loading ? never() : json(pages(moment)),
        "GET /v1/tax-returns/{return_id}/form-pages/{page_key}/fields": ({ params }) =>
          json(fields(params.page_key ?? "")),
        "GET /v1/tax-returns/{return_id}/diagnostics": () => json(diagnostics(moment)),
        "GET /v1/tax-returns/{return_id}/k1-previews": () => json(exported.k1),
      };
      // The return's record is the tax-returns frame's (the entity handlers know another id).
      const record = taxReturnHandlers()["GET /v1/tax-returns/{return_id}"];
      return {
        ...E0.handlers,
        ...taxEntityHandlers(snapshot),
        ...(record === undefined ? {} : { "GET /v1/tax-returns/{return_id}": record }),
        ...own,
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", "2026-09-14T09:24:00-05:00", "run2", "e0"), // Page 1 (2 blocking diagnostics + §754 pending) · `ridgeline-e0`
  b: at("b", "2026-09-14T09:24:00-05:00", "run2", "e0"), // K-1 · Jonah Feld (Item L 1,550 expected) · `ridgeline-e0`
  c: at("c", "2026-09-14T09:24:00-05:00", "run2", "e0"), // Schedule K page · `ridgeline-e0`
  d: at("d", "2026-09-14T09:51:00-05:00", "afterFix", "after_fix"), // Diagnostics clear (Approve return… enabled) · `ridgeline-m2-accepted`
  e: at("e", "2026-09-14T09:24:00-05:00", "run2", "e0", true), // Loading (form-rule skeleton) · `ridgeline-e0`
});

export type Tax11State = keyof typeof scenarios;

/** How each artboard opens: the page, or the partner's K-1. */
export const INITIAL: Record<Tax11State, { page?: string; k1?: string }> = {
  a: { page: "p1" },
  b: { k1: "Jonah Feld" },
  c: { page: "p4" },
  d: { page: "p1" },
  e: {},
};
