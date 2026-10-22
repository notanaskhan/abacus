import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { appRoute, lazyScreen } from "../root";

// Knowledge (SPEC-009): on the bar for all staff.
const Knowledge = lazyScreen(async () => (await import("../../legacy/Knowledge")).Knowledge);

export const knowledgeRoutes = [
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge",
    component: function KnowledgePage(): JSX.Element {
      return <Knowledge />;
    },
  }),
] as const;
