import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { AREAS, type Area } from "../../app-core/nav-areas";
import { appRoute, lazyScreen } from "../root";

// The bar's landings (P-01-T02; SHL-01 AC 1.1.5). Engagements opens ENG-01. An area whose landing screen has no route yet (Tax Returns before T-02,
// and so on) still has its path, and shows F-05-T19's flag-off state there: never a 404, a blank
// page or a hidden item. When the landing screen is routed its route replaces this one.

// ENG-01 (P-07-T27), for every firm since P-07-T59 retired `engagements.v2` (DEC-905).
const EngagementsIndex = lazyScreen(
  async () => (await import("../../screens/ENG-01")).EngagementsIndex,
);

export const engagementsIndexRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements",
  component: function EngagementsIndexPage(): JSX.Element {
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <EngagementsIndex
          onOpen={(engagementId) => {
            void navigate({ to: "/engagements/$engagementId", params: { engagementId } });
          }}
        />
      </div>
    );
  },
});

/** The flag key an area's landing is gated on: `ff.tax_returns`. */
export function areaFlag(area: Area): string {
  return `ff.${area.label.toLowerCase().replaceAll(" ", "_")}`;
}

/** The area's landing while its screen is planned. */
export function AreaLanding({ area }: { area: Area }): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FlagOffState flag={areaFlag(area)} label={area.label} />
    </div>
  );
}

const planned = AREAS.filter((a) => !a.routed);

export const areaLandingRoutes = planned.map((area) =>
  createRoute({
    getParentRoute: () => appRoute,
    path: area.path,
    component: function PlannedAreaPage(): JSX.Element {
      return <AreaLanding area={area} />;
    },
  }),
);

export const areaRoutes = [engagementsIndexRoute, ...areaLandingRoutes] as const;
