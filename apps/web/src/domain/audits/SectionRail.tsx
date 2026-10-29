import type { AuditCockpitOut, AuditSectionRowOut } from "@abacus/api-client";
import { RecordRail, status } from "@abacus/ui";
import type { JSX } from "react";
import { AUDIT_MESSAGES } from "./messages";
import { railModel } from "./rail";

// The audit cockpit's rail (A-01-T06; AUD-02, AUD-03): the C-03 RecordRail with the OverviewCard,
// the Overview links and one band per projected band. It renders the rows it is given and nothing
// else: a section with no registered provider never reaches it (DV-1). A planned target (Methodology
// → KNW-03, Activity → AUD-29 …) opens nothing; `onOpen` receives only rows with a built screen.

export interface SectionRailProps {
  cockpit: Pick<AuditCockpitOut, "bands" | "overview">;
  /** The selected row's key (`?section=`); Source Documents by default. */
  selected?: string;
  /** A row with a built target was picked: the screen routes to `row.route`. */
  onOpen?: (row: AuditSectionRowOut) => void;
  /** "Begin…" on a not-started section (only rendered with `engagement_run.start`). */
  onBegin?: (row: AuditSectionRowOut) => void;
  /** The overview pill reads "Processing" while a C6 engagement run executes (DV-11). */
  processing?: boolean;
}

export function SectionRail({
  cockpit,
  selected = "source_documents",
  onOpen,
  onBegin,
  processing = false,
}: SectionRailProps): JSX.Element {
  const model = railModel(cockpit);
  const open = (id: string): void => {
    const row = model.rows.get(id);
    if (row === undefined || model.planned.has(id)) return;
    onOpen?.(row);
  };
  return (
    <RecordRail
      title={AUDIT_MESSAGES.railTitle}
      card={{
        kind: "audit",
        title: cockpit.overview.name,
        sub: [cockpit.overview.period_label, cockpit.overview.client_name]
          .filter((s): s is string => typeof s === "string" && s !== "")
          .join(" · "),
        state: status("audit_engagement", processing ? "processing" : cockpit.overview.phase)
          .label,
      }}
      links={model.links}
      linksTitle={AUDIT_MESSAGES.bands.overview}
      tight
      sections={model.sections}
      selected={selected}
      onOpen={(item) => {
        open(item.id);
      }}
      onBegin={(phase) => {
        const row = model.rows.get(phase.id);
        if (row !== undefined) onBegin?.(row);
      }}
    />
  );
}
