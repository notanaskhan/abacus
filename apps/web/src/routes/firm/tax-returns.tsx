import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { to } from "../to";
import { appRoute, lazyScreen } from "../root";

// Tax Returns (T-02 §5.1): `/tax-returns` is TAX-01 (T-02-T12) and `/tax-returns/$returnId` the
// `ReturnFrame` on TAX-02 (T-02-T14; every form family, DV-5), behind the `tax_returns` entitlement. While the
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
        entitlement="tax_returns"
        fallback={<FlagOffState flag="tax_returns" label="Tax Returns" />}
      >
        {children}
      </FeatureGate>
    </div>
  );
}

const TAX01_SEARCH = ["tile", "office", "q", "tax_year"] as const;
type TaxReturnsSearch = Partial<Record<(typeof TAX01_SEARCH)[number], string>>;

// T-03-T11: TAX-13 `/tax-returns/extensions`.
const Extensions = lazyScreen(async () => (await import("../../screens/TAX-13")).Extensions);
export const taxExtensionsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/extensions",
  validateSearch: (search: Record<string, unknown>): { ov?: string } =>
    typeof search.ov === "string" && search.ov !== "" ? { ov: search.ov } : {},
  component: function TaxExtensionsPage(): JSX.Element {
    const navigate = useNavigate();
    const search: { ov?: string } = useSearch({ strict: false });
    return gated(
      <Extensions
        taxYear={2025}
        {...search}
        onOverlay={(ov) => {
          void navigate({ to: ".", search: ov === null ? {} : { ov } });
        }}
      />,
    );
  },
});

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

// T-05-T28 (DEC-4520): `/tax-returns/$returnId` dispatches by form family (TXP-00's
// EntityReturn); TAX-02 stays the overview for a 1040 or 1041, or with `tax.entity_workspace` off.
const EntityReturn = lazyScreen(
  async () => (await import("../../screens/TXP-00/EntityReturn")).EntityReturn,
);

export type EntitySlug = "agent" | "issues" | "workpaper" | "activity" | "review";

export function EntitySection({
  returnId,
  slug,
  review,
  fallback,
}: {
  returnId: string;
  slug: EntitySlug;
  review?: string;
  /** The route's own screen for a 1040 or 1041 (default: TAX-02). */
  fallback?: JSX.Element;
}): JSX.Element {
  const navigate = useNavigate();
  const overview = fallback ?? (
    <ReturnOverview
      returnId={returnId}
      onTab={(tab) => {
        if (tab === "intake") void navigate(to.TAX03({ returnId }));
      }}
    />
  );
  return gated(
    <EntityReturn
      returnId={returnId}
      slug={slug}
      overview={overview}
      onOpen={(suffix) => {
        void navigate({ to: `/tax-returns/${returnId}${suffix}` });
      }}
      onComposer={() => {
        void navigate({ to: ".", search: { ov: "assistant" } });
      }}
      {...(review === undefined ? {} : { review })}
    />,
  );
}

export const taxReturnRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId",
  component: function TaxReturnPage(): JSX.Element {
    const returnId = useParam("returnId");
    return <EntitySection returnId={returnId} slug="agent" />;
  },
});

// `/workpaper` is the entity return's alone (TXP-11); `/issues`, `/activity` and
// `/review/$section` are T-04's routes (tax-review.tsx), which dispatch through `EntitySection`.
export const entityWorkpaperRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/workpaper",
  component: function EntityWorkpaperPage(): JSX.Element {
    const returnId = useParam("returnId");
    return <EntitySection returnId={returnId} slug="workpaper" />;
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
// the `tax_returns` entitlement and the `tax_returns` entitlement (the firm's K-1 routes answer 404 while it is off). The
// Return chip switches the issuing return (1065, 1120-S, 1041) by its path.
export const taxReturnK1Route = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/k1",
  component: function TaxReturnK1Page(): JSX.Element {
    const returnId = useParam("returnId");
    const navigate = useNavigate();
    return gated(
      <FeatureGate
        entitlement="tax_returns"
        fallback={<FlagOffState flag="tax_returns" label="K-1 package" />}
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
// behind the `tax_returns` entitlement and `tax.delivery_efile` (the delivery routes answer 404 while it is off).
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
  taxExtensionsRoute,
  taxReturnsRoute,
  taxReturnRoute,
  entityWorkpaperRoute,
  taxReturnIntakeRoute,
  taxReturnK1Route,
  taxReturnDeliveryRoute,
] as const;
