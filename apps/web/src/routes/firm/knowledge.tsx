import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Knowledge: `/knowledge` is KNW-01 (K-01-T04) behind `knowledge.catalog`; with the flag off it is
// the SPEC-009 document search (legacy Knowledge.tsx) it replaces. Each is its own chunk.
const Knowledge = lazyScreen(async () => (await import("../../legacy/Knowledge")).Knowledge);
const Knw01 = lazyScreen(async () => (await import("../../screens/KNW-01")).KNW01);

export const knowledgeRoutes = [
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge",
    component: function KnowledgePage(): JSX.Element {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate flag="knowledge.catalog" fallback={<Knowledge />}>
            <Knw01 />
          </FeatureGate>
        </div>
      );
    },
  }),
] as const;
