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
// K-02-T13: KNW-04 at /knowledge/standards; `?section=` picks the standard (K-02 §5). The screen
// draws its own flag-off state (the T12 frame with C-20 "not turned on"), so no gate here.
const Knw04 = lazyScreen(async () => (await import("../../screens/KNW-04")).KNW04);
// K-01-T13: KNW-03 at /knowledge/programs/$programId behind `methodology.programs` (K-01 §5 route
// table): `?segment=`, `?step=<n>` and `?from=citation` (the SHL-07 ↗ arrival lights the step).
const Knw03 = lazyScreen(async () => (await import("../../screens/KNW-03")).KNW03);

interface Knw03Search {
  segment?: "steps" | "guidance" | "pbc" | "rules" | "changes";
  step?: number;
  from?: "citation";
}

function pickKnw03(search: Record<string, unknown>): Knw03Search {
  const segment = search.segment;
  const step = Number(search.step);
  return {
    ...(segment === "steps" ||
    segment === "guidance" ||
    segment === "pbc" ||
    segment === "rules" ||
    segment === "changes"
      ? { segment }
      : {}),
    ...(Number.isInteger(step) && step > 0 ? { step } : {}),
    ...(search.from === "citation" ? { from: "citation" as const } : {}),
  };
}
const KNW04_SECTIONS: ReadonlySet<string> = new Set([
  "review_checklists",
  "review_levels",
  "return_approval",
  "aje_thresholds",
  "variance_thresholds",
  "materiality_ranges",
  "document_confidence",
  "ssars_cas",
  // K-02-T17: j, Deadline rules (DF-10).
  "deadline_rules",
]);

function pickKnw04(search: Record<string, unknown>): { section?: string } {
  const section = search.section;
  return typeof section === "string" && KNW04_SECTIONS.has(section) ? { section } : {};
}

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
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge/programs/$programId",
    validateSearch: (search: Record<string, unknown>) => pickKnw03(search),
    component: function ProgramEditorPage(): JSX.Element {
      const navigate = useNavigate();
      const programId = useParam("programId");
      const search = pickKnw03(useSearch({ strict: false }));
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <FeatureGate flag="methodology.programs">
            <Knw03
              programId={programId}
              {...search}
              onSegment={(segment) => {
                void navigate({ to: ".", search: { ...search, segment }, replace: true });
              }}
              onProgram={(id) => {
                void navigate({ to: "/knowledge/programs/$programId", params: { programId: id } });
              }}
              onBack={() => {
                void navigate({ to: "/knowledge" });
              }}
            />
          </FeatureGate>
        </div>
      );
    },
  }),
  createRoute({
    getParentRoute: () => appRoute,
    path: "/knowledge/standards",
    validateSearch: (search: Record<string, unknown>) => pickKnw04(search),
    component: function FirmStandardsPage(): JSX.Element {
      const navigate = useNavigate();
      const search = pickKnw04(useSearch({ strict: false }));
      return (
        <div className="flex min-h-0 flex-1 flex-col">
          <Knw04
            initial={search.section === undefined ? {} : { section: search.section }}
            onBack={() => {
              void navigate({ to: "/knowledge" });
            }}
            onSection={(section) => {
              void navigate({ to: ".", search: { section }, replace: true });
            }}
          />
        </div>
      );
    },
  }),
] as const;
