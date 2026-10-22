import { Alert, Button, ClockProvider, EmptyState } from "@abacus/ui";
import { Link, Outlet, createRootRoute, createRoute } from "@tanstack/react-router";
import { type ComponentType, type JSX, Suspense, lazy } from "react";
import { nowMs } from "../app-core/clock";
import { OverlayHost } from "../app-core/overlay-host";
import { CALLBACK_PATH } from "../auth/session";
import { Layout } from "../legacy/Layout";
import { SignInCallback } from "../legacy/SignInCallback";

// Code-based routes (no file-router plugin): the firm workspace and the client portal (ADR-011).
// F-03-T17: the tree is split by area (routes/firm, routes/portal); each screen is its own chunk.
export const rootRoute = createRootRoute({
  component: RootShell,
  notFoundComponent: NotFound,
  errorComponent: RouteError,
});

/** F-05-T10: the design system's ClockProvider reads business time from the browser clock
 * (app-core/clock.tsx), so screens read time only through useNow, useToday and useFormat.
 * F-05-T20: OverlayHost draws the `?ov=` layers from the overlay registry (app-core/overlays.ts). */
function RootShell(): JSX.Element {
  return (
    <ClockProvider now={nowMs}>
      <Outlet />
      <OverlayHost />
    </ClockProvider>
  );
}

function NotFound(): JSX.Element {
  return (
    <main className="mx-auto max-w-md p-8">
      <EmptyState
        title="Page not found"
        action={
          <Link to="/" className="text-body underline">
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
            variant="secondary"
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

export const callbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: CALLBACK_PATH,
  component: SignInCallback,
});

/** The signed-in firm workspace: every firm area mounts under it. */
export const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  component: Layout,
});

/** A screen loaded on first use, in its own chunk (F-03-T17). */
export function lazyScreen<P extends object>(
  load: () => Promise<ComponentType<P>>,
): (props: P) => JSX.Element {
  const Screen = lazy(async () => ({ default: await load() }));
  return function LazyScreen(props: P): JSX.Element {
    return (
      <Suspense fallback={null}>
        <Screen {...props} />
      </Suspense>
    );
  };
}
