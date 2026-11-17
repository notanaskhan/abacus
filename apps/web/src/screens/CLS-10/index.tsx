// CLS-10 · Flux (C-01-T40; handoff CLS-10 a to e; SPEC-655 AC-48, AC-49): T6 inside the close
// shell's Review tab. The set is code's (`GET /v1/closes/{id}/flux?basis=`): each income
// statement line with its prior and current amounts as adjusted, the change, the change % and the
// dual-threshold test; the browser formats and never computes a figure. Only a line over both
// legs carries "Explain…" (the agent drafts with citations, never accepts) and "Accept" (a Manager
// or Partner, `flux.accept`; a draft is adopted by a person's own explanation first). Year over
// year without the prior year's ledger reads dashes and "Not comparable" (d); Budget is disabled
// with "No budget on file". Accepted lines raise the commentary banner (c).
import type { FluxLineOut, FluxSetOut, FluxSubtotalOut } from "@abacus/api-client";
import {
  acceptFluxLineMutation,
  closeFluxOptions,
  closeFluxQueryKey,
  closeSummaryOptions,
  explainFluxLineMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  DASH,
  Button,
  Icon,
  NumberedCitation,
  Pill,
  Segmented,
  Skeleton,
  Spinner,
  StatusDisc,
  TallyStrip,
  amount,
  monthYear,
  pct,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, type JSX, useState } from "react";
import { useCan } from "../../app-core/can";
import { COPY, fill } from "./copy";

export type Basis = "mom" | "yoy";

export interface CLS10Props {
  closeId: string;
  /** A scenario's starting surfaces: the basis (d) and a line whose explain run is in flight (e). */
  initial?: { basis?: Basis; explaining?: string };
  onOpen?: (target: "CLS-06" | "CLS-07" | "KNW-04", ref?: string) => void;
}

/** Whole dollars, no "$": negatives in parentheses, zero and missing as a dash (A6). */
export function whole(v: string | null | undefined): string {
  return amount(v ?? null, "whole").text;
}

/** A one-place percent from the set's percent (12.5 is 12.5%), negatives in parentheses. */
export function percent(v: string | null | undefined): string {
  return v === null || v === undefined ? "—" : pct(String(Number(v) / 100), { decimals: 1 });
}

function negative(v: string | null | undefined): boolean {
  return v !== null && v !== undefined && Number(v) < 0;
}

function priorPeriod(period: string, basis: Basis): string {
  const [y, m] = period.split("-").map(Number) as [number, number];
  if (basis === "yoy") return `${String(y - 1)}-${String(m).padStart(2, "0")}`;
  return m === 1 ? `${String(y - 1)}-12` : `${String(y)}-${String(m - 1).padStart(2, "0")}`;
}

/** The tally strip's counts, from the set's own counts and the lines' tests (A8.12). */
export function talliesOf(set: FluxSetOut): {
  tested: number;
  over: number;
  explained: number;
  unexplained: number;
  accepted: number;
} {
  const over = set.lines.filter((l) => l.test === "over_both");
  return {
    tested: set.tested,
    over: over.length,
    explained: set.explained,
    unexplained: set.unexplained,
    accepted: over.filter((l) => l.status === "accepted").length,
  };
}

function StatusCell({ line, onIssue }: { line: FluxLineOut; onIssue: () => void }): JSX.Element {
  if (line.status === "within_threshold") {
    return <span className="text-ink-2">{COPY.status.within_threshold}</span>;
  }
  if (line.status === "accepted") {
    return (
      <Pill variant="green-tint">
        {fill(COPY.status.accepted, { initials: line.accepted_by?.initials ?? "" })}
      </Pill>
    );
  }
  if (line.status === "unexplained") {
    return (
      <span className="flex items-center gap-[6px]">
        <Pill variant="amber">{COPY.status.unexplained}</Pill>
        <button type="button" className="text-[12px] font-medium" onClick={onIssue}>
          {COPY.issue} <span className="text-ink-3">›</span>
        </button>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-[6px]">
      <StatusDisc state="done" size={13} />
      {line.status === "explained_draft" ? COPY.status.explained_draft : COPY.status.explained}
    </span>
  );
}

function Explanation({ line, tracing }: { line: FluxLineOut; tracing: boolean }): JSX.Element {
  if (tracing) {
    return (
      <span data-tracing="" className="flex items-center gap-[6px] text-ink-3">
        <Spinner size={12} label={COPY.explaining} />
        {COPY.explaining}
      </span>
    );
  }
  if (line.explanation == null) return <span className="text-ink-4">—</span>;
  const cites = (line.drivers ?? []).map((d, i) => (
    <NumberedCitation key={d.citation_id} n={i + 1} label={d.label} verified />
  ));
  return (
    <span className="flex flex-wrap items-baseline gap-[4px] text-[12.5px] leading-[1.45]">
      {line.status === "explained_draft" ? (
        <AgentText inline text={line.explanation} />
      ) : (
        <span>{line.explanation}</span>
      )}
      {cites}
    </span>
  );
}

export function CLS10({ closeId, initial = {}, onOpen }: CLS10Props): JSX.Element {
  const queryClient = useQueryClient();
  const [basis, setBasis] = useState<Basis>(initial.basis ?? "mom");
  const options = { path: { close_id: closeId }, query: { basis } };
  const flux = useQuery(closeFluxOptions(options));
  const summary = useQuery(closeSummaryOptions({ path: { close_id: closeId } }));
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: closeFluxQueryKey(options) });
  };
  const explain = useMutation({ ...explainFluxLineMutation(), onSuccess: refresh });
  const accept = useMutation({ ...acceptFluxLineMutation(), onSuccess: refresh });
  const period = summary.data?.period ?? null;
  // Accept is a Manager's or Partner's (`flux.accept` on the close's engagement); a Senior never
  // sees it, and the server answers 403 regardless.
  const mayAccept = useCan("flux.accept", { engagementId: summary.data?.engagement_id });
  const tracingId = explain.isPending
    ? explain.variables.path.line_id
    : (flux.data?.lines.find((l) => l.line_key === initial.explaining)?.line_id ?? null);

  if (flux.isPending || flux.data === undefined) {
    return (
      <div data-screen-body="CLS-10" className="flex flex-col gap-[8px] p-[12px]">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-[34px] w-full" />
        ))}
      </div>
    );
  }
  const set = flux.data;
  const t = talliesOf(set);
  const current = period === null ? "" : monthYear(period);
  const prior = period === null ? "" : monthYear(priorPeriod(period, basis));
  const month = current.split(" ")[0] ?? "";

  return (
    <div data-screen-body="CLS-10" data-basis={basis} className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[44px] items-center px-[12px]">
        <Segmented
          size="small"
          label={COPY.segments.flux}
          active={COPY.segments.flux}
          options={[
            { label: COPY.segments.issues, count: summary.data?.open_issues ?? 0 },
            { label: COPY.segments.adjustments, count: summary.data?.adjustments ?? 0 },
            { label: COPY.segments.flux, count: t.over },
          ]}
          onChange={(label) => {
            if (label === COPY.segments.issues) onOpen?.("CLS-06");
            else if (label === COPY.segments.adjustments) onOpen?.("CLS-07");
          }}
        />
        <span className="absolute left-1/2 -translate-x-1/2 text-[14.5px] font-medium">
          {fill(COPY.title, { current: month === "" ? "" : current, prior })}
        </span>
        <button
          type="button"
          onClick={() => {
            onOpen?.("KNW-04");
          }}
          className="ml-auto flex h-[29px] items-center gap-[4px] rounded-pill bg-card px-[12px] text-[12.5px] shadow-e1"
        >
          {fill(COPY.threshold, { label: set.threshold_label })}
          <span className="text-ink-3">›</span>
        </button>
      </div>
      <TallyStrip
        className="px-[12px]"
        label={COPY.segments.flux}
        items={[
          { label: COPY.tally.tested, value: String(t.tested) },
          { label: COPY.tally.over, value: String(t.over) },
          { label: COPY.tally.explained, value: String(t.explained) },
          { label: COPY.tally.unexplained, value: String(t.unexplained) },
          {
            label: COPY.tally.accepted,
            value: fill(COPY.tally.acceptedValue, { n: t.accepted, total: t.over }),
            ...(t.accepted < t.over
              ? { pill: { text: COPY.tally.pending, variant: "muted" as const } }
              : {}),
          },
        ]}
      />
      {t.accepted > 0 ? (
        <div
          data-banner=""
          className="mx-[12px] mt-[8px] flex h-[32px] items-center rounded-card bg-green-tint px-[12px] text-[12.5px] text-green-ink"
        >
          {t.accepted === 1
            ? fill(COPY.bannerOne, { month })
            : fill(COPY.banner, { n: t.accepted, month })}
        </div>
      ) : null}
      <section className="m-[12px] flex min-h-0 flex-1 flex-col rounded-pane bg-card shadow-e2">
        <header className="relative flex h-[46px] items-center px-[12px]">
          <span title={set.budget_available ? undefined : COPY.noBudget}>
            <Segmented
              size="small"
              label={COPY.pane}
              active={COPY.basis[basis]}
              options={[
                COPY.basis.mom,
                COPY.basis.yoy,
                { label: COPY.basis.budget, disabled: true },
              ]}
              onChange={(label) => {
                setBasis(label === COPY.basis.yoy ? "yoy" : "mom");
              }}
            />
          </span>
          <span className="absolute left-1/2 -translate-x-1/2 text-[14.5px] font-medium">
            {COPY.pane}
          </span>
          <a
            className="ml-auto text-[12.5px] font-medium"
            href={`/v1/closes/${closeId}/flux.xlsx?basis=${basis}`}
            download
          >
            {COPY.openExcel}
          </a>
        </header>
        <p className="px-[12px] pb-[6px] text-[11.5px] text-ink-3">{COPY.asAdjusted}</p>
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="h-[30px] bg-band-hd text-[11.5px] font-medium text-ink-3">
                <th className="w-[230px] px-[12px] text-left">{COPY.columns.line}</th>
                <th className="w-[110px] px-[8px] text-right">{prior}</th>
                <th className="w-[110px] px-[8px] text-right">{current}</th>
                <th className="w-[100px] px-[8px] text-right">{COPY.columns.change}</th>
                <th className="w-[80px] px-[8px] text-right">{COPY.columns.changePct}</th>
                <th className="w-[150px] px-[8px] text-left">{COPY.columns.test}</th>
                <th className="px-[8px] text-left">{COPY.columns.explanation}</th>
                <th className="w-[140px] px-[8px] text-left">{COPY.columns.status}</th>
                <th className="w-[150px]" />
              </tr>
            </thead>
            <tbody>
              {set.lines.map((line) => {
                const over = line.test === "over_both";
                const unexplained = line.status === "unexplained";
                const after = (set.subtotals ?? []).filter(
                  (s) => s.after_line_key === line.line_key,
                );
                return (
                  <Fragment key={line.line_id}>
                    <tr
                      data-line={line.line_key}
                      data-test={line.test}
                      className="h-[34px] border-t border-hair align-top"
                    >
                      <td className="px-[12px] py-[8px] text-[12.5px]">{line.caption}</td>
                      <td className="px-[8px] py-[8px] text-right tabular-nums">
                        {whole(line.prior)}
                      </td>
                      <td className="px-[8px] py-[8px] text-right tabular-nums">
                        {whole(line.current)}
                      </td>
                      <td
                        data-variance={
                          over ? (unexplained ? "unexplained" : "explained") : undefined
                        }
                        className={`px-[8px] py-[8px] text-right tabular-nums ${
                          over && unexplained ? "bg-amber-tint font-medium text-amber-ink" : ""
                        } ${negative(line.change) ? "text-red" : ""}`}
                      >
                        {over && unexplained ? (
                          <Icon
                            name="triangle-alert"
                            size={12}
                            className="mr-[4px] inline text-amber"
                          />
                        ) : null}
                        {whole(line.change)}
                      </td>
                      <td
                        className={`px-[8px] py-[8px] text-right tabular-nums ${
                          negative(line.change_pct) ? "text-red" : ""
                        }`}
                      >
                        {percent(line.change_pct)}
                      </td>
                      <td className="px-[8px] py-[8px]">{COPY.test[line.test]}</td>
                      <td className="px-[8px] py-[8px]">
                        <Explanation line={line} tracing={tracingId === line.line_id} />
                      </td>
                      <td className="px-[8px] py-[8px]">
                        <StatusCell
                          line={line}
                          onIssue={() => {
                            onOpen?.("CLS-06", line.line_key);
                          }}
                        />
                      </td>
                      <td className="px-[8px] py-[6px] text-right">
                        {over && line.status !== "accepted" ? (
                          <span className="flex justify-end gap-[6px]">
                            <Button
                              variant="ghost"
                              size="xs"
                              loading={tracingId === line.line_id}
                              onClick={() => {
                                explain.mutate({
                                  path: { line_id: line.line_id },
                                  headers: { "Idempotency-Key": crypto.randomUUID() },
                                });
                              }}
                            >
                              {COPY.explain}
                            </Button>
                            {mayAccept ? (
                              <Button
                                variant="secondary"
                                size="xs"
                                disabled={line.status !== "explained"}
                                onClick={() => {
                                  accept.mutate({
                                    path: { line_id: line.line_id },
                                    headers: { "If-Match": String(line.row_version ?? 1) },
                                  });
                                }}
                              >
                                {COPY.accept}
                              </Button>
                            ) : null}
                          </span>
                        ) : null}
                      </td>
                    </tr>
                    {after.map((s) => (
                      <SubtotalRow key={s.kind} subtotal={s} />
                    ))}
                  </Fragment>
                );
              })}
              {(set.subtotals ?? [])
                .filter((s) => s.after_line_key == null)
                .map((s) => (
                  <SubtotalRow key={s.kind} subtotal={s} />
                ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** S48 rest (DV-a): code's subtotal rows (gross profit and operating expenses with a top rule,
 * net income with the double rule), dashes in the test, explanation and status cells. */
function SubtotalRow({ subtotal: s }: { subtotal: FluxSubtotalOut }): JSX.Element {
  const grand = s.kind === "net_income";
  return (
    <tr
      data-subtotal={s.kind}
      className={`h-[34px] font-medium ${
        grand ? "border-t-[3px] border-double border-ink" : "border-t-[0.5px] border-stroke"
      }`}
    >
      <td className="px-[12px] py-[8px] text-[12.5px]">{s.caption}</td>
      <td className="px-[8px] py-[8px] text-right tabular-nums">{whole(s.prior)}</td>
      <td className="px-[8px] py-[8px] text-right tabular-nums">{whole(s.current)}</td>
      <td
        className={`px-[8px] py-[8px] text-right tabular-nums ${negative(s.change) ? "text-red" : ""}`}
      >
        {whole(s.change)}
      </td>
      <td
        className={`px-[8px] py-[8px] text-right tabular-nums ${negative(s.change_pct) ? "text-red" : ""}`}
      >
        {percent(s.change_pct)}
      </td>
      <td className="px-[8px] py-[8px] text-ink-3">{DASH}</td>
      <td className="px-[8px] py-[8px] text-ink-3">{DASH}</td>
      <td className="px-[8px] py-[8px] text-ink-3">{DASH}</td>
      <td />
    </tr>
  );
}
