import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { to } from "../to";
import { appRoute, lazyScreen } from "../root";

// Tax Returns (T-02 §5.1): `/tax-returns` is TAX-01 (T-02-T12) and `/tax-returns/$returnId` the
// `ReturnFrame` on TAX-02 (T-02-T14; every form family, DV-5), behind `tax.returns_v1`. While the
// flag is off the area shows F-05's flag-off state, never a 404. TAX-01 keeps its tile, office
// grouping, search and tax year in the URL (`?tile=`, `?office=`, `?q=`, `?tax_year=`). The
// return's Intake tab is TAX-03 at `/tax-returns/$returnId/intake` (T-02-T19).

const PracticeBoard = lazyScreen(async () => (await import("../../screens/TAX-01")).TAX01);
const ReturnOverview = lazyScreen(async () => (await import("../../screens/TAX-02")).TAX02);
const ReturnIntake = lazyScreen(async () => (await import("../../screens/TAX-03")).TAX03);
const K1Package = lazyScreen(async () => (await import("../../screens/TXP-12")).TXP12);
const ReturnDelivery = lazyScreen(async () => (await import("../../screens/TAX-12")).TAX12);

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
      />,
    );
  },
});

export const taxReturnRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId",
  component: function TaxReturnPage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    return gated(
      <ReturnOverview
        returnId={returnId}
        onTab={(tab) => {
          if (tab === "intake") void navigate(to.TAX03({ returnId }));
        }}
      />,
    );
  },
});

// TAX-03 (T-02-T19): the return's Intake tab, `/tax-returns/$returnId/intake`.
export const taxReturnIntakeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/intake",
  component: function TaxReturnIntakePage(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    return gated(
      <ReturnIntake
        returnId={returnId}
        onTab={(tab) => {
          if (tab === "overview") void navigate(to.TAX02({ returnId }));
        }}
      />,
    );
  },
});

// TXP-12 (T-02-T25): the issuing return's K-1 package, `/tax-returns/$returnId/k1`, behind both
// `tax.returns_v1` and `tax.k1_release` (the firm's K-1 routes answer 404 while it is off). The
// Return chip switches the issuing return (1065, 1120-S, 1041) by its path.
export const taxReturnK1Route = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/k1",
  component: function TaxReturnK1Page(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    return gated(
      <FeatureGate
        flag="tax.k1_release"
        fallback={<FlagOffState flag="tax.k1_release" label="K-1 package" />}
      >
        <K1Package
          returnId={returnId}
          onReturn={(next) => {
            void navigate(to.TXP12({ returnId: next }));
          }}
          onBack={() => {
            void navigate(to.TAX02({ returnId }));
          }}
        />
      </FeatureGate>,
    );
  },
});

// TAX-12 (T-01-T51): the return's Delivery & e-file cockpit, `/tax-returns/$returnId/delivery`,
// behind `tax.returns_v1` and `tax.delivery_efile` (the delivery routes answer 404 while it is off).
export const taxReturnDeliveryRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/delivery",
  component: function TaxReturnDeliveryPage(): JSX.Element {
    const returnId = useParam("returnId");
    return gated(
      <FeatureGate
        flag="tax.delivery_efile"
        fallback={<FlagOffState flag="tax.delivery_efile" label="Delivery & e-file" />}
      >
        <ReturnDelivery returnId={returnId} />
      </FeatureGate>,
    );
  },
});

export const taxReturnRoutes = [
  taxReturnsRoute,
  taxReturnRoute,
  taxReturnIntakeRoute,
  taxReturnK1Route,
  taxReturnDeliveryRoute,
] as const;
