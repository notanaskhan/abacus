import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useOverlays } from "../../app-core/overlay-host";
import { appRoute, lazyScreen } from "../root";
import { useParam } from "../params";

// Audits (A-01 §5.1): `/audits` → AUD-01 and `/audits/$auditId` → AUD-02 (`$auditId` is the
// assurance work item), behind `audits.cockpit`. While the flag is off the area shows F-05's
// flag-off state, never a 404 (A-01-T21 retired the legacy board; its paths only redirect here). AUD-01 keeps its filters in the URL; AUD-02 its rail row, dock tab and document
// (`?section=`, `?dock=`, `?doc=`); AUD-03 (`/audits/$auditId/source-documents`, A-01-T15) its
// selected request, sort and search (`?item=`, `?sort=`, `?q=`).

const AuditsIndex = lazyScreen(
  async () => (await import("../../screens/AUD-01")).AuditsSearchPage,
);
const Cockpit = lazyScreen(async () => (await import("../../screens/AUD-02")).AUD02);
const SourceDocuments = lazyScreen(async () => (await import("../../screens/AUD-03")).AUD03);
const RiskRegister = lazyScreen(
  async () => (await import("../../screens/AUD-08")).RiskRegisterPage,
);
const Narrative = lazyScreen(async () => (await import("../../screens/AUD-05")).NarrativePage);
const Program = lazyScreen(async () => (await import("../../screens/AUD-04")).ProgramPage);
const Evaluation = lazyScreen(
  async () => (await import("../../screens/evaluation")).EvaluationPage,
);

function gated(children: JSX.Element): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FeatureGate
        flag="audits.cockpit"
        fallback={<FlagOffState flag="audits.cockpit" label="Audits" />}
      >
        {children}
      </FeatureGate>
    </div>
  );
}

/** AUD-01's filter params, as strings; AUD-01 validates their values (`auditFiltersOf`). */
const AUDITS_SEARCH = [
  "segment",
  "phase",
  "type",
  "partner",
  "office",
  "due",
  "period",
  "q",
] as const;
type AuditsSearch = Partial<Record<(typeof AUDITS_SEARCH)[number], string>>;

export const auditsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits",
  validateSearch: (search: Record<string, unknown>): AuditsSearch =>
    Object.fromEntries(
      AUDITS_SEARCH.flatMap((key) => {
        const value = search[key];
        return typeof value === "string" && value !== "" ? [[key, value]] : [];
      }),
    ),
  component: function AuditsPage(): JSX.Element {
    // Loose hooks: the page also mounts in tests' routers (the same path, any tree).
    const navigate = useNavigate();
    const search: Record<string, unknown> = useSearch({ strict: false });
    return gated(
      <AuditsIndex
        search={search}
        onSearch={(next) => {
          void navigate({ to: ".", search: next, replace: true });
        }}
        onOpen={(auditId) => {
          void navigate({
            to: "/audits/$auditId",
            params: { auditId },
            search: { section: "source_documents" },
          });
        }}
      />,
    );
  },
});

interface CockpitSearch {
  section?: string;
  dock?: "agent" | "viewer";
  doc?: string;
}

export const auditRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits/$auditId",
  validateSearch: (search: Record<string, unknown>): CockpitSearch => ({
    ...(typeof search.section === "string" ? { section: search.section } : {}),
    ...(search.dock === "agent" || search.dock === "viewer" ? { dock: search.dock } : {}),
    ...(typeof search.doc === "string" ? { doc: search.doc } : {}),
  }),
  component: function AuditPage(): JSX.Element {
    const auditId = useParam("auditId");
    const navigate = useNavigate();
    const search: CockpitSearch = useSearch({ strict: false });
    const overlays = useOverlays();
    const go = (next: CockpitSearch): void => {
      void navigate({ to: ".", search: next, replace: true });
    };
    return gated(
      <Cockpit
        auditId={auditId}
        {...(search.section === undefined ? {} : { section: search.section })}
        onSection={(section) => {
          go({ ...search, section });
        }}
        {...(search.dock === undefined ? {} : { dock: search.dock })}
        doc={search.doc ?? null}
        onDock={(dock, doc) => {
          go({ ...search, dock, ...(doc == null ? {} : { doc }) });
        }}
        onBack={() => {
          void navigate({ to: "/audits" });
        }}
        onAdd={(binderId) => {
          // SHL-14 (P-06-T13) over the work item's PBC binder.
          overlays.open("request", "new", binderId);
        }}
        onSignOff={(tbId) => {
          // AUD-06 "Sign off…" (A-02-T24): SHL-12's target (P-04-T48 mounts it).
          overlays.open("signoff", "trial_balance", tbId, "L2");
        }}
      />,
    );
  },
});

interface SourceDocumentsSearch {
  item?: string;
  sort?: "missing_first" | "received_first";
  q?: string;
}

export const sourceDocumentsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits/$auditId/source-documents",
  validateSearch: (search: Record<string, unknown>): SourceDocumentsSearch => ({
    ...(typeof search.item === "string" && search.item !== "" ? { item: search.item } : {}),
    ...(search.sort === "missing_first" || search.sort === "received_first"
      ? { sort: search.sort }
      : {}),
    ...(typeof search.q === "string" && search.q !== "" ? { q: search.q } : {}),
  }),
  component: function SourceDocumentsPage(): JSX.Element {
    const auditId = useParam("auditId");
    const navigate = useNavigate();
    const search: SourceDocumentsSearch = useSearch({ strict: false });
    const overlays = useOverlays();
    const go = (next: SourceDocumentsSearch): void => {
      void navigate({ to: ".", search: next, replace: true });
    };
    return gated(
      <SourceDocuments
        auditId={auditId}
        item={search.item ?? null}
        onItem={(item) => {
          go({
            ...(search.sort === undefined ? {} : { sort: search.sort }),
            ...(search.q === undefined ? {} : { q: search.q }),
            ...(item === null ? {} : { item }),
          });
        }}
        sort={search.sort ?? "missing_first"}
        onSort={(sort) => {
          go({ ...search, sort });
        }}
        q={search.q ?? ""}
        onQuery={(q) => {
          go({
            ...(search.item === undefined ? {} : { item: search.item }),
            ...(search.sort === undefined ? {} : { sort: search.sort }),
            ...(q === "" ? {} : { q }),
          });
        }}
        onBack={() => {
          void navigate({ to: "/audits" });
        }}
        onSection={(section) => {
          void navigate({ to: "/audits/$auditId", params: { auditId }, search: { section } });
        }}
        onAdd={(binderId) => {
          overlays.open("request", "new", binderId);
        }}
      />,
    );
  },
});

// A-06-T12: the Evaluation routes (AUD-15 findings, AUD-16 misstatements, AUD-17 review notes,
// AUD-20 financial statements), lazy, each the audit bar and its tabs over the planned screen.
type EvaluationTab = "findings" | "misstatements" | "review-notes" | "fs-disclosure";

function evaluationRoute(tab: EvaluationTab) {
  return createRoute({
    getParentRoute: () => appRoute,
    path: `/audits/$auditId/${tab}`,
    component: function EvaluationRoutePage(): JSX.Element {
      const auditId = useParam("auditId");
      const navigate = useNavigate();
      return gated(
        <Evaluation
          auditId={auditId}
          tab={tab}
          onTab={(next) => {
            void navigate({ to: `/audits/$auditId/${next}`, params: { auditId } });
          }}
          onBack={() => {
            void navigate({ to: "/audits/$auditId", params: { auditId } });
          }}
        />,
      );
    },
  });
}

// A-04-T20: AUD-08 `/audits/$auditId/risks?filter=unaddressed`, its drawer `?ov=risk:<code>`.
export const risksRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits/$auditId/risks",
  validateSearch: (search: Record<string, unknown>): { filter?: "unaddressed" } =>
    search.filter === "unaddressed" ? { filter: "unaddressed" } : {},
  component: function RisksPage(): JSX.Element {
    const auditId = useParam("auditId");
    const navigate = useNavigate();
    const search: { filter?: "unaddressed" } = useSearch({ strict: false });
    const overlays = useOverlays();
    return gated(
      <RiskRegister
        auditId={auditId}
        filter={search.filter ?? null}
        onFilter={(filter) => {
          void navigate({ to: ".", search: filter === null ? {} : { filter }, replace: true });
        }}
        onRisk={(code) => {
          overlays.open("risk", code);
        }}
        onBack={() => {
          void navigate({ to: "/audits/$auditId", params: { auditId } });
        }}
      />,
    );
  },
});

// A-04-T27: AUD-04 `/audits/$auditId/program/$wpRef?tab=linkage|approach` (Service Organizations
// by default); Adopt (L1) and Sign off… open SHL-12 on the paper.
type ProgramSearch = { tab?: "linkage" | "approach" };
export const programRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits/$auditId/program/$wpRef",
  validateSearch: (search: Record<string, unknown>): ProgramSearch =>
    search.tab === "linkage" || search.tab === "approach" ? { tab: search.tab } : {},
  component: function ProgramRoutePage(): JSX.Element {
    const auditId = useParam("auditId");
    const wpRef = useParam("wpRef");
    const navigate = useNavigate();
    const search: ProgramSearch = useSearch({ strict: false });
    const overlays = useOverlays();
    return gated(
      <Program
        auditId={auditId}
        workpaperId={wpRef}
        tab={search.tab ?? "service_organizations"}
        onTab={(tab) => {
          void navigate({
            to: ".",
            search: tab === "service_organizations" ? {} : { tab },
            replace: true,
          });
        }}
        onSignOff={(workpaperId, level) => {
          overlays.open("signoff", "workpaper", workpaperId, level);
        }}
        onBack={() => {
          void navigate({ to: "/audits/$auditId", params: { auditId } });
        }}
      />,
    );
  },
});

// A-04-T21: AUD-05 `/audits/$auditId/narrative/$wpRef?tab=risk|fraud`; Summary and Linkage open
// AUD-08; Escalate… opens SHL-14 with the flag as its prefill (`?ov=request:new&prefill=`).
export const narrativeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/audits/$auditId/narrative/$wpRef",
  validateSearch: (search: Record<string, unknown>): { tab?: "fraud" } =>
    search.tab === "fraud" ? { tab: "fraud" } : {},
  component: function NarrativeRoutePage(): JSX.Element {
    const auditId = useParam("auditId");
    const wpRef = useParam("wpRef");
    const navigate = useNavigate();
    const search: { tab?: "fraud" } = useSearch({ strict: false });
    const overlays = useOverlays();
    return gated(
      <Narrative
        auditId={auditId}
        workpaperId={wpRef}
        tab={search.tab ?? "risk"}
        onTab={(tab) => {
          void navigate({ to: ".", search: tab === "fraud" ? { tab } : {}, replace: true });
        }}
        onRegister={() => {
          void navigate({ to: "/audits/$auditId/risks", params: { auditId } });
        }}
        onRemind={() => {
          overlays.open("request", "new");
        }}
        onEscalate={(flag) => {
          void navigate({
            to: ".",
            search: (prev: Record<string, unknown>) => ({
              ...prev,
              ov: "request:new",
              prefill: flag.id,
            }),
          });
        }}
        onAdopt={(workpaperId) => {
          overlays.open("signoff", "workpaper", workpaperId, "L1");
        }}
        onBack={() => {
          void navigate({ to: "/audits/$auditId", params: { auditId } });
        }}
      />,
    );
  },
});

export const findingsRoute = evaluationRoute("findings");
export const misstatementsRoute = evaluationRoute("misstatements");
export const reviewNotesRoute = evaluationRoute("review-notes");
export const fsDisclosureRoute = evaluationRoute("fs-disclosure");

export const auditRoutes = [
  auditsRoute,
  auditRoute,
  sourceDocumentsRoute,
  risksRoute,
  narrativeRoute,
  programRoute,
  findingsRoute,
  misstatementsRoute,
  reviewNotesRoute,
  fsDisclosureRoute,
] as const;
