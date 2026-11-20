// T-05-T28 (TASK-7520; T-05 F1, §5.1; handoff TXP-00 a, TXP-02): the entity return's frame. The
// T-02 `RecordHeader` (Checkpoints ⌄ → TAX-07/SHL-16, the T-01 sync chip, the centred title with
// the state pill, "Working" while preparing, and Assistant → TAX-08) over the reviewer's Group A
// tabs; Review opens Group B. P1 review tabs are planned (T-06): absent in production, drawn
// disabled where planned screens are. The frame never fetches: the route passes the record.
import { EmptyState, MAX_OPTIONS_PER_TRACK, RecordHeader, SegmentedGroup } from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import {
  GROUP_A,
  GROUP_B,
  P1_REVIEW,
  type ReviewTab,
  type Section,
  TAB_LABEL,
} from "../../domain/tax";

export interface EntityReturnLayoutProps {
  title: string;
  context?: string;
  /** "In review · Partner", or "Working" while the workbook run prepares. */
  state?: string;
  issuesOpen?: number | null;
  section: Section;
  /** Unmapped accounts block the export: the sync chip reads "Not yet exported" until then. */
  unmapped?: number;
  onSection: (section: Section) => void;
  onCheckpoints?: () => void;
  onAssistant?: () => void;
  onSync?: () => void;
  children?: ReactNode;
  /** T-06-T29 (DEC-5741): the P1 review sections whose screens have landed behind
   * `tax.entity_depth`; they render their screen and join the track. */
  built?: ReadonlySet<ReviewTab>;
}

export const NOT_BUILT = "Not built yet";

// T-05-T68: a track holds at most seven options (C-05). The four P1 sections (T-06's) are drawn
// disabled only while they fit; with the five built sections they would make nine, so they stay
// out of the track until T-06 lands them (docs/screens/TXP-00.md, Deviations).
export function reviewOptions(
  plannedVisible: boolean = PLANNED_VISIBLE,
  built: ReadonlySet<ReviewTab> = new Set(),
  active?: ReviewTab,
): string[] {
  const all = GROUP_B.filter((t) => plannedVisible || !P1_REVIEW.has(t) || built.has(t));
  if (all.length <= MAX_OPTIONS_PER_TRACK) return all.map((t) => TAB_LABEL[t]);
  // Over seven (C-05): the built sections, the open one first, take the room the planned ones
  // leave; a built section that does not fit stays reachable by its URL.
  const base = GROUP_B.filter((t) => !P1_REVIEW.has(t));
  const room = MAX_OPTIONS_PER_TRACK - base.length;
  const extra = [...built]
    .sort((a, b) =>
      a === active ? -1 : b === active ? 1 : GROUP_B.indexOf(a) - GROUP_B.indexOf(b),
    )
    .slice(0, Math.max(0, room));
  return GROUP_B.filter((t) => base.includes(t) || extra.includes(t)).map((t) => TAB_LABEL[t]);
}

export function EntityReturnLayout(props: EntityReturnLayoutProps): JSX.Element {
  const { section } = props;
  const groupA = GROUP_A.map((t) =>
    t === "issues" && props.issuesOpen != null
      ? { label: TAB_LABEL[t], count: props.issuesOpen, bad: props.issuesOpen > 0 }
      : TAB_LABEL[t],
  );
  const reviewLabel = TAB_LABEL[section.review ?? "summary"];
  return (
    <div
      data-layout="entity-return"
      data-tab={section.tab}
      className="flex min-h-0 flex-1 flex-col"
    >
      <RecordHeader
        title={props.title}
        context={props.context}
        state={props.state}
        checkpoints
        sync="not_yet_exported"
        assistant
        {...(props.onCheckpoints ? { onCheckpoints: props.onCheckpoints } : {})}
        {...(props.onAssistant ? { onAssistant: props.onAssistant } : {})}
        {...(props.onSync ? { onSync: props.onSync } : {})}
      />
      {/* The tabs bar is 50 (T-05 §5.4 Tier D; T6's two SegmentedGroups in one 50 px row). */}
      <div data-entity="tabsbar" className="flex h-[50px] flex-none items-center justify-center">
        <SegmentedGroup
          size="small"
          label="Entity return"
          options={groupA}
          active={TAB_LABEL[section.tab]}
          sub={{
            Review: {
              options: reviewOptions(PLANNED_VISIBLE, props.built, section.review),
              active: reviewLabel,
            },
          }}
          onChange={(item, sub) => {
            const tab = GROUP_A.find((t) => TAB_LABEL[t] === item) ?? "agent";
            if (tab !== "review") {
              props.onSection({ tab });
              return;
            }
            const review = GROUP_B.find((t) => TAB_LABEL[t] === sub) ?? "summary";
            props.onSection({ tab, review });
          }}
        />
      </div>
      <div className="flex min-h-0 flex-1 flex-col">
        {section.review !== undefined &&
        P1_REVIEW.has(section.review) &&
        props.built?.has(section.review) !== true ? (
          <EmptyState title={NOT_BUILT} icon="clock">
            {TAB_LABEL[section.review]}
          </EmptyState>
        ) : (
          props.children
        )}
      </div>
    </div>
  );
}
