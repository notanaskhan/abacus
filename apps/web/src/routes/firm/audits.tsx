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

export const auditRoutes = [auditsRoute, auditRoute, sourceDocumentsRoute] as const;
