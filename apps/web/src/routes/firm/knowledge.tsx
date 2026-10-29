import { createRoute, useNavigate, useRouter, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Knowledge: `/knowledge` is KNW-01 (K-01-T04) behind `knowledge.catalog`; with the flag off it is
// the SPEC-009 document search (legacy Knowledge.tsx) it replaces. Each is its own chunk.
const Knowledge = lazyScreen(async () => (await import("../../legacy/Knowledge")).Knowledge);
const Knw01 = lazyScreen(async () => (await import("../../screens/KNW-01")).KNW01);
// K-01-T07: KNW-02's workbook slice at /knowledge/methodology/$versionId behind
// `methodology.lifecycle`; the picked program and the open sheet live in the URL (K-01 §5.1).
const Knw02 = lazyScreen(async () => (await import("../../screens/KNW-02")).KNW02);
const KNW02_SEARCH = ["program", "ov"] as const;

function pickKnw02(search: Record<string, unknown>): { program?: string; ov?: string } {
  return Object.fromEntries(
    KNW02_SEARCH.flatMap((key) => {
      const value = search[key];
      return typeof value === "string" && value !== "" ? [[key, value]] : [];
    }),
  );
}

export const knowledgeRoutes = [
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge",
    component: function KnowledgePage(): JSX.Element {
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate flag="knowledge.catalog" fallback={<Knowledge />}>
            <Knw01 />
          </FeatureGate>
        </div>
      );
    },
  }),
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge/methodology/$versionId",
    validateSearch: (search: Record<string, unknown>) => pickKnw02(search),
    component: function MethodologyVersionPage(): JSX.Element {
      const navigate = useNavigate();
      const router = useRouter();
      const versionId = useParam("versionId");
      const search = pickKnw02(useSearch({ strict: false }));
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate flag="methodology.lifecycle">
            <Knw02
              versionId={versionId}
              search={search}
              onSearch={(next) => {
                void navigate({ to: ".", search: pickKnw02({ ...next }), replace: true });
              }}
              onOpenVersion={(id) => {
                void navigate({
                  to: "/knowledge/methodology/$versionId",
                  params: { versionId: id },
                });
              }}
              onBack={() => {
                router.history.back();
              }}
            />
          </FeatureGate>
        </div>
      );
    },
  }),
] as const;
