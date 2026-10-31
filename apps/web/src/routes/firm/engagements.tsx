import { workItemsOptions } from "@abacus/api-client/query";
import { FlagOffState } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { type JSX, useEffect } from "react";
import { FeatureGate, useFlag } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// An engagement: the record is ENG-02 (P-07-T20) with its own in-screen tabs, for every firm since
// P-07-T59 retired `engagements.v2` (DEC-905). P-07-T58 retired the legacy layout (DEC-904); the
// tab routes below rendered inside that layout's outlet; ENG-02 has none, so
// they wait for their owners' retirement and render nowhere.
const EngagementRecord = lazyScreen(
  async () => (await import("../../screens/ENG-02")).EngagementRecordPage,
);
const screens = {
  Overview: lazyScreen(async () => (await import("../../legacy/Overview")).Overview),
  AgentRuns: lazyScreen(async () => (await import("../../legacy/AgentRuns")).AgentRuns),
  AgentActivity: lazyScreen(
    async () => (await import("../../legacy/AgentActivity")).AgentActivity,
  ),
  MapView: lazyScreen(async () => (await import("../../legacy/MapView")).MapView),
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

// ENG-03 (P-07-T21): `/engagements/new`, resuming `?draft=` or starting
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
      <NewEngagement
        draftId={search.draft}
        clientId={search.client}
        onClose={() => {
          void navigate({ to: "/engagements" });
        }}
        onCreated={(engagementId) => {
          void navigate({ to: "/engagements/$engagementId", params: { engagementId } });
        }}
        onOpen={(engagementId) => {
          void navigate({ to: "/engagements/$engagementId", params: { engagementId } });
        }}
      />
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
    );
  },
});

const overviewRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/",
  component: function OverviewPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    return <screens.Overview engagementId={engagementId} />;
  },
});
/** The engagement's assurance work item: `undefined` while loading, `null` when it has none. */
function useEngagementAudit(engagementId: string, enabled: boolean): string | null | undefined {
  const items = useQuery({
    ...workItemsOptions({ path: { engagement_id: engagementId } }),
    enabled,
    retry: false,
  });
  if (!enabled || items.isError) return null;
  if (items.data === undefined) return undefined;
  return items.data.find((w) => w.kind === "assurance")?.id ?? null;
}

// A-01-T16 and A-01-T21 (chapter 04 §2.2): an engagement's requests and one request are AUD-03 on
// its assurance work item. The legacy Board and ItemDetail screens are retired (A-01-T21,
// DEC-442), so these two paths only redirect: with `audits.cockpit` off they show F-05's
// flag-off state, and an engagement with no assurance work item goes to its record.
function LegacyEvidenceRedirect({ itemId }: { itemId?: string }): JSX.Element {
  const engagementId = useParam("engagementId");
  const navigate = useNavigate();
  const cockpit = useFlag("audits.cockpit") === true;
  const auditId = useEngagementAudit(engagementId, cockpit);
  useEffect(() => {
    if (typeof auditId === "string") {
      void navigate({
        to: "/audits/$auditId/source-documents",
        params: { auditId },
        search: itemId === undefined ? {} : { item: itemId },
        replace: true,
      });
    } else if (cockpit && auditId === null) {
      void navigate({ to: "/engagements/$engagementId", params: { engagementId }, replace: true });
    }
  }, [auditId, cockpit, engagementId, itemId, navigate]);
  if (!cockpit) return <FlagOffState flag="audits.cockpit" label="Audits" />;
  return <></>;
}

export const boardRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/requests",
  component: function BoardPage(): JSX.Element {
    return <LegacyEvidenceRedirect />;
  },
});

export const itemRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/items/$itemId",
  component: function ItemPage(): JSX.Element {
    const itemId = useParam("itemId");
    return <LegacyEvidenceRedirect itemId={itemId} />;
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

// ENG-13 (P-07-T60, P-07-T62): the roll-forward wizard, an O6 over the engagement, behind
// `engagements.roll_forward_v2`. `?draft=` resumes a draft; without one the page starts one and
// puts it in the URL. Closing returns to the source's record; Create opens the new engagement.
const RollForward = lazyScreen(async () => (await import("../../screens/ENG-13")).RollForwardPage);

// N-02-T34: ENG-04 is ENG-02's Letter & terms tab (`engagements.letter_composer`; off, the record
// panel), opened at its own path.
const letterRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId/letter",
  component: function LetterPage(): JSX.Element {
    const engagementId = useParam("engagementId");
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <EngagementRecord
          engagementId={engagementId}
          initialTab="letter"
          onNavigate={(target) => {
            if (target.screen === "ENG-01") void navigate({ to: "/engagements" });
            else {
              void navigate({ to: "/clients/$clientId", params: { clientId: target.clientId } });
            }
          }}
        />
      </div>
    );
  },
});

const rollForwardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId/roll-forward",
  validateSearch: (search: Record<string, unknown>): { draft?: string } =>
    typeof search.draft === "string" ? { draft: search.draft } : {},
  component: function RollForwardRoutePage(): JSX.Element {
    const engagementId = useParam("engagementId");
    const search: { draft?: string } = useSearch({ strict: false });
    const navigate = useNavigate();
    const record = (id: string): void => {
      void navigate({ to: "/engagements/$engagementId", params: { engagementId: id } });
    };
    return (
      <FeatureGate flag="engagements.roll_forward_v2">
        <RollForward
          engagementId={engagementId}
          {...(search.draft === undefined ? {} : { draftId: search.draft })}
          onDraft={(draft) => {
            void navigate({
              to: "/engagements/$engagementId/roll-forward",
              params: { engagementId },
              search: { draft },
              replace: true,
            });
          }}
          onClose={() => {
            record(engagementId);
          }}
          onCreated={record}
        />
      </FeatureGate>
    );
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
  rollForwardRoute,
  letterRoute,
  engagementRoute.addChildren([
    overviewRoute,
    boardRoute,
    itemRoute,
    mapRoute,
    activityRoute,
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
