import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useRouter,
} from "@tanstack/react-router";
import { type JSX, Suspense, lazy, useEffect, useState } from "react";
import {
  ensurePortalSession,
  goToSignIn,
  portalAccessToken,
  returnFrom,
  setSignInNavigator,
} from "../../app-core/auth/bff";
import { LANDING_PATH } from "../../app-core/portal-session";

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
// POR-02 (P-08-T15) and POR-03 (R-01-T10): Home and Documents are their own chunks; the other
// areas keep the shell's planned state.
const Home = lazy(async () => ({
  default: (await import("../../screens/POR-02")).POR02,
}));
const Documents = lazy(async () => ({
  default: (await import("../../screens/POR-03")).POR03,
}));

/** The portal's built areas by nav label; the others stay the shell's planned page. */
export const AREA_PATHS: Readonly<Record<string, string>> = { Home: "/", Documents: "/documents" };

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

/** `#token=<token>` from an invitation email (POR-01 d): into the page's memory, out of the
 * address bar; never web storage or a query string (DEC-231's memory rule). */
export function takeInvitationFromFragment(
  location: Location = window.location,
): string | undefined {
  const match = /(?:^#|&)token=([\w-]{20,200})/.exec(location.hash);
  if (match?.[1] === undefined) return undefined;
  window.history.replaceState(null, "", location.pathname + location.search);
  return match[1];
}

// The portal's paths are not the firm router's registered ones, so it moves through the router's
// history by path rather than the typed `navigate`. A signed-in person goes back to the safe
// `?return=` an expired session left (P-08-T11), else to their role's landing.
function SignInPage(): JSX.Element {
  const { history } = useRouter();
  const [link] = useState(() => takeLinkFromFragment());
  return (
    <SignIn
      {...(link === undefined ? {} : { opening: { email: "", linkToken: link } })}
      onSignedIn={(landing) => {
        history.push(returnFrom(window.location.search) ?? LANDING_PATH[landing]);
      }}
    />
  );
}

/** POR-01 d: the invitation's preview, the code, then acceptance and the person's landing. */
function AcceptPage(): JSX.Element {
  const { history } = useRouter();
  const [token] = useState(() => takeInvitationFromFragment());
  return (
    <SignIn
      opening={{ email: "", invitationToken: token ?? "" }}
      onSignedIn={(landing) => {
        history.push(LANDING_PATH[landing]);
      }}
    />
  );
}

/** A signed-in area: the held token, or one refreshed from the host cookie (a reload); without a
 * session the page goes to sign-in with its own path and query to return to (P-08-T11). */
function Area({ area }: { area: string }): JSX.Element | null {
  const [signedIn, setSignedIn] = useState(() => portalAccessToken() !== null);
  useEffect(() => {
    if (signedIn) return undefined;
    let live = true;
    void ensurePortalSession().then((ok) => {
      if (!live) return;
      if (ok) setSignedIn(true);
      else goToSignIn();
    });
    return () => {
      live = false;
    };
  }, [signedIn]);
  if (!signedIn) return null;
  if (area === "Home") return <HomePage />;
  if (area === "Documents") return <DocumentsPage />;
  return <Shell area={area} />;
}

/** A nav item, to-do link or "Open binder": built areas by path, the rest stay put. */
function useAreaNavigate(): (area: string) => void {
  const { history } = useRouter();
  return (area) => {
    const path = AREA_PATHS[area];
    if (path !== undefined) history.push(path);
  };
}

/** POR-03 with `?binder=` (R-01-T10; docs/screens/POR-03.md): the newest binder by default. */
function DocumentsPage(): JSX.Element {
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const [binder] = useState(
    () => new URLSearchParams(window.location.search).get("binder") ?? undefined,
  );
  return (
    <Documents
      {...(binder === undefined ? {} : { binderId: binder })}
      mobile={mobile}
      onNavigate={navigateTo}
    />
  );
}

/** The portal's 390 layout (T7-M, DEC-45) below 768 px wide (DEC-346). */
export const PORTAL_MOBILE_QUERY = "(max-width: 767px)";

function mediaQuery(): MediaQueryList | null {
  return typeof window.matchMedia === "function" ? window.matchMedia(PORTAL_MOBILE_QUERY) : null;
}

function useMobileViewport(): boolean {
  const [mobile, setMobile] = useState(() => mediaQuery()?.matches ?? false);
  useEffect(() => {
    const query = mediaQuery();
    if (query === null) return undefined;
    const on = (): void => {
      setMobile(query.matches);
    };
    query.addEventListener("change", on);
    return () => {
      query.removeEventListener("change", on);
    };
  }, []);
  return mobile;
}

/** POR-02 with `?scope=` (P-08 §5.1): the user menu's scope switch keeps the chosen scope in the
 * address, so a reload opens the same home. */
function HomePage(): JSX.Element {
  const { history } = useRouter();
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const [scope] = useState(() => new URLSearchParams(window.location.search).get("scope"));
  return (
    <Home
      scopeId={scope}
      mobile={mobile}
      onNavigate={navigateTo}
      onScope={(id) => {
        history.replace(`/?scope=${encodeURIComponent(id)}`);
      }}
    />
  );
}

const page = (path: string, component: () => JSX.Element | null) =>
  createRoute({ getParentRoute: () => rootRoute, path, component });

export const portalTree = rootRoute.addChildren([
  page("/sign-in", SignInPage),
  page("/accept", AcceptPage), // POR-01 d (P-08-T19)
  page("/", () => <Area area="Home" />),
  page("/documents", () => <Area area="Documents" />),
  page("/requests", NotBuilt),
  page("/k1s", NotBuilt),
  page("/governance", NotBuilt),
  page("/intake", NotBuilt),
  page("/component-room", NotBuilt),
]);

export function createPortalRouter() {
  const router = createRouter({ routeTree: portalTree });
  setSignInNavigator((to) => {
    router.history.push(to);
  });
  return router;
}
