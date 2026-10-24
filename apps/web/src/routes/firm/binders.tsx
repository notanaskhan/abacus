import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { type JSX, Suspense, lazy } from "react";
import { FeatureGate } from "../../app-core/flags";
import { registerOverlay } from "../../app-core/overlays";
import { appRoute, lazyScreen } from "../root";

// Binders (P-06 §5.1): `/binders` → BND-01 and `/binders/$binderId` → BND-02, behind
// `binders.engine` (C5). While the flag is off the area shows F-05's flag-off state, never a 404.
// BND-01 keeps its filters (P-06-T16) and BND-02 its tab and the dock's request in the search
// params (`?tab=`, `?request=`).

const BindersIndex = lazyScreen(
  async () => (await import("../../screens/BND-01")).BindersSearchPage,
);
const Binder = lazyScreen(async () => (await import("../../screens/BND-02")).BND02);

// SHL-14 (P-06-T13): the request composer drawer over its host, `?ov=request:new:<binderId>` or
// `?ov=request:<requestItemId>:<binderId>`. The drawer is its own chunk.
const Composer = lazy(async () => ({
  default: (await import("../../screens/SHL-14")).RequestComposer,
}));

registerOverlay("request", {
  layer: "drawer",
  render: ({ ref, close }) => {
    const [first, binderId] = ref.args;
    if (first === undefined || binderId === undefined) return null;
    return (
      <Suspense fallback={null}>
        <Composer
          binderId={binderId}
          requestId={first === "new" ? null : first}
          open
          onOpenChange={(open) => {
            if (!open) close();
          }}
        />
      </Suspense>
    );
  },
});

function gated(children: JSX.Element): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FeatureGate
        flag="binders.engine"
        fallback={<FlagOffState flag="binders.engine" label="Binders" />}
      >
        {children}
      </FeatureGate>
    </div>
  );
}

/** BND-01's filter params, as strings; BND-01 validates their values. */
interface BindersSearch {
  service?: string;
  season?: string;
  office?: string;
  preparer?: string;
  client_activity?: string;
  status?: string;
  q?: string;
}
const BINDERS_SEARCH = [
  "service",
  "season",
  "office",
  "preparer",
  "client_activity",
  "status",
  "q",
] as const;

export const bindersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/binders",
  // P-06-T16: the filters live in the URL (`?season=&client_activity=none_30_days&status=&q=`);
  // BND-01 reads and validates them (`validateBinderSearch` in domain/requests).
  validateSearch: (search: Record<string, unknown>): BindersSearch =>
    Object.fromEntries(
      BINDERS_SEARCH.flatMap((key) => {
        const value = search[key];
        return typeof value === "string" && value !== "" ? [[key, value]] : [];
      }),
    ),
  component: function BindersPage(): JSX.Element {
    // Loose hooks: the page also mounts in tests' routers (the same path, any tree).
    const navigate = useNavigate();
    const search: Record<string, unknown> = useSearch({ strict: false });
    return gated(
      <BindersIndex
        search={search}
        onSearch={(next) => {
          void navigate({ to: ".", search: next, replace: true });
        }}
        onOpen={(row) => {
          void navigate({ to: "/binders/$binderId", params: { binderId: row.id } });
        }}
      />,
    );
  },
});

interface BinderSearch {
  tab?: "activity";
  request?: string;
}

function searchOf(tab: "activity" | undefined, request: string | undefined): BinderSearch {
  return {
    ...(tab === undefined ? {} : { tab }),
    ...(request === undefined ? {} : { request }),
  };
}

export const binderRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/binders/$binderId",
  validateSearch: (search: Record<string, unknown>): BinderSearch => ({
    ...(search.tab === "activity" ? { tab: "activity" as const } : {}),
    ...(typeof search.request === "string" ? { request: search.request } : {}),
  }),
  component: function BinderPage(): JSX.Element {
    const { binderId } = binderRoute.useParams();
    const search = binderRoute.useSearch();
    const navigate = binderRoute.useNavigate();
    return gated(
      <Binder
        binderId={binderId}
        onBack={() => {
          void navigate({ to: "/binders" });
        }}
        request={search.request ?? null}
        onRequest={(id) => {
          void navigate({ search: searchOf(search.tab, id ?? undefined), replace: true });
        }}
        tab={search.tab ?? "requests"}
        onTab={(tab) => {
          void navigate({
            search: searchOf(tab === "activity" ? "activity" : undefined, search.request),
          });
        }}
      />,
    );
  },
});

export const binderRoutes = [bindersRoute, binderRoute] as const;
