// AUD-13 live (A-08-T32; TASK-8546; DEC-5531): one analytics set on `GET /v1/analytics-sets/{id}`,
// in the T6 statement grammar of the fixture screen (whole numbers, negatives in parentheses, no
// dollar sign). Every figure, flag and status is the server's: lines, derived subtotals (`derived`),
// over/within, the tallies and the dual threshold. An explanation is the line's own, drawn through
// AgentText with its author; accepting is a person's (`analytics.accept` in `allowed_actions`,
// ADR-005), for every explained line at once against the set's `review_hash`. The agent drafts and
// the client questions stay on the fixture screen's sheet until their reads land (DEC-5531).
import type { AnalyticsLineOut, AnalyticsSetOut } from "@abacus/api-client";
import {
  acceptExplanationsMutation,
  getAnalyticsSetOptions,
  getAnalyticsSetQueryKey,
} from "@abacus/api-client/query";
import {
  AgentText,
  Amount,
  Button,
  DASH,
  ErrorState,
  Pill,
  Skeleton,
  amount,
  cn,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { BlockCard } from "../../domain/fieldwork";
import { AUD13_COPY as C } from "./copy";

const TH = "h-[30px] bg-nested px-[8px] text-[11.5px] font-medium text-ink-3";
const TD = "px-[8px] py-[6px] text-[12px] align-top";
const GROUPS = ["income_statement", "balance_sheet"] as const;

function pct(value: string | null): string {
  if (value === null) return DASH;
  return value.startsWith("-") ? `(${value.slice(1)}%)` : `${value}%`;
}

function Status({ line }: { line: AnalyticsLineOut }): JSX.Element {
  if (line.status === null || line.status === "within") {
    return <span className="text-ink-3">{C.within}</span>;
  }
  if (line.status === "accepted") {
    return (
      <Pill variant="green-tint">
        {C.acceptedBy(line.explanation?.accepted_by_initials ?? "")}
      </Pill>
    );
  }
  if (line.status === "explained") return <Pill variant="neutral">Explained</Pill>;
  return <Pill variant="amber">Unexplained</Pill>;
}

function Note({ line }: { line: AnalyticsLineOut }): ReactNode {
  const e = line.explanation;
  if (e === null) return <span className="text-ink-3">{DASH}</span>;
  return (
    <span className="flex flex-col gap-[4px]">
      <AgentText text={e.text} />
      <span className="text-[11.5px] text-ink-3">{e.authored_by_name}</span>
    </span>
  );
}

function Statement({ set }: { set: AnalyticsSetOut }): JSX.Element {
  const final = set.stage === "final";
  const cols = [
    C.columns.account,
    final ? C.columns.cyAdjusted : C.columns.cy,
    C.columns.py,
    C.columns.change,
    C.columns.pct,
    C.columns.threshold,
    C.columns.explanation,
    C.columns.status,
  ];
  return (
    <table className="w-full border-collapse" data-aud13="statement">
      <caption className="sr-only">{final ? C.finalTitle : C.title}</caption>
      <thead>
        <tr className="hairline-b">
          {cols.map((h, i) => (
            <th
              key={h}
              scope="col"
              className={cn(TH, i === 0 || i >= 5 ? "text-left" : "text-right")}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      {GROUPS.map((group) => (
        <tbody key={group}>
          <tr>
            <th
              scope="colgroup"
              colSpan={cols.length}
              className="h-[28px] px-[8px] text-left text-[9.5px] font-medium tracking-[0.06em] text-ink-3"
            >
              {C.groups[group]}
            </th>
          </tr>
          {set.lines
            .filter((l) => l.group_key === group)
            .sort((a, b) => a.position - b.position)
            .map((l) =>
              l.derived ? (
                <tr
                  key={l.fs_line_key}
                  data-subtotal={l.caption}
                  className="font-medium hairline-b"
                >
                  <th scope="row" className={cn(TD, "text-left font-medium")}>
                    {l.caption}
                  </th>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.cy} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.py} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.change} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right tabular-nums")}>{pct(l.change_pct)}</td>
                  <td className={TD} colSpan={3} />
                </tr>
              ) : (
                <tr
                  key={l.fs_line_key}
                  data-line={l.fs_line_key}
                  data-over={l.over ? "" : undefined}
                  data-status={l.status ?? undefined}
                  className={cn(
                    "hairline-b",
                    l.over && l.status === "unexplained" && "bg-amber-tint",
                  )}
                >
                  <th scope="row" className={cn(TD, "text-left font-normal")}>
                    {l.caption}
                  </th>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.cy} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.py} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={l.change} style="whole" />
                  </td>
                  <td className={cn(TD, "text-right tabular-nums")}>{pct(l.change_pct)}</td>
                  <td className={TD}>
                    <span className={cn(!l.over && "text-ink-3")}>
                      {l.over ? C.over : C.within}
                    </span>
                  </td>
                  <td className={cn(TD, "w-[290px]")}>
                    <Note line={l} />
                  </td>
                  <td className={TD}>
                    <Status line={l} />
                  </td>
                </tr>
              ),
            )}
        </tbody>
      ))}
    </table>
  );
}

function Tally({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-w-[112px] flex-col gap-[4px] rounded-[10px] bg-card px-[12px] py-[8px] shadow-e1">
      <span className="text-[9.5px] font-medium tracking-[0.06em] text-ink-3 uppercase">
        {label}
      </span>
      <span className="text-[14px] tabular-nums">{children}</span>
    </div>
  );
}

export function AUD13Live({ analyticsSetId }: { analyticsSetId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const options = { path: { analytics_set_id: analyticsSetId } };
  const read = useQuery(getAnalyticsSetOptions(options));
  const accept = useMutation({
    ...acceptExplanationsMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: getAnalyticsSetQueryKey(options) });
    },
  });
  if (read.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void read.refetch();
        }}
      />
    );
  }
  const set = read.data;
  if (set === undefined) return <Skeleton className="h-[480px]" />;
  const t = set.tallies;
  const title =
    set.stage === "final"
      ? C.finalTitle
      : set.stage === "substantive"
        ? C.substantiveTitle
        : C.title;
  const explained = set.lines.filter((l) => l.status === "explained").map((l) => l.position);
  const mayAccept =
    set.allowed_actions.includes("analytics.accept") && set.review_hash !== undefined;
  return (
    <div data-screen="AUD-13" data-live="true" className="bg-shell p-[12px]">
      <section aria-label={title} className="flex w-[1036px] flex-col gap-[10px]">
        <header className="flex h-[46px] items-center justify-between">
          <h1 className="text-[14.5px] font-medium">{title}</h1>
          <span className="text-[12.5px] text-ink-3">{set.basis_label}</span>
        </header>
        <div data-aud13="tallies" className="flex flex-wrap gap-[8px]">
          <Tally label={C.tally.lines}>{t.lines}</Tally>
          <Tally label={C.tally.over}>{t.over_threshold}</Tally>
          <Tally label={C.tally.explained}>{t.explained}</Tally>
          <Tally label={C.tally.unexplained}>
            <Pill variant={t.unexplained > 0 ? "amber" : "muted"}>{t.unexplained}</Pill>
          </Tally>
          <Tally label={C.tally.threshold}>
            {C.tally.thresholdOf(set.threshold.pct, amount(set.threshold.amount, "dollars").text)}
          </Tally>
        </div>
        <BlockCard title={title}>
          <Statement set={set} />
        </BlockCard>
        {mayAccept && explained.length > 0 && (
          <footer className="flex h-[44px] items-center gap-[8px]">
            <Button
              variant="tonal"
              disabled={accept.isPending}
              onClick={() => {
                accept.mutate({
                  path: { analytics_set_id: analyticsSetId },
                  headers: { "Idempotency-Key": crypto.randomUUID() },
                  body: { line_positions: explained, seen_hash: set.review_hash ?? "" },
                });
              }}
            >
              {C.footer.accept}
            </Button>
            <span className="text-[12px] text-ink-3">{C.footer.note}</span>
          </footer>
        )}
      </section>
    </div>
  );
}
