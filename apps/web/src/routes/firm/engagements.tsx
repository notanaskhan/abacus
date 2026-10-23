import { createRoute, useNavigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// An engagement (SPEC-016): one header over its tabs; each tab's screen is its own chunk. Behind
// `engagements.v2` the record is ENG-02 (P-07-T20) with its own in-screen tabs; the legacy layout
// and its tab routes answer while the flag is off.
const EngagementRecord = lazyScreen(
  async () => (await import("../../screens/ENG-02")).EngagementRecordPage,
);
const EngagementLayout = lazyScreen(
  async () => (await import("../../legacy/EngagementLayout")).EngagementLayout,
);
const screens = {
  Overview: lazyScreen(async () => (await import("../../legacy/Overview")).Overview),
  DefaultToSetup: lazyScreen(async () => (await import("../../legacy/Setup")).DefaultToSetup),
  Setup: lazyScreen(async () => (await import("../../legacy/Setup")).Setup),
  AgentRuns: lazyScreen(async () => (await import("../../legacy/AgentRuns")).AgentRuns),
  AgentActivity: lazyScreen(
    async () => (await import("../../legacy/AgentActivity")).AgentActivity,
  ),
  ItemDetail: lazyScreen(async () => (await import("../../legacy/ItemDetail")).ItemDetail),
  Board: lazyScreen(async () => (await import("../../legacy/Board")).Board),
  ImportRequestList: lazyScreen(
    async () => (await import("../../legacy/ImportRequestList")).ImportRequestList,
  ),
  MapView: lazyScreen(async () => (await import("../../legacy/MapView")).MapView),
  People: lazyScreen(async () => (await import("../../legacy/People")).People),
  Planning: lazyScreen(async () => (await import("../../legacy/Planning")).Planning),
  Findings: lazyScreen(async () => (await import("../../legacy/Findings")).Findings),
  Fieldwork: lazyScreen(async () => (await import("../../legacy/Fieldwork")).Fieldwork),
  Review: lazyScreen(async () => (await import("../../legacy/Review")).Review),
  Workpapers: lazyScreen(async () => (await import("../../legacy/Workpapers")).Workpapers),
  Workpaper: lazyScreen(async () => (await import("../../legacy/Workpaper")).Workpaper),
  CompletionRelease: lazyScreen(
    async () => (await import("../../legacy/CompletionRelease")).CompletionRelease,
  ),
  EngagementDashboard: lazyScreen(
    async () => (await import("../../legacy/EngagementDashboard")).EngagementDashboard,
  ),
  ReviewMatrix: lazyScreen(async () => (await import("../../legacy/ReviewMatrix")).ReviewMatrix),
  TrialBalance: lazyScreen(async () => (await import("../../legacy/TrialBalance")).TrialBalance),
};

// ENG-03 (P-07-T21): `/engagements/new` behind `engagements.v2`, resuming `?draft=` or starting
// a draft (prefilled with `?client=`); Create opens the new engagement's record.
const NewEngagement = lazyScreen(
  async () => (await import("../../screens/ENG-03")).NewEngagementPage,
);

interface NewEngagementSearch {
  draft?: string;
  client?: string;
}

export const newEngagementRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/new",
  validateSearch: (search: Record<string, unknown>): NewEngagementSearch => ({
    ...(typeof search.draft === "string" ? { draft: search.draft } : {}),
    ...(typeof search.client === "string" ? { client: search.client } : {}),
  }),
  component: function NewEngagementRoutePage(): JSX.Element {
    const search = newEngagementRoute.useSearch();
    const navigate = useNavigate();
    return (
      <FeatureGate flag="engagements.v2">
        <NewEngagement
          draftId={search.draft}
          clientId={search.client}
          onClose={() => {
            void navigate({ to: "/engagements" });
          }}
          onCreated={(engagementId) => {
            void navigate({ to: "/engagements/$engagementId", params: { engagementId } });
          }}
        />
      </FeatureGate>
    );
  },
});

export const engagementRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId",
  component: function EngagementPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    const navigate = useNavigate();
    return (
      <FeatureGate
        flag="engagements.v2"
        fallback={<EngagementLayout engagementId={engagementId} />}
      >
        <div className="flex min-h-0 flex-1 flex-col">
          <EngagementRecord
            engagementId={engagementId}
            onNavigate={(target) => {
              if (target.screen === "ENG-01") void navigate({ to: "/engagements" });
              else {
                void navigate({ to: "/clients/$clientId", params: { clientId: target.clientId } });
              }
            }}
          />
        </div>
      </FeatureGate>
    );
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
    return (
      <div className="flex flex-col gap-4">
        <screens.AgentRuns engagementId={engagementId} />
        <screens.AgentActivity engagementId={engagementId} />
      </div>
    );
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

// SPEC-313 (TASK-331): the sign-off matrix, the review gate and every review note.
const signOffsRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/sign-offs",
  component: function SignOffsPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.ReviewMatrix engagementId={engagementId} />;
  },
});

// SPEC-314 (TASK-332): EQR, going concern, report, representation letter, release, archive.
const completionRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/completion",
  component: function CompletionPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.CompletionRelease engagementId={engagementId} />;
  },
});

// SPEC-317 (TASK-460): the engagement at a glance.
const dashboardRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/dashboard",
  component: function DashboardPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.EngagementDashboard engagementId={engagementId} />;
  },
});

export const engagementRoutes = [
  newEngagementRoute,
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
    completionRoute,
    dashboardRoute,
  ]),
] as const;
