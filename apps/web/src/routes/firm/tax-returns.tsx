import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Tax Returns (T-02 §5.1): `/tax-returns` is TAX-01, behind `tax.returns_v1` (T-02-T12). While the
// flag is off the area shows F-05's flag-off state, never a 404. TAX-01 keeps its tile, office
// grouping, search and tax year in the URL (`?tile=`, `?office=`, `?q=`, `?tax_year=`).

const PracticeBoard = lazyScreen(async () => (await import("../../screens/TAX-01")).TAX01);

const TAX01_SEARCH = ["tile", "office", "q", "tax_year"] as const;
type TaxReturnsSearch = Partial<Record<(typeof TAX01_SEARCH)[number], string>>;

export const taxReturnsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns",
  validateSearch: (search: Record<string, unknown>): TaxReturnsSearch =>
    Object.fromEntries(
      TAX01_SEARCH.flatMap((key) => {
        const value = search[key];
        return typeof value === "string" && value !== "" ? [[key, value]] : [];
      }),
    ),
  component: function TaxReturnsPage(): JSX.Element {
    // Loose hooks: the page also mounts in tests' routers (the same path, any tree).
    const navigate = useNavigate();
    const search: TaxReturnsSearch = useSearch({ strict: false });
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="tax.returns_v1"
          fallback={<FlagOffState flag="tax.returns_v1" label="Tax Returns" />}
        >
          <PracticeBoard
            search={search}
            onSearch={(next) => {
              void navigate({ to: ".", search: next, replace: true });
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});

export const taxReturnRoutes = [taxReturnsRoute] as const;
