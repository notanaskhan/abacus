// T-05-T28 (TASK-7520; T-05 F1, §5.1; handoff TXP-00 a, TXP-02): the entity return's frame. The
// T-02 `RecordHeader` (Checkpoints ⌄ → TAX-07/SHL-16, the T-01 sync chip, the centred title with
// the state pill, "Working" while preparing, and Assistant → TAX-08) over the reviewer's Group A
// tabs; Review opens Group B. P1 review tabs are planned (T-06): absent in production, drawn
// disabled where planned screens are. The frame never fetches: the route passes the record.
import { EmptyState, RecordHeader, SegmentedGroup } from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { GROUP_A, GROUP_B, P1_REVIEW, type Section, TAB_LABEL } from "../../domain/tax";

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
}

export const NOT_BUILT = "Not built yet";

function reviewOptions(): string[] {
  return GROUP_B.filter((t) => PLANNED_VISIBLE || !P1_REVIEW.has(t)).map((t) => TAB_LABEL[t]);
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
      <div className="flex justify-center py-[7px]">
        <SegmentedGroup
          size="small"
          label="Entity return"
          options={groupA}
          active={TAB_LABEL[section.tab]}
          sub={{ Review: { options: reviewOptions(), active: reviewLabel } }}
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
        {section.review !== undefined && P1_REVIEW.has(section.review) ? (
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
