import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useRouter,
} from "@tanstack/react-router";
import { type JSX, Suspense, lazy, useEffect, useState } from "react";
import { LANDING_PATH, portalAccessToken } from "../../app-core/portal-session";

// The client portal's route tree (P-08-T07; P-08 §5.1; DEC-59): its own entry (portal.html), its
// own origin root, no `/client` prefix. Sign-in and invitation acceptance are public; home,
// documents and the role landings need a session. Nothing here reaches the firm's tree, shell or
// screens (INV-4, eslint L7). This file holds no design-system import: the providers
// (portal/PortalRoot.tsx, with the branding loader for the tab's title and icon) and every screen
// are their own chunks, so the first load stays inside the portal's budget.

const PortalRoot = lazy(async () => ({
  default: (await import("../../portal/PortalRoot")).PortalRoot,
}));
const NotBuiltScreen = lazy(async () => ({
  default: (await import("../../portal/PortalRoot")).NotBuilt,
}));
const SignIn = lazy(async () => ({
  default: (await import("../../screens/POR-01")).PortalSignIn,
}));
const Shell = lazy(async () => ({
  default: (await import("../../portal/PortalShell")).PortalShell,
}));

function Root(): JSX.Element {
  return (
    <Suspense fallback={null}>
      <PortalRoot>
        <Outlet />
      </PortalRoot>
    </Suspense>
  );
}

function NotBuilt(): JSX.Element {
  return <NotBuiltScreen />;
}

const rootRoute = createRootRoute({ component: Root, notFoundComponent: NotBuilt });

/** `#link=<token>` from a reminder email: into the page's memory, out of the address bar. */
export function takeLinkFromFragment(location: Location = window.location): string | undefined {
  const match = /(?:^#|&)link=([\w-]{20,200})/.exec(location.hash);
  if (match?.[1] === undefined) return undefined;
  window.history.replaceState(null, "", location.pathname + location.search);
  return match[1];
}

// The portal's paths are not the firm router's registered ones, so it moves through the router's
// history by path rather than the typed `navigate`.
function SignInPage(): JSX.Element {
  const { history } = useRouter();
  const [link] = useState(() => takeLinkFromFragment());
  return (
    <SignIn
      {...(link === undefined ? {} : { opening: { email: "", linkToken: link } })}
      onSignedIn={(landing) => {
        history.push(LANDING_PATH[landing]);
      }}
    />
  );
}

/** A signed-in area: without a session the page goes to sign-in with its own path to return to. */
function Area({ area }: { area: string }): JSX.Element | null {
  const { history } = useRouter();
  const signedIn = portalAccessToken() !== null || import.meta.env.VITE_FIXTURES === "1";
  useEffect(() => {
    if (!signedIn) history.push(`/sign-in?return=${encodeURIComponent(window.location.pathname)}`);
  }, [signedIn, history]);
  return signedIn ? <Shell area={area} /> : null;
}

const page = (path: string, component: () => JSX.Element | null) =>
  createRoute({ getParentRoute: () => rootRoute, path, component });

export const portalTree = rootRoute.addChildren([
  page("/sign-in", SignInPage),
  // POR-01 d (invitation acceptance) is P-08-T19's.
  page("/accept", NotBuilt),
  page("/", () => <Area area="Home" />),
  page("/documents", () => <Area area="Documents" />),
  page("/requests", NotBuilt),
  page("/k1s", NotBuilt),
  page("/governance", NotBuilt),
  page("/intake", NotBuilt),
  page("/component-room", NotBuilt),
]);

export function createPortalRouter() {
  return createRouter({ routeTree: portalTree });
}
