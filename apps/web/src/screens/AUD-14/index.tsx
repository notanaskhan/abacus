import type { ConfirmationCoverageOut, ConfirmationDetailOut } from "@abacus/api-client";
import {
  Amount,
  Button,
  amount,
  DASH,
  FilterChip,
  RegistryStatus,
  SearchField,
  StatusTile,
  type StatusTileVariant,
  cn,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { ConfirmationDrawer, NewConfirmationSheet } from "../../domain/fieldwork";
import {
  ALPINE_RIDGE_DETAIL,
  ALPINE_RIDGE_WHY,
  type ConfirmationLogRow,
  GRANITE_PEAK_CONFIRMATIONS,
  GRANITE_PEAK_COVERAGE,
} from "../kit-a08-data";
import { AUD14_COPY as C } from "./copy";
import { AUD14_SCENARIOS, type Aud14Scenario } from "./scenarios";

// AUD-14 Confirmations (A-08-T29; SPEC-657 F7; handoff AUD-14 a to e) on T1 in fixture mode:
// filter chips, status tiles as filters, the coverage line, the grouped bank row, the drawer
// (Response, Reconciliation, Classification, Why this was surfaced) and the new confirmation
// sheet with its address gate. Accept reconciliation renders only for the manager (the server's
// `allowed_actions`; the agent never accepts, ADR-005). Nothing here is client-visible.

type Status = ConfirmationLogRow["status"];
/** The viewer's grants, as the server's `allowed_actions` answer them (Simone holds none here). */
const MANAGER_GRANTS = ["confirmation.accept_reconciliation"] as const;

const STATUSES: readonly { code: Status; label: string; variant: StatusTileVariant }[] = [
  { code: "draft", label: "Draft", variant: "neutral" },
  { code: "authorization_requested", label: "Authorization requested", variant: "amber" },
  { code: "sent", label: "Sent", variant: "state" },
  { code: "responded", label: "Responded", variant: "green-tint" },
  { code: "exception", label: "Exception", variant: "red-tint" },
  { code: "alternative_procedures", label: "Alternative procedures", variant: "amber" },
  { code: "closed", label: "Closed", variant: "green" },
];

/** The log as each artboard's data condition holds it (b, c: before responses; d: C3 closed). */
function rowsFor(scenario: Aud14Scenario): ConfirmationLogRow[] {
  return GRANITE_PEAK_CONFIRMATIONS.map((row): ConfirmationLogRow => {
    const unanswered = {
      ...row,
      response: "",
      confirmed: null,
      difference: null,
      lines: row.lines?.map((l) => ({ ...l, confirmed: "", difference: "" })),
    } as ConfirmationLogRow;
    if (scenario === "b") {
      const waiting = row.number === "C1";
      return {
        ...unanswered,
        sent: "",
        status: waiting ? "authorization_requested" : "draft",
        ...(waiting ? { subLine: C.waitingOn } : {}),
      };
    }
    if (scenario === "c") {
      return {
        ...unanswered,
        status: "sent",
        ...(row.number === "C1" ? {} : { subLine: C.viewed }),
      };
    }
    if (scenario === "d" && row.number === "C3") return { ...row, status: "closed" };
    return row;
  });
}

function detailFor(grants: readonly string[]): ConfirmationDetailOut {
  const allowed = ALPINE_RIDGE_DETAIL.row.allowed_actions.filter(
    (a) => a !== "confirmation.accept_reconciliation" || grants.includes(a),
  );
  return { ...ALPINE_RIDGE_DETAIL, row: { ...ALPINE_RIDGE_DETAIL.row, allowed_actions: allowed } };
}

const TH = "h-[30px] bg-nested px-[8px] text-[12.5px] font-normal text-ink-2";
const TD = "h-[40px] px-[8px] text-cell";

function Money({ value }: { value: string | null | undefined }): JSX.Element {
  if (value === null || value === undefined || value === "") {
    return <span className="text-ink-3">{DASH}</span>;
  }
  return <Amount value={value} style="money" zero="explicit" />;
}

function LogTable({
  rows,
  selected,
  onSelect,
  onBook,
}: {
  rows: readonly ConfirmationLogRow[];
  selected: string | null;
  onSelect: (number: string) => void;
  /** Book amount → SHL-09, where the balance comes from (the live host's; fixture: none). */
  onBook?: ((number: string) => void) | undefined;
}): JSX.Element {
  return (
    <table className="w-full border-collapse" data-aud14="log">
      <caption className="sr-only">{C.title}</caption>
      <thead>
        <tr className="hairline-b">
          {C.columns.map((h, i) => (
            <th
              key={h}
              scope="col"
              className={cn(TH, i >= 7 && i <= 9 ? "text-right" : "text-left")}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.flatMap((r) => {
          const out: JSX.Element[] = [
            <tr
              key={r.number}
              data-confirmation={r.number}
              data-status={r.status}
              aria-selected={selected === r.number}
              className={cn("hairline-b", selected === r.number && "bg-selected")}
              onClick={() => {
                onSelect(r.number);
              }}
            >
              <td className={TD}>{r.number}</td>
              <td className={cn(TD, r.lines !== undefined && "font-medium")}>{r.item}</td>
              <td className={TD}>{r.respondent}</td>
              <td className={cn(TD, "max-w-[200px] truncate")} title={r.address}>
                {r.address}
              </td>
              <td className={TD}>{r.channel}</td>
              <td className={TD}>{r.sent === "" ? DASH : r.sent}</td>
              <td className={cn(TD, r.response === "No response" && "text-ink-3")}>
                {r.response === "" ? DASH : r.response}
                {r.number === "C4" && r.response === "No response" && (
                  <span className="block text-[11.5px] text-ink-3">{C.secondRequest}</span>
                )}
              </td>
              <td className={cn(TD, "text-right")}>
                {r.lines === undefined &&
                  (onBook === undefined ? (
                    <Money value={r.book} />
                  ) : (
                    <button
                      type="button"
                      data-aud14="book"
                      className="hover:underline"
                      onClick={(e) => {
                        e.stopPropagation();
                        onBook(r.number);
                      }}
                    >
                      <Money value={r.book} />
                    </button>
                  ))}
              </td>
              <td className={cn(TD, "text-right")}>
                {r.lines === undefined && <Money value={r.confirmed} />}
              </td>
              <td
                className={cn(
                  TD,
                  "text-right",
                  r.difference !== null && r.difference !== "0.00" && "font-medium text-amber-ink",
                )}
              >
                {r.lines === undefined && <Money value={r.difference} />}
              </td>
              <td className={TD}>
                <RegistryStatus object="confirmation" code={r.status} />
                {r.subLine !== undefined && (
                  <span data-subline="" className="block text-[11.5px] text-ink-3">
                    {r.subLine}
                  </span>
                )}
              </td>
            </tr>,
          ];
          for (const l of r.lines ?? []) {
            out.push(
              <tr
                key={`${r.number}-${l.account}`}
                data-account-line={l.account}
                className="hairline-b"
              >
                <td className={TD} />
                <td className={cn(TD, "pl-[25px]")} colSpan={6}>
                  {l.account}
                </td>
                <td className={cn(TD, "text-right")}>
                  <Money value={l.book} />
                </td>
                <td className={cn(TD, "text-right")}>
                  <Money value={l.confirmed} />
                </td>
                <td className={cn(TD, "text-right")}>
                  <Money value={l.difference} />
                </td>
                <td className={TD} />
              </tr>,
            );
          }
          return out;
        })}
      </tbody>
    </table>
  );
}

export { MANAGER_GRANTS };

/** A-08-T32 (DEC-5530): the live host's reads (live.tsx), in place of the fixture's seed rows. */
export interface ConfirmationsData {
  rows: readonly ConfirmationLogRow[];
  coverage: ConfirmationCoverageOut | null;
  /** The open row's drawer detail, once read; `selected` names the row. */
  detail: ConfirmationDetailOut | undefined;
  selected: string | null;
  onSelect: (number: string | null) => void;
  onBook?: ((number: string) => void) | undefined;
}

export function ConfirmationsWorkspace({
  st,
  grants = [],
  data,
}: {
  st?: string | undefined;
  /** Fixture: the viewer's grants (`MANAGER_GRANTS` for Hannah Leclerc). */
  grants?: readonly string[];
  data?: ConfirmationsData | undefined;
}): JSX.Element {
  const scenario: Aud14Scenario = (AUD14_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud14Scenario)
    : "a";
  const rows = data?.rows ?? rowsFor(scenario);
  const [filter, setFilter] = useState<Status | null>(null);
  const [fixtureDrawer, setFixtureDrawer] = useState(data === undefined && scenario === "a");
  const [sheet, setSheet] = useState(data === undefined && scenario === "e");
  const shown = filter === null ? rows : rows.filter((r) => r.status === filter);
  const v = data === undefined ? GRANITE_PEAK_COVERAGE : data.coverage;
  const drawer = data === undefined ? fixtureDrawer : data.selected !== null;
  const setDrawer = (open: boolean): void => {
    if (data === undefined) setFixtureDrawer(open);
    else if (!open) data.onSelect(null);
  };
  const detail = data === undefined ? detailFor(grants) : data.detail;
  const money = (s: string): string => amount(s, "money").text;
  return (
    <div
      data-screen="AUD-14"
      data-scenario={scenario}
      className="flex flex-col gap-[10px] bg-shell p-[12px]"
    >
      <div className="flex h-[50px] items-center gap-[8px]">
        {(["type", "respondent", "status", "channel"] as const).map((k) => (
          <FilterChip key={k} label={C.filters[k]} options={[]} placeholder={C.filters.all} />
        ))}
        <span className="flex-1" />
        <Button variant="ghost">{C.back}</Button>
      </div>
      <div className="flex items-center gap-[8px]" role="group" aria-label={C.tilesLabel}>
        {STATUSES.map((s) => (
          <StatusTile
            key={s.code}
            count={rows.filter((r) => r.status === s.code).length}
            label={s.label}
            variant={s.variant}
            selected={filter === s.code}
            onSelect={() => {
              setFilter((f) => (f === s.code ? null : s.code));
            }}
          />
        ))}
        {v !== null && (
          <p data-aud14="coverage" className="ml-[8px] text-[12.5px] text-ink-3">
            {C.coverage(
              money(v.sent_total),
              money(v.population_total),
              v.sent_pct,
              money(v.confirmed_total),
              money(v.differences_total),
              amount(v.clearly_trivial, "dollars").text,
            )}
          </p>
        )}
      </div>
      <section aria-label={C.title} className="rounded-pane bg-card shadow-e1">
        <header className="flex h-[46px] items-center justify-between px-[12px]">
          <span className="w-[220px]">
            <SearchField label={C.search} />
          </span>
          <h1 className="text-[14px] font-medium">{C.title}</h1>
          <Button
            variant="primary"
            onClick={() => {
              setSheet(true);
            }}
          >
            {C.newConfirmation}
          </Button>
        </header>
        <LogTable
          rows={shown}
          selected={data === undefined ? (drawer ? "C3" : null) : data.selected}
          onSelect={(n) => {
            if (data !== undefined) data.onSelect(n);
            else if (n === "C3") setDrawer(true);
          }}
          onBook={data?.onBook}
        />
        <footer
          data-aud14="client-note"
          className="flex h-[36px] items-center bg-nested px-[12px] text-[12px] text-ink-3 hairline-t"
        >
          {C.clientNote}
        </footer>
      </section>
      {(data === undefined ? scenario !== "d" : detail !== undefined) && detail !== undefined && (
        <ConfirmationDrawer
          open={drawer}
          onOpenChange={setDrawer}
          detail={detail}
          why={data === undefined ? ALPINE_RIDGE_WHY : undefined}
          held={data === undefined && scenario === "a"}
        />
      )}
      <NewConfirmationSheet
        open={sheet}
        onOpenChange={setSheet}
        held={scenario === "e"}
        {...(scenario === "e"
          ? {
              initial: {
                respondentOrg: "Cascade Peak Outfitters",
                address: "ap@cascadepeak.example",
                method: "From the client's AR listing",
                sources: ["client_supplied" as const],
              },
            }
          : {})}
      />
    </div>
  );
}
