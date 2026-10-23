import { FlagOffState } from "@abacus/ui";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Binders (P-06 §5.1): `/binders` → BND-01, behind `binders.engine` (C5). While the flag is off
// the area shows F-05's flag-off state, never a 404.

const BindersIndex = lazyScreen(async () => (await import("../../screens/BND-01")).BindersIndex);

export const bindersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/binders",
  component: function BindersPage(): JSX.Element {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="binders.engine"
          fallback={<FlagOffState flag="binders.engine" label="Binders" />}
        >
          <BindersIndex />
        </FeatureGate>
      </div>
    );
  },
});

export const binderRoutes = [bindersRoute] as const;
