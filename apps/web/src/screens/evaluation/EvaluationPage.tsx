import {
  auditFindingsOptions,
  misstatementsOptions,
  reviewNoteListOptions,
} from "@abacus/api-client/query";
import { Segmented, type TabOption, ViewStateBody, type ViewState } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { ReviewNotesPane } from "../AUD-17";
import { FsDisclosurePane } from "../AUD-20";
import { AuditBar, isNotFound, useAuditCockpit } from "../../domain/audits";
import { FindingsRegister } from "../AUD-15";
import { MisstatementsPane } from "../AUD-16";
import { COPY } from "./copy";

// The Evaluation chrome (A-06-T12; A-06 §5, chapter 04 §2.1): the audit bar, then the Evaluation
// tabs (Findings · Misstatements · Review notes · Sign-offs, 50 px) with counts from the server —
// the findings still awaiting a decision (the list's `awaiting_decision` count: AUD-15 a's
// "Findings 3", DEC-2612), the misstatements list total and the engagement's open review notes —
// linking
// `/audits/$auditId/findings`, `/misstatements` and `/review-notes`; `/fs-disclosure` (AUD-20) has
// the bar alone. The four screens (AUD-15, AUD-16, AUD-17, AUD-20) land with their own rows (AUD-15
// with A-06-T18): until
// then each body is the planned target, "Not built yet" in dev, fixture and gallery builds and
// nothing in production.

export type EvaluationTab = "findings" | "misstatements" | "review-notes" | "fs-disclosure";

const LABEL: Record<Exclude<EvaluationTab, "fs-disclosure">, string> = {
  findings: COPY.findings,
  misstatements: COPY.misstatements,
  "review-notes": COPY.reviewNotes,
};

function useCounts(workItemId: string, engagementId: string | undefined) {
  const findings = useQuery(auditFindingsOptions({ path: { work_item_id: workItemId } }));
  const misstatements = useQuery(misstatementsOptions({ path: { work_item_id: workItemId } }));
  const notes = useQuery({
    ...reviewNoteListOptions({ query: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== undefined,
  });
  return {
    findings: findings.data?.counts?.awaiting_decision,
    misstatements: misstatements.data?.total,
    "review-notes": notes.data?.total,
  };
}

export function EvaluationTabs({
  tab,
  counts,
  onTab,
}: {
  tab: EvaluationTab;
  counts: Partial<Record<EvaluationTab, number | undefined>>;
  onTab: (tab: EvaluationTab) => void;
}): JSX.Element {
  const keys = Object.keys(LABEL) as (keyof typeof LABEL)[];
  const options: TabOption[] = [
    ...keys.map((k) => ({
      label: LABEL[k],
      ...(counts[k] === undefined ? {} : { count: counts[k] }),
    })),
    { label: COPY.signOffs, disabled: true },
  ];
  const active = tab === "fs-disclosure" ? undefined : LABEL[tab];
  return (
    <div data-evaluation-tabs="" className="flex h-[50px] items-center justify-center hairline-b">
      <Segmented
        label={COPY.tabs}
        options={options}
        {...(active === undefined ? {} : { active })}
        onChange={(label) => {
          const next = keys.find((k) => LABEL[k] === label);
          if (next !== undefined) onTab(next);
        }}
      />
    </div>
  );
}

export function EvaluationPage({
  auditId,
  tab,
  onTab,
  onBack,
}: {
  auditId: string;
  tab: EvaluationTab;
  onTab: (tab: EvaluationTab) => void;
  onBack?: () => void;
}): JSX.Element {
  const cockpit = useAuditCockpit(auditId);
  const open = useOpenOverlay();
  const counts = useCounts(auditId, cockpit.data?.engagement_id);
  let state: ViewState = { kind: "ready" };
  if (cockpit.isError) {
    state = isNotFound(cockpit.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void cockpit.refetch() };
  } else if (cockpit.data === undefined) state = { kind: "loading" };
  return (
    <div data-screen="evaluation" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      <ViewStateBody state={state} empty={{ title: COPY.planned }}>
        {cockpit.data !== undefined && (
          <>
            <AuditBar cockpit={cockpit.data} {...(onBack === undefined ? {} : { onBack })} />
            {tab !== "fs-disclosure" && <EvaluationTabs tab={tab} counts={counts} onTab={onTab} />}
            {tab === "findings" && <FindingsRegister auditId={auditId} />}
            {/* A-06-T22: AUD-16 under the Misstatements tab. */}
            {tab === "misstatements" && (
              <MisstatementsPane
                auditId={auditId}
                onFinding={() => {
                  onTab("findings");
                }}
              />
            )}
            {/* A-06-T24: AUD-17 under the Review notes tab. */}
            {tab === "review-notes" && (
              <ReviewNotesPane
                engagementId={cockpit.data.engagement_id}
                workItemId={cockpit.data.work_item_id}
                onSignOff={(type, id, level) => {
                  open(ov.SHL12(type, id, `L${String(level)}`));
                }}
              />
            )}
            {/* A-06-T30: AUD-20, the Evaluation route with no tab of its own. */}
            {tab === "fs-disclosure" && (
              <FsDisclosurePane
                engagementId={cockpit.data.engagement_id}
                onMismatch={() => {
                  onTab("misstatements");
                }}
                {...(onBack === undefined ? {} : { onCockpit: onBack })}
              />
            )}
          </>
        )}
      </ViewStateBody>
    </div>
  );
}
