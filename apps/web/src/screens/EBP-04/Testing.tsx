import type { TestGridOut } from "@abacus/api-client";
import { ebpContributionsTestOptions } from "@abacus/api-client/query";
import { Amount, Button, Pill, Skeleton, cn } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { COPY } from "./copy";

// EBP-04 c · Testing (A-05-T32; A-05 §3 F6; AUD-12 variant b grammar): the 25-participant deferral
// and match recalculation on the shared attribute-test grid (`GET …/ebp/contributions/test`). Each
// cell shows the figure as recorded and code's recalculation; an exception row that traces to an
// EBP-03 sample item opens it. Draft 4a schedule hands the late remittance to EBP-07. The browser
// recalculates nothing (ADR-050).

// The grid's three attributes (compensation, deferrals, match) between the # and link columns.
const COLS = "grid grid-cols-[40px_110px_1fr_1fr_1fr_120px] items-center";

const RESULT: Record<string, "green-tint" | "red-tint" | "amber" | "muted"> = {
  pass: "green-tint",
  exception: "red-tint",
  needs_human: "amber",
  no_effect: "muted",
  agent_tested: "muted",
  not_started: "muted",
};

export function ContributionsTesting({
  workItemId,
  enabled,
  onEligibility,
  onDraft4a,
}: {
  workItemId: string;
  enabled: boolean;
  /** EBP-03 on the participant's sample item. */
  onEligibility?: (itemId: string) => void;
  onDraft4a?: () => void;
}): JSX.Element {
  const grid = useQuery({
    ...ebpContributionsTestOptions({ path: { work_item_id: workItemId } }),
    enabled,
  });
  const data: TestGridOut | undefined = grid.data;
  if (data === undefined) return <Skeleton className="mx-[12px] h-[320px]" />;
  const T = COPY.testingGrid;
  return (
    <section
      data-ebp04="testing"
      className="mx-[12px] flex flex-col rounded-pane bg-card shadow-e1"
    >
      <p className="flex h-[40px] items-center px-[14px] text-[13.5px] font-medium hairline-b">
        {T.title(data.rows.length)}
      </p>
      <div className="flex flex-col">
        <div
          role="group"
          className={cn(COLS, "h-[28px] bg-nested text-[11.5px] font-medium text-ink-3")}
        >
          <span className="px-[8px]">#</span>
          <span className="px-[8px]">{T.participant}</span>
          {data.attributes.map((a) => (
            <span key={a} className="px-[8px] text-right">
              {T.attribute[a] ?? a}
            </span>
          ))}
          <span className="px-[8px]" />
        </div>
        {data.rows.map((r) => (
          <div
            key={r.item_id}
            role="group"
            data-test-row={r.position}
            data-state={r.state}
            className={cn(
              COLS,
              "min-h-[30px] text-cell hairline-b",
              r.state === "exception" && "bg-sel-bg",
            )}
          >
            <span className="px-[8px] text-ink-3 tabular-nums">{r.position}</span>
            <span className="px-[8px]">{r.record_key}</span>
            {data.attributes.map((a) => {
              const c = r.cells.find((x) => x.attribute_key === a);
              return (
                <span
                  key={a}
                  data-cell={a}
                  className="flex items-center justify-end gap-[6px] px-[8px]"
                >
                  {c?.expected !== null && c?.expected !== undefined && (
                    <Amount value={c.expected} style="cents" data-expected />
                  )}
                  {c !== undefined && c.result !== "pass" && (
                    <Pill variant={RESULT[c.result] ?? "muted"} size="micro">
                      {T.result[c.result] ?? c.result}
                    </Pill>
                  )}
                </span>
              );
            })}
            <span className="px-[8px]">
              {r.linked_item_id !== null &&
                r.linked_item_id !== undefined &&
                onEligibility !== undefined && (
                  <button
                    type="button"
                    data-link="EBP-03"
                    className="text-dense font-medium"
                    onClick={() => {
                      onEligibility(r.linked_item_id as string);
                    }}
                  >
                    {T.openEligibility} <span className="text-ink-3">→</span>
                  </button>
                )}
            </span>
          </div>
        ))}
      </div>
      <div className="flex justify-end p-[10px]">
        <Button
          variant="secondary"
          size="sm"
          disabled={onDraft4a === undefined}
          onClick={onDraft4a}
        >
          {COPY.draft4a}
        </Button>
      </div>
    </section>
  );
}
