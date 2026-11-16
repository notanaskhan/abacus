import type { CriterionOut, ScoredEntryOut } from "@abacus/api-client";
import { getJeTestOptions, listEntriesOptions } from "@abacus/api-client/query";
import { ErrorState, MatchScope, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import {
  CardWell,
  CriteriaTable,
  FIELDWORK_COPY,
  PopulationCard,
  SelectedEntriesCard,
  type SelectedEntry,
  TestingFooter,
} from "../../domain/fieldwork";

// AUD-12 live, JE artboards (S47 partials, TASK-8354): GET /v1/je-tests/{id} and its selected
// entries (`?selected=true`, cursor pages), on the A-08 kit's JE cards. Every figure is the API's
// (code's scoring and draw); the words are the kit's (FIELDWORK_COPY, from the handoff). A row's
// test result is "Not started" until per-entry results have a read (recorded in TASK-8354); the
// host opens SHL-15 for Raise exception… and AUD-11 for Expand testing….

export interface Aud12LiveProps {
  jeTestId: string;
  onRaise?: (() => void) | undefined;
  onExpand?: (() => void) | undefined;
  onAdopt?: (() => void) | undefined;
}

export function AUD12Live({ jeTestId, onRaise, onExpand, onAdopt }: Aud12LiveProps): JSX.Element {
  const test = useQuery(getJeTestOptions({ path: { je_test_id: jeTestId } }));
  const [filter, setFilter] = useState<CriterionOut["key"] | null>(null);
  // Each page: its cursor and the count of entries on the pages before it.
  const [pages, setPages] = useState<{ cursor: string | null; offset: number }[]>([
    { cursor: null, offset: 0 },
  ]);
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const page = pages[pages.length - 1] ?? { cursor: null, offset: 0 };
  const cursor = page.cursor;
  const entries = useQuery({
    ...listEntriesOptions({
      path: { je_test_id: jeTestId },
      query: {
        selected: true,
        ...(filter === null ? {} : { criterion: filter }),
        ...(cursor === null ? {} : { cursor }),
      },
    }),
    enabled: test.data?.selection != null,
  });
  if (test.isError || entries.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void test.refetch();
          void entries.refetch();
        }}
      />
    );
  }
  const data = test.data;
  if (data === undefined) return <Skeleton className="h-[480px]" />;
  const K = FIELDWORK_COPY.criteria;
  const sel = data.selection;
  const selected = sel === null ? 0 : sel.by_score + sel.unpredictable;
  const from = page.offset + 1;
  const rows: SelectedEntry[] = (entries.data?.items ?? []).map(
    (entry: ScoredEntryOut, i): SelectedEntry => ({
      position: from + i,
      entry,
      result: "not_started",
    }),
  );
  return (
    <MatchScope className="flex gap-[12px]">
      <div data-screen="AUD-12" data-live="true" className="flex w-[536px] flex-col">
        <CardWell>
          <PopulationCard
            source={data.population_source ?? ""}
            entries={data.entries_count}
            lines={data.lines_count}
            periodStart={data.period_start ?? ""}
            periodEnd={data.period_end ?? ""}
            postCloseThrough={data.post_close_through ?? undefined}
            tie={data.tie}
          />
          <CriteriaTable
            criteria={data.criteria}
            uniqueFlagged={data.unique_flagged}
            filter={filter}
            onFilter={(key) => {
              setFilter(key);
              setPages([{ cursor: null, offset: 0 }]);
            }}
            footer={
              sel === null
                ? undefined
                : K.footer(selected, sel.by_score, sel.score_min, sel.unpredictable) +
                  (sel.approved_by_initials !== null && sel.approved_on !== null
                    ? K.approved(sel.approved_by_initials, sel.approved_on)
                    : "")
            }
          />
          {sel !== null && entries.data === undefined && <Skeleton className="h-[240px]" />}
          {sel !== null && entries.data !== undefined && (
            <SelectedEntriesCard
              rows={rows}
              total={selected}
              from={from}
              selectedRef={selectedRef}
              onSelect={setSelectedRef}
              onPage={(direction) => {
                const shown = entries.data.items.length;
                const next = entries.data.next_cursor;
                if (direction === 1 && next !== null) {
                  setPages((p) => [...p, { cursor: next, offset: page.offset + shown }]);
                } else if (direction === -1 && pages.length > 1) {
                  setPages((p) => p.slice(0, -1));
                }
              }}
              pending={
                sel.pending_expansion != null
                  ? {
                      add: sel.pending_expansion.add_count,
                      initials: sel.pending_expansion.approver_initials,
                    }
                  : undefined
              }
            />
          )}
        </CardWell>
        <TestingFooter
          {...(onAdopt === undefined ? {} : { onAdopt })}
          {...(onExpand === undefined ? {} : { onExpand })}
          {...(onRaise === undefined ? {} : { onRaise })}
        />
      </div>
    </MatchScope>
  );
}
