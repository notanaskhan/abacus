import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
  useParams,
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
// POR-14 (R-01-T14): a third party's room, its own chunk.
const Room = lazy(async () => ({
  default: (await import("../../screens/POR-14")).POR14,
}));
// POR-16 (A-02-T28): the entity's connections, its own chunk.
const Connections = lazy(async () => ({
  default: (await import("../../screens/POR-16")).PortalConnections,
}));
// POR-06 (N-02-T26): the Sign area, its own chunk.
const SignScreen = lazy(async () => ({
  default: (await import("../../screens/POR-06")).PortalSign,
}));
// POR-05 (T-02-T24): Questions, its own chunk (`?q=` names the questionnaire).
const QuestionsScreen = lazy(async () => ({
  default: (await import("../../screens/POR-05")).POR05,
}));
// POR-13 (T-02-T27): My K-1s, its own chunk.
const K1sScreen = lazy(async () => ({
  default: (await import("../../screens/POR-13")).POR13,
}));
// POR-04 (R-01-T12): the request sheet over Documents, its own chunk.
const RequestSheetScreen = lazy(async () => ({
  default: (await import("../../screens/POR-04")).POR04,
}));

/** The portal's built areas by nav label; the others stay the shell's planned page. */
export const AREA_PATHS: Readonly<Record<string, string>> = {
  Home: "/",
  Documents: "/documents",
  Sign: "/sign",
  Questions: "/questions",
  "My K-1s": "/k1s",
};

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

const FRAGMENT = {
  link: /(?:^#|&)link=([\w-]{20,200})/,
  token: /(?:^#|&)token=([\w-]{20,200})/,
} as const;

/** The fragment's `#<name>=<token>`, read only: it leaves the address bar as it is. */
function fragmentValue(
  name: keyof typeof FRAGMENT,
  location: Location = window.location,
): string | undefined {
  return FRAGMENT[name].exec(location.hash)?.[1];
}

function clearFragment(location: Location = window.location): void {
  window.history.replaceState(null, "", location.pathname + location.search);
}

/** `#link=<token>` from a reminder email: into the page's memory, out of the address bar. */
export function takeLinkFromFragment(location: Location = window.location): string | undefined {
  const link = fragmentValue("link", location);
  if (link !== undefined) clearFragment(location);
  return link;
}

/** `#token=<token>` from an invitation email (POR-01 d): into the page's memory, out of the
 * address bar; never web storage or a query string (DEC-231's memory rule). */
export function takeInvitationFromFragment(
  location: Location = window.location,
): string | undefined {
  const token = fragmentValue("token", location);
  if (token !== undefined) clearFragment(location);
  return token;
}

/** A page's fragment token, taken once: read in the state initializer, which must stay pure
 * (StrictMode calls it twice and keeps one answer, so clearing there lost the token in dev), and
 * cleared from the address bar by an effect. */
function useFragmentToken(name: keyof typeof FRAGMENT): string | undefined {
  const [value] = useState(() => fragmentValue(name));
  useEffect(() => {
    if (value !== undefined) clearFragment();
  }, [value]);
  return value;
}

// The portal's paths are not the firm router's registered ones, so it moves through the router's
// history by path rather than the typed `navigate`. A signed-in person goes back to the safe
// `?return=` an expired session left (P-08-T11), else to their role's landing.
function SignInPage(): JSX.Element {
  const { history } = useRouter();
  const link = useFragmentToken("link");
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
  const token = useFragmentToken("token");
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
  if (area === "Request") return <RequestPage />;
  if (area === "Requests") return <RoomPage />;
  if (area === "Connections") return <ConnectionsPage />;
  if (area === "Sign") return <SignPage />;
  if (area === "Questions") return <QuestionsPage />;
  if (area === "K1s") return <K1sPage />;
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

/** POR-16 with `?entity=` (A-02-T28): the scope's entity by default; back to Home until POR-12;
 * a stale second factor signs in again and returns here; Export instead opens Documents. */
function ConnectionsPage(): JSX.Element {
  const mobile = useMobileViewport();
  const { history } = useRouter();
  const [entity] = useState(
    () => new URLSearchParams(window.location.search).get("entity") ?? undefined,
  );
  const here = `/connections${entity === undefined ? "" : `?entity=${encodeURIComponent(entity)}`}`;
  return (
    <Connections
      {...(entity === undefined ? {} : { entityId: entity })}
      mobile={mobile}
      onBack={() => {
        history.push("/");
      }}
      onStepUp={() => {
        history.push(`/sign-in?next=${encodeURIComponent(here)}`);
      }}
      onExportInstead={() => {
        history.push("/documents");
      }}
    />
  );
}

/** After POR-04 closes, the request's title on POR-03 takes focus back once it is drawn and the
 * sheet has let go of focus, so a keyboard user lands where they left (R-01-T31; WCAG 2.4.3). */
function focusRequestTitle(id: string): void {
  const selector = `[data-request="${CSS.escape(id)}"] [data-open-title]`;
  let left = 100; // 5 s at 50 ms
  const attempt = (): void => {
    const title = document.querySelector<HTMLElement>(selector);
    const inDialog = document.activeElement?.closest("[role='dialog']") ?? null;
    if (
      title !== null &&
      inDialog === null &&
      document.querySelector("[role='dialog']") === null
    ) {
      title.focus();
      if (document.activeElement === title) return;
    }
    left -= 1;
    if (left > 0) window.setTimeout(attempt, 50);
  };
  window.setTimeout(attempt, 0);
}

/** POR-03 with `?binder=` (R-01-T10; docs/screens/POR-03.md): the newest binder by default. */
function DocumentsPage(): JSX.Element {
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const [binder] = useState(
    () => new URLSearchParams(window.location.search).get("binder") ?? undefined,
  );
  const { history } = useRouter();
  return (
    <Documents
      {...(binder === undefined ? {} : { binderId: binder })}
      mobile={mobile}
      onNavigate={navigateTo}
      onOpenRequest={(id) => {
        history.push(`/documents/requests/${encodeURIComponent(id)}${window.location.search}`);
      }}
    />
  );
}

/** POR-04 over POR-03 (R-01-T12; docs/screens/POR-04.md): ✕, the scrim and Esc go back to
 * `/documents` with its `?binder=` and filters, and focus to the row that opened the sheet. */
function RequestPage(): JSX.Element {
  const { history } = useRouter();
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const params: { requestId?: string } = useParams({ strict: false });
  const [binder] = useState(
    () => new URLSearchParams(window.location.search).get("binder") ?? undefined,
  );
  return (
    <RequestSheetScreen
      requestId={params.requestId ?? ""}
      {...(binder === undefined ? {} : { binderId: binder })}
      mobile={mobile}
      onNavigate={navigateTo}
      onClose={() => {
        history.push(`/documents${window.location.search}`);
        if (params.requestId !== undefined) focusRequestTitle(params.requestId);
      }}
    />
  );
}

/** POR-14 (R-01-T14; docs/screens/POR-14.md): the room, a row open at `/requests/$requestId`
 * (full screen at 390). */
function RoomPage(): JSX.Element {
  const { history } = useRouter();
  const mobile = useMobileViewport();
  const params: { requestId?: string } = useParams({ strict: false });
  return (
    <Room
      mobile={mobile}
      {...(params.requestId === undefined ? {} : { expanded: params.requestId })}
      onExpand={(id) => {
        history.replace(id === null ? "/requests" : `/requests/${encodeURIComponent(id)}`);
      }}
    />
  );
}

/** POR-06 (N-02-T26; docs/screens/POR-06.md): the Sign list at `/sign`, an envelope at
 * `/sign/$envelopeId`, and the provider's return at `/sign/$envelopeId/return?session=` (a hint:
 * the screen reads the server's view until it says signed). */
function SignPage(): JSX.Element {
  const { history } = useRouter();
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const params: { envelopeId?: string } = useParams({ strict: false });
  const [session] = useState(() => {
    if (!window.location.pathname.endsWith("/return")) return undefined;
    return new URLSearchParams(window.location.search).get("session") ?? undefined;
  });
  return (
    <SignScreen
      {...(params.envelopeId === undefined ? {} : { envelopeId: params.envelopeId })}
      {...(session === undefined ? {} : { session })}
      mobile={mobile}
      onNavigate={navigateTo}
      onOpenEnvelope={(id) => {
        history.push(`/sign/${encodeURIComponent(id)}`);
      }}
      onBack={() => {
        history.push("/sign");
      }}
    />
  );
}

/** POR-05 (T-02-T24; docs/screens/POR-05.md): the questionnaires at `/questions?q=`. */
function QuestionsPage(): JSX.Element {
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  const [questionnaireId] = useState(
    () => new URLSearchParams(window.location.search).get("q") ?? undefined,
  );
  return (
    <QuestionsScreen
      {...(questionnaireId === undefined ? {} : { questionnaireId })}
      mobile={mobile}
      onNavigate={navigateTo}
    />
  );
}

/** POR-13 (T-02-T27; docs/screens/POR-13.md): a recipient's K-1s at `/k1s`, the reduced shell for
 * a K-1-only person and inside the full shell for a role union (DV-11). */
function K1sPage(): JSX.Element {
  const mobile = useMobileViewport();
  const navigateTo = useAreaNavigate();
  return <K1sScreen mobile={mobile} onNavigate={navigateTo} />;
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
  page("/documents/requests/$requestId", () => <Area area="Request" />), // POR-04
  page("/requests", () => <Area area="Requests" />), // POR-14
  page("/requests/$requestId", () => <Area area="Requests" />),
  page("/connections", () => <Area area="Connections" />), // POR-16 (A-02-T28)
  page("/sign", () => <Area area="Sign" />), // POR-06 (N-02-T26)
  page("/questions", () => <Area area="Questions" />), // POR-05 (T-02-T24)
  page("/sign/$envelopeId", () => <Area area="Sign" />),
  page("/sign/$envelopeId/return", () => <Area area="Sign" />),
  page("/k1s", () => <Area area="K1s" />), // POR-13 (T-02-T27)
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
