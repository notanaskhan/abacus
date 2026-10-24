// The audit cockpit's section rail as the C-03 Rail kit draws it (A-01-T06; A-01 §5.2; DV-1).
// Rows come only from the cockpit projection's bands, which hold only registered sections
// (`register_audit_section`): nothing here adds, invents or reorders a row. Each row's state is a
// registry code (`audit_section`) drawn in one of two grammars, never colour alone:
//   sub_line   the run grammar (AUD-02 a): disc + "Complete · 9:26 AM", "Running", "Queued" …
//   idle_pill  the audit-program grammar (AUD-02 g): "Ready" / "In progress" pills
// The Overview band's rows are links (Client, Methodology … Source Documents "11 of 24 received").

import type { AuditBandOut, AuditCockpitOut, AuditSectionRowOut } from "@abacus/api-client";
import type {
  DiscState,
  IconName,
  Phase,
  RailLink,
  RailSection,
  RegistryContext,
} from "@abacus/ui";
import { status } from "@abacus/ui";
import { AUDIT_MESSAGES } from "./messages";

type SectionCode = NonNullable<AuditSectionRowOut["section_state"]>;

/** The Overview band's lead icons by section key (AUD-02 spec RailRows). */
const LINK_ICON: Readonly<Record<string, IconName>> = {
  client: "user-round",
  methodology: "layers",
  standards_set: "book-open",
  source_documents: "file",
  team: "users-round",
  activity: "clock",
};

/** The action that lets a person start a not-started section ("Begin…"; P-10's run engine). */
export const BEGIN_ACTION = "engagement_run.start";

/** "Blocked on a {role} decision": the role the cockpit names (AUD-02 a, the partner). */
const BLOCKED_ROLE = "partner";

function resolved(code: SectionCode, context?: RegistryContext) {
  return status("audit_section", code, {
    ...(context === undefined ? {} : { context }),
    vars: { role: BLOCKED_ROLE },
  });
}

/** The disc a code draws (the registry's), `todo` for a row without a state. */
export function discOf(code: SectionCode | null | undefined): DiscState {
  if (code == null) return "todo";
  return resolved(code).disc?.state ?? "todo";
}

/** The run grammar's sub-line: the projection's code-built text, else the registry's word. */
export function subLineOf(row: AuditSectionRowOut): string | null {
  if (row.sub_line != null && row.sub_line !== "") return row.sub_line;
  if (row.section_state == null) return null;
  return resolved(row.section_state, "sub_line_when_run_active").label;
}

/** The audit-program grammar's pill (AUD-02 g): "Ready" or "In progress", none when idle. */
export function idlePillOf(row: AuditSectionRowOut): Phase["pill"] | undefined {
  const code = row.section_state;
  if (code == null || code === "not_started" || code === "queued") return undefined;
  if (code === "ready_to_run" || code === "draft_ready") {
    return { kind: "ready", text: resolved("ready_to_run").label };
  }
  const word = resolved(code, "pill_when_idle");
  const pill = word.label === resolved(code).label ? resolved(code, "pill") : word;
  return { kind: "progress", text: pill.label };
}

export function phaseOf(row: AuditSectionRowOut): Phase {
  const begin = (row.allowed_actions ?? []).includes(BEGIN_ACTION);
  const base: Phase = { id: row.key, title: row.title, ...(begin ? { begin: true } : {}) };
  if (row.grammar === "idle_pill") {
    const pill = idlePillOf(row);
    if (pill === undefined) return { ...base, disc: discOf(row.section_state) };
    return { ...base, disc: pill.kind === "ready" ? "done" : "half", pill };
  }
  const text = subLineOf(row);
  return {
    ...base,
    disc: discOf(row.section_state),
    ...(text === null
      ? {}
      : {
          live: {
            text,
            ...(row.section_state === "blocked_on_decision" ? { tone: "amber" as const } : {}),
          },
        }),
  };
}

export function linkOf(row: AuditSectionRowOut): RailLink {
  const icon = LINK_ICON[row.key];
  return {
    id: row.key,
    title: row.title,
    ...(icon === undefined ? {} : { icon }),
    ...(row.sub_line == null ? {} : { sub: row.sub_line }),
  };
}

export interface RailModel {
  links: RailLink[];
  sections: RailSection[];
  /** Planned targets (DV-1): rows whose screen is not built open nothing. */
  planned: ReadonlySet<string>;
  /** The rows by key, for the screen's routing (`route`, `blocked_on_name`). */
  rows: ReadonlyMap<string, AuditSectionRowOut>;
}

function sectionOf(band: AuditBandOut): RailSection {
  return {
    id: band.key,
    title: AUDIT_MESSAGES.bands[band.key],
    ...(band.collapsed === true ? { collapsed: true } : {}),
    phases: (band.rows ?? []).map(phaseOf),
  };
}

/** The cockpit's bands as the Rail kit's links and sections, in the projection's order. */
export function railModel(cockpit: Pick<AuditCockpitOut, "bands">): RailModel {
  const bands = cockpit.bands ?? [];
  const all = bands.flatMap((b) => b.rows ?? []);
  const overview = bands.find((b) => b.key === "overview");
  return {
    links: (overview?.rows ?? []).map(linkOf),
    sections: bands.filter((b) => b.key !== "overview").map(sectionOf),
    planned: new Set(all.filter((r) => r.link === "planned").map((r) => r.key)),
    rows: new Map(all.map((r) => [r.key, r])),
  };
}
