// T-05-T28/T29 (DEC-4520, DEC-4521): `/tax-returns/$returnId` dispatches by form family. With
// `tax.entity_workspace` on, a 1065 opens the entity layout on its Agent tab (TXP-00); a 1040 or
// 1041, or any return with the flag off, keeps TAX-02 (the route's `overview`). The entity
// sections live at `/issues`, `/workpaper`, `/activity` and `/review/$review`; a review slug that
// is not the form's goes back to the Agent tab.
import { entityRunsOptions, returnRecordOptions } from "@abacus/api-client/query";
import { EmptyState, Spinner } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { SCREEN_OF, type Section, isEntityForm, sectionOf, slugOf } from "../../domain/tax";
import { to } from "../../routes/to";
import { EntityReturnLayout, NOT_BUILT } from "./EntityReturnLayout";
import { Financials } from "../TXP-02/Financials";
import { ScheduleK } from "../TXP-05/ScheduleK";
import { Workpaper } from "../TXP-11/Workpaper";
import { Summary } from "../TXP-01/Summary";
import { Issues } from "../TXP-10/Issues";
import { TXP00, frameOf } from "./index";

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
}

export function EntityReturn({
  returnId,
  slug,
  review,
  overview,
  onOpen,
  onComposer,
}: EntityReturnProps): JSX.Element {
  const navigate = useNavigate();
  const entityOn = useFlag("tax.entity_workspace") === true;
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
      onSection={(next) => {
        if (next.tab === "intake") {
          void navigate(to.TAX03({ returnId }));
          return;
        }
        onOpen(slugOf(next));
      }}
    >
      {section.tab === "agent" ? (
        <AgentTab returnId={returnId} onComposer={onComposer} />
      ) : section.review === "financials" ? (
        <Financials returnId={returnId} form={form} taxYear={record.data.row.tax_year} />
      ) : section.review === "schedule-k" ? (
        <ScheduleK returnId={returnId} onOpen={onOpen} />
      ) : section.review === "summary" ? (
        <Summary returnId={returnId} />
      ) : section.tab === "issues" ? (
        <Issues returnId={returnId} onOpen={onOpen} />
      ) : section.tab === "workpaper" ? (
        <Workpaper returnId={returnId} />
      ) : (
        // TXP-10/01/05/07 land with their rows; until then the planned state, never blank.
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
  onComposer,
}: {
  returnId: string;
  onComposer: () => void;
}): JSX.Element {
  const runs = useQuery(entityRunsOptions({ path: { return_id: returnId } }));
  if (runs.data === undefined) return <Spinner label="Loading the workbook runs" />;
  return <TXP00 frame={frameOf(runs.data.items)} onComposer={onComposer} />;
}
