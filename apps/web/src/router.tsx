import { Alert, Button, EmptyState } from "@abacus/ui";
import { Link, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import type { JSX } from "react";
import { CALLBACK_PATH } from "./auth/session";
import { Board } from "./screens/Board";
import { Engagements } from "./screens/Engagements";
import { ImportRequestList } from "./screens/ImportRequestList";
import { Layout } from "./screens/Layout";
import { Methodology } from "./screens/Methodology";
import { MethodologyVersion } from "./screens/MethodologyVersion";
import { Accept } from "./screens/ClientAccept";
import { ClientHome } from "./screens/ClientHome";
import { People } from "./screens/People";
import { EngagementLayout } from "./screens/EngagementLayout";
import { MapView } from "./screens/MapView";
import { Overview } from "./screens/Overview";
import { Review } from "./screens/Review";
import { SignInCallback } from "./screens/SignInCallback";

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
    return <Overview engagementId={engagementId} />;
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

// Firm admin (SPEC-016): methodology now; budget, knowledge, support and walls later.
const methodologyRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/admin/methodology",
  component: Methodology,
});
const methodologyVersionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/admin/methodology/$versionId",
  component: function VersionPage(): JSX.Element {
    const { versionId } = methodologyVersionRoute.useParams();
    return <MethodologyVersion versionId={versionId} />;
  },
});

// The client portal: a separate tree (ADR-011; SPEC-015, SPEC-016).
const clientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client",
  component: ClientHome,
});
const acceptRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/client/accept",
  component: Accept,
});

const routeTree = rootRoute.addChildren([
  callbackRoute,
  clientRoute,
  acceptRoute,
  appRoute.addChildren([
    engagementsRoute,
    engagementRoute.addChildren([overviewRoute, boardRoute, mapRoute, peopleRoute, reviewRoute]),
    methodologyRoute,
    methodologyVersionRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
