import type { CertificationPointOut, InvestmentRowOut, InvestmentsOut } from "@abacus/api-client";
import { ebpCertificationMutation, ebpInvestmentsOptions } from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Button,
  MATCH_CELL,
  PaneAction,
  Pill,
  Segmented,
  Skeleton,
  amount,
  cn,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-06 · Investments, certification & trust tie-out (A-05-T40; A-05 §3 F6; the handoff spec): the
// Fieldwork › Investments & Certification canvas in the T2 cockpit with the viewer dock. Every figure
// is the server's (A-05-T39), complete and never truncated. ✓ MS means agreed to a certified source;
// notes receivable carry an ink-3 ✓ only (agreed to the loan report, not certified). Only a person
// evaluates a point, and sign-off is disabled with the hold reason while any point is open.

export const INVESTMENTS = "ebp_06";
const FLAG = "ebp.modules";
type Layer = keyof typeof COPY.layers;
const LAYERS: readonly Layer[] = ["unadjusted", "aje", "rje", "final"];

const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? "" : amount(v, "cents", { zero: "explicit" }).text;

export interface InvestmentsOptions {
  active?: boolean;
  layer?: Layer;
  onLayer?: (layer: Layer) => void;
  /** A row lit: the viewer's linked row follows. */
  selected?: string | null;
  onSelect?: (key: string) => void;
  /** Run in progress: ✓ MS pills arrive row by row as results land. */
  running?: boolean;
  onSignOff?: () => void;
  onSourceDocs?: () => void;
  signedInitials?: string | null;
}

function Row({
  row,
  selected,
  onSelect,
}: {
  row: InvestmentRowOut;
  selected: boolean;
  onSelect?: (key: string) => void;
}): JSX.Element {
  // The spec's click: the cell lights in the match colour, once at a time on this row.
  const [litCell, setLitCell] = useState<"boy" | "eoy" | null>(null);
  const certified = row.level === "level1" || row.level === "nav";
  const mark = row.ties === true ? (certified ? COPY.ms : COPY.tick) : null;
  return (
    <tr
      data-row={row.key}
      data-level={row.level}
      {...(selected ? { "data-lit": "" } : {})}
      onClick={() => onSelect?.(row.key)}
      className={cn("h-[29px] cursor-pointer text-[12px] hairline-t", selected && "bg-selected")}
    >
      <td className="px-[12px]">{row.label}</td>
      {[row.trust_boy ?? row.tb_boy, row.trust_eoy ?? row.tb_eoy].map((value, i) => (
        <td
          key={i === 0 ? "boy" : "eoy"}
          {...(litCell === (i === 0 ? "boy" : "eoy") ? { "data-lit": "" } : {})}
          onClick={() => {
            setLitCell(i === 0 ? "boy" : "eoy");
          }}
          className={cn("pr-[8px] text-right tabular-nums whitespace-nowrap", MATCH_CELL)}
        >
          {money(value)}
          {mark !== null && (
            <span
              data-mark={certified ? "ms" : "tick"}
              className={cn(
                "ml-[6px] text-[10.5px]",
                certified ? "font-medium text-green" : "text-ink-3",
              )}
            >
              {mark}
            </span>
          )}
        </td>
      ))}
      <td className="px-[8px] text-[11.5px] text-ink-3">
        {row.level === "other" ? COPY.refs.tb : COPY.refs.trust}
      </td>
    </tr>
  );
}

function Certification({
  points,
  levels,
  workItemId,
}: {
  points: readonly CertificationPointOut[];
  levels: string;
  workItemId: string;
}): JSX.Element {
  const client = useQueryClient();
  const evaluate = useMutation({
    ...ebpCertificationMutation(),
    onSuccess: () => void client.invalidateQueries(),
  });
  return (
    <section
      data-ebp06="certification"
      className="m-[12px] overflow-hidden rounded-[12px] bg-card shadow-e1"
    >
      <h4 className="flex h-[32px] items-center px-[12px] text-[13px] font-medium hairline-b">
        {COPY.certification.title}
      </h4>
      {points.map((point) => (
        <div
          key={point.key}
          data-point={point.key}
          data-answer={point.answer}
          className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-[12px] hairline-b"
        >
          <span className="w-[140px] shrink-0 text-ink-2">
            {COPY.certification.points[point.key] ?? point.key}
          </span>
          <span className="flex-1">{point.proposed_answer ?? ""}</span>
          {point.answer === "evaluated" ? (
            <span
              role="img"
              aria-label={COPY.certification.evaluated}
              className="size-[15px] rounded-full bg-green"
            />
          ) : (
            <Button
              size="xs"
              variant="secondary"
              disabled={evaluate.isPending}
              onClick={() => {
                evaluate.mutate({
                  path: { work_item_id: workItemId, point_key: point.key },
                  body: { answer: "evaluated", note: point.proposed_answer ?? point.key },
                  headers: { "Idempotency-Key": crypto.randomUUID() },
                });
              }}
            >
              {COPY.certification.evaluate}
            </Button>
          )}
        </div>
      ))}
      <div className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-[12px]">
        <span className="w-[140px] shrink-0 text-ink-2">{COPY.certification.levels}</span>
        <span data-ebp06="levels" className="tabular-nums">
          {levels}
        </span>
      </div>
    </section>
  );
}

function Table({
  view,
  selected,
  onSelect,
}: {
  view: InvestmentsOut;
  selected: string | null;
  onSelect?: (key: string) => void;
}): JSX.Element {
  const invested = view.rows.filter((r) => r.level === "level1" || r.level === "nav");
  // The server's own split: a line that isn't a fund or CIT follows the subtotal, by its key.
  const brokerage = invested.filter((r) => /^(broker|sdba)/u.test(r.key));
  const funds = invested.filter((r) => !brokerage.includes(r));
  const below = view.rows.filter((r) => r.level === "not_certified" || r.level === "other");
  const rowProps = onSelect === undefined ? {} : { onSelect };
  return (
    <table data-ebp06="table" className="w-full">
      <thead>
        <tr className="h-[28px] bg-band-hd text-[11.5px] font-normal text-ink-2">
          <th className="px-[12px] text-left font-normal">{COPY.columns.description}</th>
          <th className="pr-[8px] text-right font-normal">{COPY.columns.boy}</th>
          <th className="pr-[8px] text-right font-normal">{COPY.columns.eoy}</th>
          <th className="px-[8px] text-left font-normal">{COPY.columns.ref}</th>
        </tr>
      </thead>
      <tbody>
        <tr className="h-[29px] text-[12px] font-medium hairline-t">
          <td colSpan={4} className="px-[12px]">
            {COPY.assets}
          </td>
        </tr>
        <tr className="h-[29px] text-[12px] font-medium hairline-t">
          <td colSpan={4} className="px-[12px]">
            {COPY.investments}
          </td>
        </tr>
        <tr className="h-[29px] text-[12px] font-medium hairline-t">
          <td colSpan={4} className="px-[20px]">
            {COPY.funds}
          </td>
        </tr>
        {funds.map((row) => (
          <Row key={row.key} row={row} selected={selected === row.key} {...rowProps} />
        ))}
        <tr data-row="funds_total" className="h-[29px] text-[12px] font-medium hairline-t">
          <td className="px-[12px]">{COPY.fundsTotal}</td>
          <td className="pr-[8px] text-right tabular-nums">{money(view.funds_boy)}</td>
          <td className="pr-[8px] text-right tabular-nums">{money(view.funds_eoy)}</td>
          <td className="px-[8px] text-[11.5px] font-normal text-ink-3">{COPY.refs.tb}</td>
        </tr>
        {brokerage.map((row) => (
          <Row key={row.key} row={row} selected={selected === row.key} {...rowProps} />
        ))}
        <tr data-row="total" className="h-[29px] text-[12px] font-medium hairline-t">
          <td className="px-[12px]">{COPY.total}</td>
          <td className="pr-[8px] text-right tabular-nums">{money(view.investments_boy)}</td>
          <td className="pr-[8px] text-right tabular-nums">{money(view.investments_eoy)}</td>
          <td className="px-[8px] text-[11.5px] font-normal text-ink-3">{COPY.refs.trust}</td>
        </tr>
        {below.map((row) => (
          <Row key={row.key} row={row} selected={selected === row.key} {...rowProps} />
        ))}
        <tr
          data-row="net_assets"
          className="h-[29px] border-t-[3px] border-double border-ink text-[12px] font-medium"
        >
          <td className="px-[12px]">{COPY.netAssets}</td>
          <td />
          <td className="pr-[8px] text-right tabular-nums">{money(view.net_assets)}</td>
          <td className="px-[8px] text-[11.5px] font-normal text-ink-3">{COPY.refs.tb}</td>
        </tr>
      </tbody>
    </table>
  );
}

export function useInvestmentsCanvas(
  workItemId: string,
  options: InvestmentsOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const layer = options.layer ?? "final";
  const found = useQuery({
    ...ebpInvestmentsOptions({ path: { work_item_id: workItemId }, query: { layer } }),
    enabled: options.active !== false && on,
    retry: false,
  });
  const view = found.data;
  const held = view?.hold_reason != null;
  const signOffProps = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const sourceProps = options.onSourceDocs === undefined ? {} : { onClick: options.onSourceDocs };
  const selectProps = options.onSelect === undefined ? {} : { onSelect: options.onSelect };
  return {
    title: COPY.title,
    actions: (
      <>
        {options.signedInitials != null && (
          <Pill size="chip" variant="green-tint" check>
            {options.signedInitials}
          </Pill>
        )}
        <PaneAction label={COPY.edit} />
        <PaneAction label={COPY.signOff} disabled={held} {...signOffProps} />
        <PaneAction label={COPY.sourceDocs} {...sourceProps} />
      </>
    ),
    controls: (
      <div className="flex w-full items-center justify-between">
        <Segmented
          label={COPY.title}
          active={COPY.layers[layer]}
          onChange={(label) => {
            const next = LAYERS.find((value) => COPY.layers[value] === label);
            if (next !== undefined) options.onLayer?.(next);
          }}
          options={LAYERS.map((value) => COPY.layers[value])}
        />
        {view !== undefined && (
          <span data-ebp06="chips" className="flex gap-[6px]">
            <Pill size="chip" variant={view.tb_balanced ? "green-tint" : "red-tint"}>
              {view.tb_balanced ? COPY.chips.balanced : COPY.chips.unbalanced}
            </Pill>
            <Pill size="chip" variant={view.py_ties ? "green-tint" : "amber"}>
              {view.py_ties ? COPY.chips.pyTies : COPY.chips.pyOff}
            </Pill>
          </span>
        )}
      </div>
    ),
    children:
      view === undefined ? (
        <Skeleton className="m-[12px] h-[240px]" />
      ) : (
        <div data-screen="EBP-06" className="min-h-0 flex-1 overflow-y-auto bg-shell">
          {held && (
            <div
              role="status"
              data-ebp06="hold"
              className="flex min-h-[32px] items-center bg-amber-tint px-[12px] text-[12.5px] text-amber-ink"
            >
              {COPY.certification.hold}
            </div>
          )}
          <div className="bg-card">
            <Table view={view} selected={options.selected ?? null} {...selectProps} />
          </div>
          <Certification
            points={view.points}
            workItemId={workItemId}
            levels={COPY.certification.levelsValue(
              money(view.level1_eoy),
              money(view.nav_eoy),
              money(view.investments_eoy),
            )}
          />
        </div>
      ),
  };
}
