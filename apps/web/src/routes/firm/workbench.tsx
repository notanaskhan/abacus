import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate } from "@tanstack/react-router";
import { type JSX, Suspense, lazy } from "react";
import { registerOverlay } from "../../app-core/overlays";
import { useFlag } from "../../app-core/flags";
import { useParam } from "../params";
import { to } from "../to";
import { appRoute, lazyScreen } from "../root";

// Workbench sessions (W-02-T08; W-02 §5.1; docs/screens/WB-01.md to WB-03.md). Behind
// `workbench.enabled`: off, every path draws F-05's flag-off state (never a blank pane) and the
// API answers 404. `/workbench` is WB-01 (`?filter=` `?q=`; HOME-01's "3 running" pill links to
// `?filter=running`); `/workbench/sessions/new` is WB-02 (SHL-02 "New session…" and the list's "+");
// `/workbench/sessions/$sessionId` is the thread (WB-01 a–g and WB-03's run arc).
// Planned links (hidden in production, "Not built yet" in fixture builds): WB-04, WB-06, WB-07,
// WB-10, WB-12 (W-01, W-03).

const FLAG = "workbench.enabled";
const FILTERS = ["all", "mine", "via_agent", "running", "needs_answer"] as const;
type Filter = (typeof FILTERS)[number];
const isFilter = (v: unknown): v is Filter =>
  typeof v === "string" && (FILTERS as readonly string[]).includes(v);

interface WorkbenchSearch {
  filter?: Filter;
  q?: string;
  session?: string;
}

function validateWorkbenchSearch(search: Record<string, unknown>): WorkbenchSearch {
  return {
    ...(isFilter(search.filter) && search.filter !== "all" ? { filter: search.filter } : {}),
    ...(typeof search.q === "string" && search.q !== "" ? { q: search.q } : {}),
    ...(typeof search.session === "string" && search.session !== ""
      ? { session: search.session }
      : {}),
  };
}

const Sessions = lazyScreen(async () => (await import("../../screens/WB-01")).WB01);
const NewSession = lazyScreen(async () => (await import("../../screens/WB-02")).WB02);
const Thread = lazyScreen(async () => (await import("../../screens/WB-03")).WB03);
const Connect = lazyScreen(async () => (await import("../../screens/WB-10")).WB10);
const CONNECT_FLAG = "integrations.connect_v1";

function Gate({ children }: { children: JSX.Element }): JSX.Element {
  const on = useFlag(FLAG) === true;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {on ? children : <FlagOffState flag={FLAG} label="Workbench" />}
    </div>
  );
}

export const workbenchRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/workbench",
  validateSearch: validateWorkbenchSearch,
  component: function WorkbenchPage(): JSX.Element {
    const search = workbenchRoute.useSearch();
    const navigate = workbenchRoute.useNavigate();
    return (
      <Gate>
        <Sessions
          filter={search.filter ?? "all"}
          q={search.q ?? ""}
          sessionId={search.session ?? null}
          onQuery={(q) => void navigate({ search: { ...search, q }, replace: true })}
          onSelect={(session) => void navigate({ search: { ...search, session } })}
          onNew={(href) => void navigate({ href })}
          onConnect={() => void navigate({ to: "/workbench/connect" })}
          onFilter={(f) => {
            const rest = Object.fromEntries(
              Object.entries(search).filter(([k]) => k !== "filter"),
            ) as WorkbenchSearch;
            void navigate({ search: f === "all" ? rest : { ...rest, filter: f }, replace: true });
          }}
        />
      </Gate>
    );
  },
});

export const newSessionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/workbench/sessions/new",
  component: function NewSessionPage(): JSX.Element {
    const navigate = useNavigate();
    return (
      <Gate>
        <NewSession
          list={
            <Sessions
              filter="all"
              q=""
              sessionId={null}
              onQuery={() => undefined}
              onSelect={(sessionId) =>
                void navigate({ to: "/workbench/sessions/$sessionId", params: { sessionId } })
              }
              onNew={() => undefined}
            />
          }
          onDraft={() => undefined}
          // W-02-T16: the answer's Internal Control link opens AUD-09 on that sheet.
          onOpenControl={(auditId) => {
            if (auditId !== null) {
              void navigate({ ...to.AUD09({ auditId }), search: { sheet: "internal-control" } });
            }
          }}
        />
      </Gate>
    );
  },
});

export const sessionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/workbench/sessions/$sessionId",
  component: function SessionPage(): JSX.Element {
    const sessionId = useParam("sessionId");
    const navigate = useNavigate();
    return (
      <Gate>
        <Thread
          sessionId={sessionId}
          list={
            <Sessions
              filter="all"
              q=""
              sessionId={sessionId}
              onQuery={() => undefined}
              onSelect={(next) =>
                void navigate({
                  to: "/workbench/sessions/$sessionId",
                  params: { sessionId: next },
                })
              }
              onNew={(href) => void navigate({ href })}
            />
          }
        />
      </Gate>
    );
  },
});

// WB-03 d2: the O4 workbook preview over the thread, `?ov=artifact:<artifactId>` (W-02-T20 draws
// the sheet; registered here so the link resolves in fixture mode).
export const ARTIFACT_KEY = "artifact";
const ArtifactPreview = lazy(async () => ({
  default: (await import("../../screens/WB-03/ArtifactPreview")).ArtifactPreview,
}));
registerOverlay(ARTIFACT_KEY, {
  layer: "modal",
  render: ({ ref, close }) => {
    const artifactId = ref.args[0];
    return artifactId === undefined ? null : (
      <Suspense fallback={null}>
        <ArtifactPreview artifactId={artifactId} onClose={close} />
      </Suspense>
    );
  },
});

// W-01-T12: WB-10 Workbench › Connect, `/workbench/connect?category=&status=&q=`, behind
// `integrations.connect_v1` (off: F-05's flag-off state, never blank; the API answers 404).
const CATEGORIES = [
  "tax",
  "practice",
  "erp",
  "grc",
  "docs",
  "comms",
  "prod",
  "crm",
  "hris",
  "spend",
];
const CONNECT_STATUSES = ["connected", "available", "coming_soon"] as const;

interface ConnectSearch {
  category?: string;
  status?: (typeof CONNECT_STATUSES)[number];
  q?: string;
}

function validateConnectSearch(search: Record<string, unknown>): ConnectSearch {
  const status = CONNECT_STATUSES.find((s) => s === search.status);
  return {
    ...(typeof search.category === "string" && CATEGORIES.includes(search.category)
      ? { category: search.category }
      : {}),
    ...(status === undefined ? {} : { status }),
    ...(typeof search.q === "string" && search.q !== "" ? { q: search.q } : {}),
  };
}

export const connectRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/workbench/connect",
  validateSearch: validateConnectSearch,
  component: function ConnectPage(): JSX.Element {
    const search = connectRoute.useSearch();
    const navigate = useNavigate();
    const on = useFlag(CONNECT_FLAG) === true;
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        {on ? (
          <Connect
            initial={{
              category: search.category ?? null,
              status: search.status ?? null,
              q: search.q ?? "",
            }}
            onTab={(tab) => {
              if (tab === "sessions") void navigate({ to: "/workbench" });
            }}
          />
        ) : (
          <FlagOffState flag={CONNECT_FLAG} label="Connect" />
        )}
      </div>
    );
  },
});

// W-01-T17: where a provider sends the browser back (`connect_service.CALLBACK_PATH`). It posts
// the provider's state and code once, then returns to WB-10 with the outcome; a refused or
// replayed state reads as expired and the person starts again (never a provider's own message).
const CALLBACK_REASONS: Record<string, string> = {
  invalid_state: "This link has expired or was already used. Start connecting again.",
  connect_declined: "The connection wasn't approved. Start connecting again.",
};
const CallbackLayer = lazy(async () => ({
  default: (await import("../../screens/WB-11/callback")).ConnectCallback,
}));

export const connectCallbackRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/workbench/connect/callback",
  validateSearch: (search: Record<string, unknown>): { state?: string; code?: string } => ({
    ...(typeof search.state === "string" ? { state: search.state } : {}),
    ...(typeof search.code === "string" ? { code: search.code } : {}),
  }),
  component: function ConnectCallbackPage(): JSX.Element {
    const search = connectCallbackRoute.useSearch();
    const navigate = useNavigate();
    return (
      <Suspense fallback={null}>
        <CallbackLayer
          state={search.state ?? ""}
          code={search.code ?? ""}
          reasons={CALLBACK_REASONS}
          onDone={() => void navigate({ to: "/workbench/connect", replace: true })}
        />
      </Suspense>
    );
  },
});

export const workbenchRoutes = [
  workbenchRoute,
  newSessionRoute,
  sessionRoute,
  connectRoute,
  connectCallbackRoute,
] as const;
