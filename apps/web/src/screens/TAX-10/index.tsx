// TAX-10 · Two-year comparison (T-08-T22; TASK-8936; docs/screens/TAX-10.md; handoff TAX-10 a–e,
// composed DF-04 x1; SPEC-710 AC-21 to AC-25; DEC-5938): the Feld 2025 Form 1040 against 2024 at
// `/tax-returns/$returnId/review/two-year` inside the review workspace, on `GET …/two-year`. Every
// figure, Δ, Δ%, flag and threshold is the server's (code's compare over the CPA line map); the
// browser formats only. An over-threshold line carries its explanation: amber while proposed or
// missing, green ✓ once a person accepts it. "Accept" shows only with the server's
// `two_year.accept` (the reviewer); "Edit" opens an inline editor (a new version); "Explain…"
// starts the agent's run and is replaced by the DF-04 line when the agent is off for this
// taxpayer, where Samuel Ito types the explanation. No explained variance reads red.
import type { TaxPracticeTwoYearLineOut, TaxPracticeTwoYearOut } from "@abacus/api-client";
import {
  twoYearAcceptMutation,
  twoYearExplainMutation,
  twoYearExplanationMutation,
  twoYearOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  Icon,
  Popover,
  Segmented,
  Skeleton,
  Spinner,
  StatusDisc,
  TallyStrip,
  Tag,
  amount,
  cn,
  pct,
  time,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

export interface TAX10Props {
  returnId: string;
  /** `?filter=over_threshold` (b). */
  filter?: "all" | "over_threshold";
  onFilter?: (filter: "all" | "over_threshold") => void;
  /** The review sheets' sub-navigation (DF-39): Worksheets, Leadsheets. */
  onSheet?: (sheet: (typeof C.sheets)[number]) => void;
}

const num = (v: string | null | undefined): string => (v == null ? DASH : amount(v, "whole").text);
const pctOf = (v: string | null | undefined): string =>
  // The server's percent (8.4) as the kit's ratio, negatives in parentheses.
  v == null ? DASH : pct(String(Number(v) / 100), { decimals: 1 });

function Explanation({
  returnId,
  line,
  data,
}: {
  returnId: string;
  line: TaxPracticeTwoYearLineOut;
  data: TaxPracticeTwoYearOut;
}): JSX.Element {
  const queries = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(line.explanation ?? "");
  const refresh = async (): Promise<void> => {
    await queries.invalidateQueries();
  };
  const accept = useMutation({ ...twoYearAcceptMutation(), onSuccess: refresh });
  const edit = useMutation({
    ...twoYearExplanationMutation(),
    onSuccess: async () => {
      setEditing(false);
      await refresh();
    },
  });
  const explain = useMutation({ ...twoYearExplainMutation(), onSuccess: refresh });
  const can = (a: string): boolean => (line.allowed_actions ?? []).includes(a);
  if (!line.flagged) {
    return (
      <span
        className="text-ink-3"
        title={line.below_reason === "below_amount" ? C.belowAmount : undefined}
      >
        {DASH}
      </span>
    );
  }
  if (editing) {
    return (
      <form
        className="flex flex-col gap-[4px]"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim() === "") return;
          edit.mutate({
            path: { return_id: returnId, line_key: line.line_key },
            body: { text: draft.trim() },
            headers: { "If-Match": line.values_hash },
          });
        }}
      >
        <textarea
          aria-label={C.editLabel(line.label)}
          rows={2}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
          }}
          className="rounded-nested bg-nested p-[6px] text-[12px] text-ink"
        />
        <span className="flex gap-[6px]">
          <Button size="sm" variant="primary" type="submit" disabled={draft.trim() === ""}>
            {C.save}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            type="button"
            onClick={() => {
              setEditing(false);
            }}
          >
            {C.cancel}
          </Button>
        </span>
      </form>
    );
  }
  if (line.state === "accepted") {
    return (
      <span
        className="flex items-start gap-[6px] text-[12px] text-ink-2"
        data-explained="accepted"
      >
        <StatusDisc state="done" size={13} />
        <span className="min-w-0 flex-1">
          {line.explanation}
          {(line.citations ?? []).map((c) => (
            <Tag key={c.citation_id} className="ml-[6px]">
              {c.label}
            </Tag>
          ))}
          <span className="block text-[11.5px] text-ink-3">
            {C.acceptedBy(
              line.accepted_by_initials ?? DASH,
              line.line_key === "scha.11" && line.accepted_at != null
                ? time(line.accepted_at)
                : null,
            )}
          </span>
        </span>
      </span>
    );
  }
  const explainingNow = data.explaining === true && line.state === "unexplained";
  return (
    <span
      data-explained={line.state ?? "unexplained"}
      className="flex items-start gap-[6px] rounded-[6px] bg-amber-tint px-[6px] py-[4px] text-[12px] text-amber-ink"
    >
      <Icon name="triangle-alert" size={12} />
      <span className="min-w-0 flex-1">
        {explainingNow ? (
          <span className="flex items-center gap-[6px]">
            <Spinner size={12} label={C.explaining} showLabel />
            <Skeleton className="h-[10px] w-[160px]" />
          </span>
        ) : line.state === "proposed" ? (
          <>
            <span className="text-ink-2">{line.explanation}</span>
            {(line.citations ?? []).map((c) => (
              <Tag key={c.citation_id} className="ml-[6px]">
                {c.label}
              </Tag>
            ))}
          </>
        ) : data.explain_unavailable_reason != null ? (
          <span>{C.agentsOff[data.explain_unavailable_reason] ?? C.unexplained}</span>
        ) : (
          <span>{C.unexplained}</span>
        )}
      </span>
      <span className="flex flex-none gap-[4px]">
        {line.state === "proposed" &&
        can("two_year.accept") &&
        line.explanation_version_id != null ? (
          <Button
            size="sm"
            variant="primary"
            disabled={accept.isPending}
            onClick={() => {
              accept.mutate({
                path: { return_id: returnId, line_key: line.line_key },
                body: {
                  explanation_version_id: line.explanation_version_id ?? "",
                  values_hash: line.values_hash,
                },
                headers: {
                  "Idempotency-Key": `tax10-accept-${line.explanation_version_id ?? ""}`,
                },
              });
            }}
          >
            {C.accept}
          </Button>
        ) : null}
        {line.state === "unexplained" && data.explain_available && !explainingNow ? (
          <Button
            size="sm"
            variant="secondary"
            disabled={explain.isPending}
            onClick={() => {
              explain.mutate({
                path: { return_id: returnId },
                body: { line_keys: [line.line_key] },
                headers: { "Idempotency-Key": `tax10-explain-${line.line_key}` },
              });
            }}
          >
            {C.explain}
          </Button>
        ) : null}
        {can("two_year.edit") && !explainingNow ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setDraft(line.explanation ?? "");
              setEditing(true);
            }}
          >
            {C.edit}
          </Button>
        ) : null}
      </span>
    </span>
  );
}

export function TAX10({ returnId, filter = "all", onFilter, onSheet }: TAX10Props): JSX.Element {
  const [shown, setShown] = useState(filter);
  const read = useQuery(
    twoYearOptions({ path: { return_id: returnId }, query: { filter: shown } }),
  );
  const data = read.data;
  if (read.isError) {
    return (
      <div data-screen="TAX-10" role="alert" className="p-[16px] text-[13px]">
        {C.failed}{" "}
        <Button size="sm" variant="secondary" onClick={() => void read.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  if (data === undefined) {
    return (
      <div data-screen="TAX-10" aria-busy="true" className="p-[12px]">
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  const t = data.threshold;
  const thresholdAmount = amount(t.amount, "dollars").text;
  const groups = ["income", "deductions", "tax_and_payments"] as const;
  return (
    <div data-screen="TAX-10" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={C.sheetsLabel}
          options={[...C.sheets]}
          active={C.active}
          onChange={(label) => {
            onSheet?.(label as (typeof C.sheets)[number]);
          }}
        />
        <Segmented
          size="small"
          label={C.filterLabel}
          options={[C.all, { label: C.over, count: data.over_threshold }]}
          active={shown === "over_threshold" ? C.over : C.all}
          onChange={(label) => {
            const next = label === C.over ? "over_threshold" : "all";
            setShown(next);
            onFilter?.(next);
          }}
        />
        <h2 className="flex-1 text-center text-[14.5px] font-medium">{C.title}</h2>
        <Button
          variant="ghost"
          size="sm"
          icon="file-spreadsheet"
          onClick={() => {
            window.open(`/v1/tax-returns/${returnId}/two-year.xlsx`, "_blank", "noopener");
          }}
        >
          {C.openInExcel}
        </Button>
        <Popover
          trigger={
            <button
              type="button"
              data-tax10="threshold"
              className="inline-flex h-[28px] items-center gap-[6px] rounded-pill bg-card px-[10px] text-[12px] shadow-e1"
            >
              <span className="text-ink-3">{C.threshold}</span>
              <span>{C.thresholdValue(thresholdAmount, String(Number(t.percent)))}</span>
              <Icon name="info" size={12} />
            </button>
          }
        >
          <p className="max-w-[260px] p-[10px] text-[12px]">
            {C.thresholdPopover(t.source_label, thresholdAmount, String(Number(t.percent)))}
          </p>
        </Popover>
      </div>
      <TallyStrip
        label={C.tally}
        className="flex-none px-[12px] pb-[10px]"
        items={[
          {
            label: C.agi,
            value: `${num(data.agi)} (${pctOf(data.agi_delta_pct).replace(/^(?!\()/u, "+")})`,
          },
          {
            label: C.totalTax,
            value: `${num(data.total_tax)} (${pctOf(data.total_tax_delta_pct).replace(/^(?!\()/u, "+")})`,
          },
          {
            label: C.refund,
            value: `${num(data.refund)} ${C.refundPrior(num(data.prior_refund))}`,
          },
          { label: C.overThreshold, value: String(data.over_threshold) },
          { label: C.accepted, value: C.acceptedValue(data.accepted, data.over_threshold) },
        ]}
      />
      <section
        aria-label={C.pane}
        className="mx-[12px] mb-[12px] min-h-0 flex-1 overflow-auto rounded-pane bg-card shadow-e1"
      >
        <h3 className="flex h-[46px] items-center justify-center text-[14px] font-medium">
          {C.pane}
        </h3>
        <table className="w-full border-collapse text-[12px]" data-tax10="statement">
          <colgroup>
            {[340, 110, 110, 100, 70, undefined, 96].map((w, i) => (
              <col key={i} style={w === undefined ? undefined : { width: w }} />
            ))}
          </colgroup>
          <thead>
            <tr className="h-[30px] bg-band-hd text-[11.5px] font-medium text-ink-3">
              {C.columns.map((h, i) => (
                <th
                  key={`${h}${String(i)}`}
                  scope="col"
                  className={cn("px-[10px]", i === 0 || i === 5 ? "text-left" : "text-right")}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          {groups.map((g) => {
            const rows = data.lines.filter((l) => l.group === g);
            if (rows.length === 0) return null;
            return (
              <tbody key={g}>
                <tr className="h-[24px]">
                  <th
                    colSpan={7}
                    scope="rowgroup"
                    className="px-[10px] text-left text-[10px] font-medium tracking-[0.07em] text-ink-3 uppercase"
                  >
                    {C.groups[g]}
                  </th>
                </tr>
                {rows.map((l) => (
                  <tr
                    key={l.line_key}
                    data-line={l.line_key}
                    data-total={l.total ?? undefined}
                    className={cn(
                      "min-h-[26px] align-top",
                      l.total === "total" && "border-t-[0.5px] border-ink font-medium",
                      l.total === "grand" && "border-t-[3px] border-double border-ink font-medium",
                    )}
                  >
                    <td className="px-[10px] py-[5px]">{l.label}</td>
                    <td className="px-[10px] py-[5px] text-right tabular-nums">{num(l.prior)}</td>
                    <td className="px-[10px] py-[5px] text-right tabular-nums">
                      {num(l.current)}
                    </td>
                    <td
                      className={cn(
                        "px-[10px] py-[5px] text-right tabular-nums",
                        !l.flagged && "text-ink-3",
                      )}
                    >
                      {num(l.delta)}
                    </td>
                    <td
                      className={cn(
                        "px-[10px] py-[5px] text-right tabular-nums",
                        !l.flagged && "text-ink-3",
                      )}
                      title={l.below_reason === "below_amount" ? C.belowAmount : undefined}
                    >
                      {pctOf(l.delta_pct)}
                    </td>
                    <td className="px-[10px] py-[5px]" colSpan={2}>
                      <Explanation returnId={returnId} line={l} data={data} />
                    </td>
                  </tr>
                ))}
              </tbody>
            );
          })}
        </table>
      </section>
    </div>
  );
}
