import { entityRunsOptions, returnRecordOptions } from "@abacus/api-client/query";
import { EmptyState, FlagOffState, Spinner } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { createRoute, redirect, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate, useFlag } from "../../app-core/flags";
import {
  type Section,
  SCREEN_OF,
  isEntityForm,
  sectionOf,
  slugOf,
} from "../../domain/tax/entityReturn";
import { TXP00, frameOf } from "../../screens/TXP-00";
import { EntityReturnLayout, NOT_BUILT } from "../../screens/TXP-00/EntityReturnLayout";
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

// T-05-T28 (DEC-4520): `/tax-returns/$returnId` dispatches by form family. With
// `tax.entity_workspace` on, a 1065 opens the entity layout on its Agent tab (TXP-00); a 1040 or
// 1041, or any return with the flag off, keeps TAX-02 as today. The entity sections live at
// `/issues`, `/workpaper`, `/activity` and `/review/$review`; a slug that is not the form's
// redirects to the Agent tab before load.
function EntitySection({
  returnId,
  section,
}: {
  returnId: string;
  section: Section;
}): JSX.Element {
  const navigate = useNavigate();
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const entityOn = useFlag("tax.entity_workspace") === true;
  if (record.data === undefined) {
    return <Spinner label="Loading the return" />;
  }
  const form = record.data.row.form;
  if (!entityOn || !isEntityForm(form)) {
    return (
      <ReturnOverview
        returnId={returnId}
        onTab={(tab) => {
          if (tab === "intake") void navigate(to.TAX03({ returnId }));
        }}
      />
    );
  }
  const screen = SCREEN_OF[section.review ?? section.tab];
  return (
    <EntityReturnLayout
      title={`${String(record.data.row.tax_year)} Form ${form}`}
      context={record.data.row.client_name}
      section={section}
      onSection={(next) => {
        if (next.tab === "intake") {
          void navigate(to.TAX03({ returnId }));
          return;
        }
        void navigate({ to: `/tax-returns/${returnId}${slugOf(next)}` });
      }}
    >
      {section.tab === "agent" ? (
        <AgentTab returnId={returnId} />
      ) : (
        // TXP-10/11/01/02/05/07 land with their rows; until then the planned state, never blank.
        <EmptyState title={NOT_BUILT} icon="clock">
          {screen ?? ""}
        </EmptyState>
      )}
    </EntityReturnLayout>
  );
}

// T-05-T29: TXP-00 on the return's workbook runs (the newest run sets the frame).
function AgentTab({ returnId }: { returnId: string }): JSX.Element {
  const navigate = useNavigate();
  const runs = useQuery(entityRunsOptions({ path: { return_id: returnId } }));
  if (runs.data === undefined) return <Spinner label="Loading the workbook runs" />;
  return (
    <TXP00
      frame={frameOf(runs.data.items)}
      onComposer={() => {
        void navigate({ to: ".", search: { ov: "assistant" } });
      }}
    />
  );
}

export const taxReturnRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId",
  component: function TaxReturnPage(): JSX.Element {
    const returnId = useParam("returnId");
    return gated(<EntitySection returnId={returnId} section={{ tab: "agent" }} />);
  },
});

function entitySectionRoute(slug: "issues" | "workpaper" | "activity") {
  return createRoute({
    getParentRoute: () => appRoute,
    path: `/tax-returns/$returnId/${slug}`,
    component: function EntitySectionPage(): JSX.Element {
      const returnId = useParam("returnId");
      return gated(<EntitySection returnId={returnId} section={{ tab: slug }} />);
    },
  });
}

export const entityIssuesRoute = entitySectionRoute("issues");
export const entityWorkpaperRoute = entitySectionRoute("workpaper");
export const entityActivityRoute = entitySectionRoute("activity");

export const entityReviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/tax-returns/$returnId/review/$review",
  beforeLoad: ({ params }) => {
    if (sectionOf("review", params.review) === null) {
      // biome-ignore lint/style/useThrowOnlyError: TanStack's redirect is thrown by design
      throw redirect({ to: "/tax-returns/$returnId", params: { returnId: params.returnId } });
    }
  },
  component: function EntityReviewPage(): JSX.Element {
    const returnId = useParam("returnId");
    const review = useParam("review");
    const section = sectionOf("review", review) ?? { tab: "agent" };
    return gated(<EntitySection returnId={returnId} section={section} />);
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
  entityIssuesRoute,
  entityWorkpaperRoute,
  entityActivityRoute,
  entityReviewRoute,
  taxReturnIntakeRoute,
  taxReturnK1Route,
  taxReturnDeliveryRoute,
] as const;
