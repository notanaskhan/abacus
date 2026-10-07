import { Alert, Button, EmptyState } from "@abacus/ui";
import { Link, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import type { JSX } from "react";
import { CALLBACK_PATH } from "./auth/session";
import { Board } from "./screens/Board";
import { Engagements } from "./screens/Engagements";
import { Layout } from "./screens/Layout";
import { Review } from "./screens/Review";
import { SignInCallback } from "./screens/SignInCallback";

// Code-based routes (no file-router plugin): firm users only in this spec (ADR-011).
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
const boardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId",
  component: BoardPage,
});

function BoardPage(): JSX.Element {
  const { engagementId } = boardRoute.useParams();
  return (
    <Board
      engagementId={engagementId}
      reviewLink={
        <Link
          to="/engagements/$engagementId/review"
          params={{ engagementId }}
          className="text-sm underline"
        >
          Review queue
        </Link>
      }
    />
  );
}

const reviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/engagements/$engagementId/review",
  component: ReviewPage,
});

function ReviewPage(): JSX.Element {
  const { engagementId } = reviewRoute.useParams();
  return <Review engagementId={engagementId} />;
}

const routeTree = rootRoute.addChildren([
  callbackRoute,
  appRoute.addChildren([engagementsRoute, boardRoute, reviewRoute]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
