import type { ReferenceSetOut, ReferenceSetVersionOut } from "@abacus/api-client";
import { listReferenceSetsOptions, resolveReferenceSetOptions } from "@abacus/api-client/query";
import {
  ErrorState,
  Fieldset,
  FieldsetEmpty,
  FlagOffState,
  RegistryStatus,
  Skeleton,
  amount,
  cn,
  date,
} from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { DEADLINE_COPY as C } from "./deadline-copy";

// KNW-04 j · Deadline rules (K-02-T17; DF-10, composed from the T12 grammar; docs/screens/KNW-04.md
// j; K-02 F6 US-6.1): the platform reference sets (C21) behind `rules.reference_sets`, one
// fieldset per set resolved as of today: due-date rules, legal holidays, disaster postponements,
// the 8879 form set with the Pub 1345 tolerances, information-return thresholds and retention
// minimums. Each header names the set's version, its effective date and its status; its footer
// cites the source. Read-only for every firm role: no control here edits, drafts or publishes
// (the platform publishes under a two-person rule; firm overrides are T-03's). The browser only
// formats what the server resolved; it computes no date.

type Payload = ReferenceSetVersionOut["payload"];

/** A fieldset table on hairlines: the #EFEEEB head row, then 34 rows (the T12 grammar). */
function Table({
  label,
  head,
  cols,
  rows,
  right = [],
}: {
  label: string;
  head: readonly string[];
  cols: string;
  rows: readonly { key: string; cells: readonly ReactNode[] }[];
  right?: readonly number[];
}): JSX.Element {
  return (
    <div role="table" aria-label={label}>
      <div role="rowgroup">
        <div
          role="row"
          className="grid min-h-[30px] items-center gap-[12px] border-b-[0.5px] border-hair bg-nested px-[12px] text-th text-ink-2"
          style={{ gridTemplateColumns: cols }}
        >
          {head.map((h, i) => (
            <span key={h} role="columnheader" className={cn(right.includes(i) && "text-right")}>
              {h}
            </span>
          ))}
        </div>
      </div>
      <div role="rowgroup">
        {rows.map((r) => (
          <div
            key={r.key}
            role="row"
            className="grid min-h-[34px] items-center gap-[12px] border-b-[0.5px] border-hair px-[12px] py-[6px] text-body last:border-b-0"
            style={{ gridTemplateColumns: cols }}
          >
            {r.cells.map((cell, i) => (
              <span
                key={i}
                role="cell"
                className={cn("min-w-0", right.includes(i) && "text-right tabular-nums")}
              >
                {cell}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

const usd = (n: number): string => `$${amount(String(n), "whole").text}`;

function Rows({ payload, label, now }: { payload: Payload; label: string; now: number }) {
  const k = C.columns;
  const day = (iso: string): string => date(iso, { now, withYear: true });
  switch (payload.kind) {
    case "due_date_rules":
      return (
        <Table
          label={label}
          head={[k.form, k.period, k.original, k.extension, k.authority]}
          cols="80px 120px minmax(0,1fr) minmax(0,1fr) 120px"
          rows={payload.rows.map((r) => ({
            key: `${r.form}:${r.fye_rule}`,
            cells: [
              r.form,
              C.fyeRule[r.fye_rule] ?? r.fye_rule,
              C.original(r.original.months_after_period_end, r.original.day),
              r.extension === null
                ? C.none
                : C.extension(r.extension.form, r.extension.months, r.extension.day ?? null),
              r.authority,
            ],
          }))}
        />
      );
    case "legal_holidays":
      return (
        <Table
          label={label}
          head={[k.date, k.name, k.jurisdiction]}
          cols="140px minmax(0,1fr) 110px"
          rows={payload.rows.map((r) => ({
            key: r.date + r.jurisdiction,
            cells: [day(r.date), r.name, r.jurisdiction],
          }))}
        />
      );
    case "disaster_postponements":
      return payload.rows.length === 0 ? (
        <FieldsetEmpty>{C.empty}</FieldsetEmpty>
      ) : (
        <Table
          label={label}
          head={[k.notice, k.areas, k.window, k.postponedTo]}
          cols="120px minmax(0,1fr) 220px 130px"
          rows={payload.rows.map((r) => ({
            key: r.notice_id,
            cells: [
              r.notice_id,
              r.areas.map((a) => a.state_code).join(", "),
              `${day(r.window.start)} – ${day(r.window.end)}`,
              day(r.postponed_to),
            ],
          }))}
        />
      );
    case "form_8879_set":
      return (
        <>
          <Table
            label={label}
            head={[k.returnType, k.authorization, k.revision, k.jurisdiction]}
            cols="120px minmax(0,1fr) 120px 110px"
            rows={payload.rows.map((r) => ({
              key: `${r.return_type}:${r.jurisdiction}`,
              cells: [r.return_type, r.authorization_form, r.revision, r.jurisdiction],
            }))}
          />
          <Table
            label={C.tolerances}
            head={[C.tolerances, k.threshold]}
            cols="minmax(0,1fr) 120px"
            right={[1]}
            rows={[
              { key: "agi", cells: [C.agi, usd(payload.tolerances.total_income_or_agi_usd)] },
              {
                key: "tax",
                cells: [C.tax, usd(payload.tolerances.tax_withholding_refund_balance_usd)],
              },
            ]}
          />
        </>
      );
    case "information_return_thresholds":
      return (
        <Table
          label={label}
          head={[k.form, k.threshold, k.transactions]}
          cols="minmax(0,1fr) 140px 140px"
          right={[1, 2]}
          rows={payload.rows.map((r) => ({
            key: `${r.form}:${String(r.payment_year)}`,
            cells: [
              r.form,
              usd(r.threshold_usd),
              r.min_transactions === null ? C.none : String(r.min_transactions),
            ],
          }))}
        />
      );
    case "retention_minimums":
      return (
        <Table
          label={label}
          head={[k.serviceLine, k.record, k.floor, k.anchor, k.authority]}
          cols="100px minmax(0,1fr) 90px minmax(0,1fr) 200px"
          rows={payload.rows.map((r) => ({
            key: `${r.service_line}:${r.record_type}`,
            cells: [r.service_line, r.record_type, C.years(r.floor_years), r.anchor, r.authority],
          }))}
        />
      );
    case "standards_sets":
      return null;
  }
}

function SetFieldset({
  set,
  version,
  now,
}: {
  set: ReferenceSetOut;
  version: ReferenceSetVersionOut;
  now: number;
}): JSX.Element {
  const effective = date(version.effective_from, { now, withYear: true });
  return (
    <div data-reference-set={set.key} data-kind={set.kind}>
      <Fieldset
        flush
        title={set.title}
        action={
          <span className="flex items-center gap-[8px] text-meta text-ink-3">
            <span
              data-version-chip=""
              className="rounded-full bg-chip px-[7px] py-[1px] text-pill-sm text-ink-2"
            >
              {C.version(version.version)}
            </span>
            {version.tax_year !== null && <span>{C.taxYear(version.tax_year)}</span>}
            <span data-effective="">{C.effective(effective)}</span>
            <RegistryStatus object="reference_set_version" code={version.status} />
          </span>
        }
      >
        <Rows payload={version.payload} label={set.title} now={now} />
        <p data-source="" className="px-[12px] pt-[8px] pb-[10px] text-meta text-ink-3">
          {version.source_citations.map((s) => C.source(s.label)).join(" · ")}
        </p>
      </Fieldset>
    </div>
  );
}

const KIND_ORDER: readonly ReferenceSetOut["kind"][] = [
  "due_date_rules",
  "legal_holidays",
  "disaster_postponements",
  "form_8879_set",
  "information_return_thresholds",
  "retention_minimums",
];

export function DeadlineRulesSection(): JSX.Element {
  const on = useFlag("rules.reference_sets") === true;
  const now = useNow();
  const asOf = now.toISOString().slice(0, 10);
  const list = useQuery({ ...listReferenceSetsOptions(), enabled: on });
  const sets = (list.data?.items ?? [])
    .filter((s) => KIND_ORDER.includes(s.kind))
    .sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  const resolved = useQueries({
    queries: sets.map((s) => ({
      ...resolveReferenceSetOptions({ path: { key: s.key }, query: { as_of: asOf } }),
      enabled: on,
    })),
  });
  if (!on) {
    return <FlagOffState flag="rules.reference_sets" label={C.flagLabel} icon="calendar-clock" />;
  }
  if (list.isError || resolved.some((r) => r.isError)) {
    return (
      <ErrorState
        title={C.error}
        retryLabel={C.retry}
        onRetry={() => {
          void list.refetch();
          for (const r of resolved) void r.refetch();
        }}
      />
    );
  }
  if (list.isPending || resolved.some((r) => r.isPending)) {
    return (
      <div aria-busy="true" aria-label={C.loading} className="flex flex-col gap-[10px]">
        <Skeleton className="h-[160px]" />
        <Skeleton className="h-[90px]" />
      </div>
    );
  }
  return (
    <div data-deadline-rules="" className="flex flex-col">
      <p className="mb-[10px] max-w-[760px] text-dense text-ink-2">{C.helper}</p>
      {sets.map((s, i) => {
        const data = resolved[i]?.data;
        return data === undefined ? null : (
          <SetFieldset key={s.key} set={s} version={data.version} now={now.getTime()} />
        );
      })}
    </div>
  );
}
