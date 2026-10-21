import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// An engagement (SPEC-016): one header over its tabs; each tab's screen is its own chunk.
const EngagementLayout = lazyScreen(
  async () => (await import("../../screens/EngagementLayout")).EngagementLayout,
);
const screens = {
  Overview: lazyScreen(async () => (await import("../../screens/Overview")).Overview),
  DefaultToSetup: lazyScreen(async () => (await import("../../screens/Setup")).DefaultToSetup),
  Setup: lazyScreen(async () => (await import("../../screens/Setup")).Setup),
  AgentActivity: lazyScreen(
    async () => (await import("../../screens/AgentActivity")).AgentActivity,
  ),
  ItemDetail: lazyScreen(async () => (await import("../../screens/ItemDetail")).ItemDetail),
  Board: lazyScreen(async () => (await import("../../screens/Board")).Board),
  ImportRequestList: lazyScreen(
    async () => (await import("../../screens/ImportRequestList")).ImportRequestList,
  ),
  MapView: lazyScreen(async () => (await import("../../screens/MapView")).MapView),
  People: lazyScreen(async () => (await import("../../screens/People")).People),
  Planning: lazyScreen(async () => (await import("../../screens/Planning")).Planning),
  Findings: lazyScreen(async () => (await import("../../screens/Findings")).Findings),
  Fieldwork: lazyScreen(async () => (await import("../../screens/Fieldwork")).Fieldwork),
  Review: lazyScreen(async () => (await import("../../screens/Review")).Review),
  Workpapers: lazyScreen(async () => (await import("../../screens/Workpapers")).Workpapers),
  Workpaper: lazyScreen(async () => (await import("../../screens/Workpaper")).Workpaper),
  ReviewMatrix: lazyScreen(async () => (await import("../../screens/ReviewMatrix")).ReviewMatrix),
  TrialBalance: lazyScreen(async () => (await import("../../screens/TrialBalance")).TrialBalance),
};

export const engagementRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId",
  component: function EngagementPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <EngagementLayout engagementId={engagementId} />;
  },
});

const overviewRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/",
  component: function OverviewPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return (
      <screens.DefaultToSetup engagementId={engagementId}>
        <screens.Overview engagementId={engagementId} />
      </screens.DefaultToSetup>
    );
  },
});
const itemRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/items/$itemId",
  component: function ItemPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    const itemId = useParam("itemId");
    return <screens.ItemDetail engagementId={engagementId} itemId={itemId} />;
  },
});
const boardRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/requests",
  component: function BoardPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return (
      <screens.Board
        engagementId={engagementId}
        actions={<screens.ImportRequestList engagementId={engagementId} />}
      />
    );
  },
});

const mapRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/map",
  component: function MapPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.MapView engagementId={engagementId} />;
  },
});

const setupRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/setup",
  component: function SetupPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Setup engagementId={engagementId} />;
  },
});

const activityRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/activity",
  component: function ActivityPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.AgentActivity engagementId={engagementId} />;
  },
});

const peopleRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/people",
  component: function PeoplePage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.People engagementId={engagementId} />;
  },
});

const reviewRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/review",
  component: function ReviewPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Review engagementId={engagementId} />;
  },
});

const fieldworkRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/fieldwork",
  component: function FieldworkPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Fieldwork engagementId={engagementId} />;
  },
});

const findingsRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/findings",
  component: function FindingsPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Findings engagementId={engagementId} />;
  },
});

const planningRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/planning",
  component: function PlanningPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Planning engagementId={engagementId} />;
  },
});

// SPEC-308 (TASK-319): working papers and one paper's grid.
const workpapersRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/workpapers",
  component: function WorkpapersPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Workpapers engagementId={engagementId} />;
  },
});

const workpaperRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/workpapers/$workpaperId",
  component: function WorkpaperPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    const workpaperId = useParam("workpaperId");
    return <screens.Workpaper engagementId={engagementId} workpaperId={workpaperId} />;
  },
});

// SPEC-309 (TASK-320): the trial balance of record and its leadsheets.
const trialBalanceRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/trial-balance",
  component: function TrialBalancePage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.TrialBalance engagementId={engagementId} />;
  },
});

// SPEC-313 (TASK-325): the sign-off matrix, the review gate and every review note.
const signOffsRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/sign-offs",
  component: function SignOffsPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.ReviewMatrix engagementId={engagementId} />;
  },
});

export const engagementRoutes = [
  engagementRoute.addChildren([
    overviewRoute,
    boardRoute,
    itemRoute,
    mapRoute,
    setupRoute,
    activityRoute,
    peopleRoute,
    reviewRoute,
    fieldworkRoute,
    findingsRoute,
    planningRoute,
    workpapersRoute,
    workpaperRoute,
    trialBalanceRoute,
    signOffsRoute,
  ]),
] as const;
