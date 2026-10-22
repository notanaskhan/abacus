import { createRoute } from "@tanstack/react-router";
import { appRoute, lazyScreen } from "../root";

// Home: today the engagements index with what's waiting on you (TASK-093, TASK-102).
const Engagements = lazyScreen(async () => (await import("../../legacy/Engagements")).Engagements);

export const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: function HomePage() {
    return <Engagements />;
  },
});

export const homeRoutes = [homeRoute] as const;
