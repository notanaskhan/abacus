// T-05-T28/T29 (DEC-4520, DEC-4521): `/tax-returns/$returnId` dispatches by form family. With
// `tax.entity_workspace` on, a 1065 opens the entity layout on its Agent tab (TXP-00); a 1040 or
// 1041, or any return with the flag off, keeps TAX-02 (the route's `overview`). The entity
// sections live at `/issues`, `/workpaper`, `/activity` and `/review/$review`; a review slug that
// is not the form's goes back to the Agent tab.
import type { TaxReturnRecordOut } from "@abacus/api-client";
import { entityRunsOptions, returnRecordOptions } from "@abacus/api-client/query";
import { EmptyState, Spinner } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { useEntitlement, useFlag } from "../../app-core/flags";
import { useOpenHref } from "../../app-core/open";
import {
  type ReviewTab,
  SCREEN_OF,
  type Section,
  isEntityForm,
  sectionOf,
  slugOf,
} from "../../domain/tax";
import { hrefOf, to } from "../../routes/to";
import { EntityReturnLayout, NOT_BUILT } from "./EntityReturnLayout";
import { Financials } from "../TXP-02/Financials";
import { ScheduleK } from "../TXP-05/ScheduleK";
import { Workpaper } from "../TXP-11/Workpaper";
import { Summary } from "../TXP-01/Summary";
import { Issues } from "../TXP-10/Issues";
import { CapitalAccounts } from "../TXP-07/CapitalAccounts";
import { FixedAssets } from "../TXP-03/FixedAssets";
import { BookTax } from "../TXP-04/BookTax";
import { COPY } from "./copy";
import { TXP00, frameOf } from "./index";

/** T-06's review sections built so far (T-06-T29 to T31). */
const DEPTH_BUILT: ReadonlySet<ReviewTab> = new Set<ReviewTab>(["fixed-assets", "m1-m3"]);

export type EntitySlug = "agent" | "issues" | "workpaper" | "activity" | "review";

export interface EntityReturnProps {
  returnId: string;
  slug: EntitySlug;
  /** The `$review` segment under `/review/`. */
  review?: string;
  /** The route's own screen (TAX-02 on the return, T-04's TAX-04 to TAX-07 on its sections),
   * drawn for a 1040 or 1041, or with the flag off. */
  overview: JSX.Element;
  /** Open an entity section: the path after `/tax-returns/$returnId` ("" is the Agent tab). The
   * sections are planned screens without manifest paths yet, so the route navigates. */
  onOpen: (suffix: string) => void;
  /** The composer hands off to TAX-08 (the route's `?ov=assistant`). */
  onComposer: () => void;
  /** T-06-T29: the opening search a section reads (`?view=`); default: the page's own. */
  search?: string;
}

export function EntityReturn({
  returnId,
  slug,
  review,
  overview,
  onOpen,
  onComposer,
  search,
}: EntityReturnProps): JSX.Element {
  const navigate = useNavigate();
  const entityOn = useFlag("tax.entity_workspace") === true;
  // T-06 §0: TXP-03/04/08/09 open behind `tax.entity_depth`; off, the tab stays planned.
  const depthOn = useFlag("tax.entity_depth") === true;
  // T-05-T66 (AC-13.2): a firm without `tax_entity_returns` keeps the coordination view, locked.
  const entitled = useEntitlement("tax_entity_returns");
  // With the flag off nothing is fetched: the route's own screen draws as before.
  const record = useQuery({
    ...returnRecordOptions({ path: { return_id: returnId } }),
    enabled: entityOn,
  });
  if (!entityOn) return overview;
  if (record.data === undefined) {
    return <Spinner label="Loading the return" />;
  }
  const form = record.data.row.form;
  if (!isEntityForm(form)) return overview;
  if (!entitled) {
    return (
      <div data-entity-locked className="flex min-h-0 flex-1 flex-col gap-[10px]">
        <EmptyState icon="lock" className="flex-none" title={COPY.lockedTitle}>
          {COPY.lockedBody}
        </EmptyState>
        {overview}
      </div>
    );
  }
  const section: Section | null = slug === "review" ? sectionOf("review", review) : { tab: slug };
  if (section === null) {
    return <Navigate {...to.TAX02({ returnId })} replace />;
  }
  const screen = SCREEN_OF[section.review ?? section.tab];
  return (
    <EntityReturnLayout
      title={`${String(record.data.row.tax_year)} Form ${form}`}
      context={record.data.row.client_name}
      section={section}
      {...(depthOn ? { built: DEPTH_BUILT } : {})}
      onSection={(next) => {
        if (next.tab === "intake") {
          void navigate(to.TAX03({ returnId }));
          return;
        }
        onOpen(slugOf(next));
      }}
    >
      {section.tab === "agent" ? (
        <AgentTab returnId={returnId} record={record.data} onComposer={onComposer} />
      ) : section.review === "financials" ? (
        <Financials returnId={returnId} form={form} taxYear={record.data.row.tax_year} />
      ) : section.review === "schedule-k" ? (
        <ScheduleK returnId={returnId} onOpen={onOpen} />
      ) : section.review === "fixed-assets" && depthOn ? (
        <FixedAssets returnId={returnId} {...(search === undefined ? {} : { search })} />
      ) : (section.review === "m1-m3" || section.review === "schedule-m2") && depthOn ? (
        <BookTax
          returnId={returnId}
          frame={section.review}
          onOpen={onOpen}
          {...(search === undefined ? {} : { search })}
        />
      ) : section.review === "capital" ? (
        <CapitalAccounts returnId={returnId} />
      ) : section.review === "summary" ? (
        <Summary returnId={returnId} />
      ) : section.tab === "issues" ? (
        <Issues returnId={returnId} />
      ) : section.tab === "workpaper" ? (
        <Workpaper returnId={returnId} />
      ) : (
        // A section whose screen is not built yet: the planned state, never blank.
        <EmptyState title={NOT_BUILT} icon="clock">
          {screen ?? ""}
        </EmptyState>
      )}
    </EntityReturnLayout>
  );
}

// T-05-T29: TXP-00 on the return's workbook runs (the newest run sets the frame).
function AgentTab({
  returnId,
  record,
  onComposer,
}: {
  returnId: string;
  record: TaxReturnRecordOut;
  onComposer: () => void;
}): JSX.Element {
  const navigate = useNavigate();
  const openHref = useOpenHref();
  const runs = useQuery(entityRunsOptions({ path: { return_id: returnId } }));
  if (runs.data === undefined) return <Spinner label="Loading the workbook runs" />;
  const review =
    (section: string, search: Record<string, string> = {}) =>
    () => {
      void navigate({ ...to.TXP02({ returnId, section }), search });
    };
  // T-05-T69 (handoff TXP-00 INTERACTIONS): a row's name opens its Review sub-tab. Fixed assets
  // (TXP-03) and states (TXP-09) are T-06's screens, so those rows stay text.
  const taskTargets: Record<string, () => void> = {
    import_trial_balance: review("financials"),
    map_lines: review("financials"),
    contributions_distributions: () => void navigate(to.TXP07({ returnId, section: "capital" })),
    capital_m2: () => void navigate(to.TXP07({ returnId, section: "capital" })),
    interim_closing_706d: () =>
      void navigate({
        ...to.TXP06({ returnId, section: "schedule-k" }),
        search: { ov: "allocation" },
      }),
    federal_k1s: () => void navigate(to.TXP12({ returnId })),
    state_k1s_k3s: () => void navigate(to.TXP12({ returnId })),
  };
  const { row } = record;
  const short = row.client_name.split(/[\s,]/u)[0] ?? row.client_name;
  return (
    <TXP00
      frame={frameOf(runs.data.items)}
      waitingOn={runs.data.items[0]?.waiting_on ?? []}
      onComposer={onComposer}
      taskTargets={taskTargets}
      // "n open" → TXP-10; "View work" → TXP-11 (the workbook opens on its sheet there).
      onOpenItems={() => void navigate(to.TXP10({ returnId }))}
      onViewWork={() => void navigate(to.TXP11({ returnId }))}
      links={[
        { key: "client", label: COPY.linkRows.client, value: row.client_name },
        {
          key: "engagement",
          label: COPY.linkRows.engagement,
          value: COPY.engagementLink(row.tax_year, row.form),
        },
        { key: "binder", label: COPY.linkRows.binder, value: COPY.binderLink(row.tax_year) },
        {
          key: "files",
          label: COPY.linkRows.files,
          value: COPY.filesLink(row.tax_year, short),
          // FIL-01 is built: the client's folder (`/files/$clientId`, as TAX-02 links it).
          onOpen: () => {
            openHref(`${hrefOf(to.FIL01())}/${encodeURIComponent(row.client_id)}`);
          },
        },
      ]}
    />
  );
}
