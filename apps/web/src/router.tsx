import { meOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, EmptyState } from "@abacus/ui";
import { Link, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import type { JSX } from "react";
import { CALLBACK_PATH } from "./auth/session";
import { AdminLayout } from "./screens/AdminLayout";
import { Autonomy, FirmAgents, LetterPolicy } from "./screens/Autonomy";
import { AgentActivity } from "./screens/AgentActivity";
import { Onboarding } from "./screens/Onboarding";
import { Board } from "./screens/Board";
import { Budget } from "./screens/Budget";
import { Knowledge } from "./screens/Knowledge";
import { KnowledgeDocuments } from "./screens/KnowledgeDocuments";
import { SupportAccess } from "./screens/SupportAccess";
import { Walls } from "./screens/Walls";
import { Engagements } from "./screens/Engagements";
import { ImportRequestList } from "./screens/ImportRequestList";
import { FirmPeople } from "./screens/FirmPeople";
import { ItemDetail } from "./screens/ItemDetail";
import { Join } from "./screens/Join";
import { Layout } from "./screens/Layout";
import { Methodology } from "./screens/Methodology";
import { MethodologyVersion } from "./screens/MethodologyVersion";
import { Accept } from "./screens/ClientAccept";
import { ClientEngagement } from "./screens/ClientEngagement";
import { ConnectCallback } from "./screens/ConnectCallback";
import { ClientHome } from "./screens/ClientHome";
import { People } from "./screens/People";
import { EngagementLayout } from "./screens/EngagementLayout";
import { MapView } from "./screens/MapView";
import { Overview } from "./screens/Overview";
import { DefaultToSetup, Setup } from "./screens/Setup";
import { Review } from "./screens/Review";
import { SignInCallback } from "./screens/SignInCallback";
import { Signup } from "./screens/Signup";

// Code-based routes (no file-router plugin): the firm workspace and the client portal (ADR-011).
const rootRoute = createRootRoute({
  notFoundComponent: NotFound,
  errorComponent: RouteError,
});

function NotFound(): JSX.Element {
  return (
    <main className="mx-auto max-w-md p-8">
      <EmptyState
        title="Page not found"
        action={
          <Link to="/" className="text-sm underline">
            Go to engagements
          </Link>
        }
      />
    </main>
  );
}

function RouteError(): JSX.Element {
  return (
    <main className="mx-auto max-w-md p-8">
      <Alert
        title="Something went wrong"
        action={
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              window.location.reload();
            }}
          >
            Reload
          </Button>
        }
      >
        The page couldn&apos;t be shown.
      </Alert>
    </main>
  );
}
const callbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CALLBACK_PATH,
  component: SignInCallback,
});
const appRoute = createRoute({ getParentRoute: () => rootRoute, id: "app", component: Layout });
const engagementsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: Engagements,
});

// An engagement (SPEC-016): Overview · Requests · Map · Contacts · Review under one header.
const engagementRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId",
  component: function EngagementPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <EngagementLayout engagementId={engagementId} />;
  },
});
const overviewRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/",
  component: function OverviewPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return (
      <DefaultToSetup engagementId={engagementId}>
        <Overview engagementId={engagementId} />
      </DefaultToSetup>
    );
  },
});
const engagementActivityRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/activity",
  component: function ActivityPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <AgentActivity engagementId={engagementId} />;
  },
});
const engagementSetupRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/setup",
  component: function SetupPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <Setup engagementId={engagementId} />;
  },
});
const itemRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/items/$itemId",
  component: function ItemPage(): JSX.Element {
    const { engagementId, itemId } = itemRoute.useParams();
    return <ItemDetail engagementId={engagementId} itemId={itemId} />;
  },
});
const boardRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/requests",
  component: function BoardPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return (
      <div className="flex flex-col gap-3">
        <div className="flex justify-end">
          <ImportRequestList engagementId={engagementId} />
        </div>
        <Board
          engagementId={engagementId}
          reviewLink={
            <Link
              to="/engagements/$engagementId/review"
              params={{ engagementId }}
              className="text-sm text-accent hover:underline"
            >
              Review queue
            </Link>
          }
        />
      </div>
    );
  },
});
const mapRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/map",
  component: function MapPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <MapView engagementId={engagementId} />;
  },
});
const peopleRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/people",
  component: function PeoplePage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <People engagementId={engagementId} />;
  },
});
const reviewRoute = createRoute({
  getParentRoute: () => engagementRoute,
  path: "/review",
  component: function ReviewPage(): JSX.Element {
    const { engagementId } = engagementRoute.useParams();
    return <Review engagementId={engagementId} />;
  },
});

// Firm admin (SPEC-016, SPEC-019 Q1): one section with tabs; Knowledge is on the rail for all staff.
const knowledgeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/knowledge",
  component: Knowledge,
});
const adminRoute = createRoute({
  getParentRoute: () => appRoute,
  id: "admin",
  component: AdminLayout,
});
const methodologyRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/methodology",
  component: Methodology,
});
const methodologyVersionRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/methodology/$versionId",
  component: function VersionPage(): JSX.Element {
    const { versionId } = methodologyVersionRoute.useParams();
    return <MethodologyVersion versionId={versionId} />;
  },
});
const knowledgeDocumentsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/knowledge",
  component: KnowledgeDocuments,
});
const budgetRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/budget",
  component: Budget,
});
const autonomyRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/autonomy",
  component: function AutonomyPage(): JSX.Element {
    const me = useQuery(meOptions());
    const tenant = me.data?.active_tenant_id ?? null;
    const role = me.data?.memberships.find((m) => m.tenant_id === tenant)?.firm_role;
    return (
      <div className="flex flex-col gap-4">
        <Autonomy canSet={role === "firm_admin"} />
        <LetterPolicy canSet={role === "firm_admin"} />
        <FirmAgents canSet={role === "firm_admin"} />
      </div>
    );
  },
});
const setupRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/setup",
  component: function SetupPage(): JSX.Element {
    return <Onboarding always />;
  },
});
const peopleAdminRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/people",
  component: FirmPeople,
});
const supportRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/support",
  component: SupportAccess,
});
const wallsRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/walls",
  component: Walls,
});

// The client portal: a separate tree (ADR-011; SPEC-015, SPEC-016).
const clientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client",
  component: ClientHome,
});
const clientEngagementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/engagements/$engagementId",
  component: function ClientEngagementPage(): JSX.Element {
    const { engagementId } = clientEngagementRoute.useParams();
    return <ClientEngagement engagementId={engagementId} />;
  },
});
const joinRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/join",
  component: Join,
});
const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signup",
  component: Signup,
});
const connectCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/connect/callback",
  component: ConnectCallback,
});
const acceptRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/accept",
  component: Accept,
});

const routeTree = rootRoute.addChildren([
  callbackRoute,
  clientRoute,
  clientEngagementRoute,
  connectCallbackRoute,
  signupRoute,
  joinRoute,
  acceptRoute,
  appRoute.addChildren([
    engagementsRoute,
    engagementRoute.addChildren([
      overviewRoute,
      boardRoute,
      itemRoute,
      mapRoute,
      engagementSetupRoute,
      engagementActivityRoute,
      peopleRoute,
      reviewRoute,
    ]),
    knowledgeRoute,
    adminRoute.addChildren([
      methodologyRoute,
      methodologyVersionRoute,
      knowledgeDocumentsRoute,
      budgetRoute,
      autonomyRoute,
      setupRoute,
      peopleAdminRoute,
      supportRoute,
      wallsRoute,
    ]),
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
