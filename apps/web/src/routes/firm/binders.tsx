import { FlagOffState } from "@abacus/ui";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// Binders (P-06 §5.1): `/binders` → BND-01 and `/binders/$binderId` → BND-02, behind
// `binders.engine` (C5). While the flag is off the area shows F-05's flag-off state, never a 404.
// BND-02 keeps its tab and the dock's request in the search params (`?tab=`, `?request=`).

const BindersIndex = lazyScreen(async () => (await import("../../screens/BND-01")).BindersIndex);
const Binder = lazyScreen(async () => (await import("../../screens/BND-02")).BND02);

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

export const bindersRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/binders",
  component: function BindersPage(): JSX.Element {
    const navigate = bindersRoute.useNavigate();
    return gated(
      <BindersIndex
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
