import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Tax Returns (T-02 §5.1): `/tax-returns` is TAX-01 (T-02-T12) and `/tax-returns/$returnId` the
// `ReturnFrame` on TAX-02 (T-02-T14; every form family, DV-5), behind `tax.returns_v1`. While the
// flag is off the area shows F-05's flag-off state, never a 404. TAX-01 keeps its tile, office
// grouping, search and tax year in the URL (`?tile=`, `?office=`, `?q=`, `?tax_year=`).

const PracticeBoard = lazyScreen(async () => (await import("../../screens/TAX-01")).TAX01);
const ReturnOverview = lazyScreen(async () => (await import("../../screens/TAX-02")).TAX02);

function gated(children: JSX.Element): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FeatureGate
        flag="tax.returns_v1"
        fallback={<FlagOffState flag="tax.returns_v1" label="Tax Returns" />}
      >
        {children}
      </FeatureGate>
    </div>
  );
}

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
    return gated(
      <PracticeBoard
        search={search}
        onSearch={(next) => {
          void navigate({ to: ".", search: next, replace: true });
        }}
        onOpen={(row) => {
          void navigate({ to: "/tax-returns/$returnId", params: { returnId: row.id } });
        }}
      />,
    );
  },
});

export const taxReturnRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId",
  component: function TaxReturnPage(): JSX.Element {
    const returnId = useParam("returnId");
    return gated(<ReturnOverview returnId={returnId} />);
  },
});

export const taxReturnRoutes = [taxReturnsRoute, taxReturnRoute] as const;
