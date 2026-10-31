// AUD-06 · Trial balance & leadsheets (A-02-T09; docs/screens/AUD-06.md): the T2 workpaper pane
// the AUD-02 cockpit shows for its Trial Balance row, read through the generated client (C9 v1).
// Header pills, the R2 label chip, the control row (Trial Balance · Leadsheets; Unadjusted · AJE ·
// RJE · Final), the check strip, the evidence-grammar table with chips and ticks, the provenance
// caption, and the linked row: a line's typed citation re-targets the dock's viewer.
//
// Code computes, models judge (ADR-050): every total, subtotal, difference, Δ and Δ% here is the
// server's string. This file formats and places them; it adds, subtracts and compares no amount
// (the "no browser sums" test reads this source).

import type {
  MappingSetOut,
  TbGroupOut,
  TbLayerLineOut,
  TbLayerViewOut,
  TbLeadsheetAreaOut,
  TbTickOut,
  TieOutCheckOut,
  TrialBalancesOut,
} from "@abacus/api-client";
import {
  getCitationOptions,
  mappingSetOptions,
  mappingSetsOptions,
  tbLayerViewOptions,
  tbLeadsheetAreaOptions,
  tieOutChecksOptions,
  trialBalancesOptions,
} from "@abacus/api-client/query";
import {
  AGENT_NAME,
  Amount,
  type AmountStyle,
  type CockpitCanvas,
  Icon,
  PaneAction,
  Segmented,
  TallyPill,
  Tooltip,
  type ViewState,
  amount,
  cn,
  status,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, Suspense, lazy, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { isNotFound } from "../../domain/audits";
import type { EvidenceViewerTarget } from "../SHL-08";
import { COPY } from "./copy";

// A-02-T24: the live actions load on demand (the firm entry is at its budget).
const AdoptAction = lazy(async () => ({ default: (await import("./TbLive")).AdoptAction }));
const NewerBanner = lazy(async () => ({ default: (await import("./TbLive")).NewerBanner }));
const SourceActions = lazy(async () => ({ default: (await import("./TbLive")).SourceActions }));
// A-02-T35: a line's Agree to source…, Mark reviewed and Edit… on P-04 fields.
const LineActions = lazy(async () => ({ default: (await import("./LineActions")).LineActions }));

export type TbTab = "trial_balance" | "leadsheets";
export type TbLayer = TbLayerViewOut["layer"];

const LAYERS: readonly TbLayer[] = ["unadjusted", "aje", "rje", "final"];

/** Facts the C9 v1 view does not carry yet, for controls whose targets are planned (AUD-33,
 * AUD-38): drawn only in dev, fixture and gallery builds, never in production (A-02-T14). */
export interface PlannedFacts {
  /** A group's entities, the open one first named in `entity` (AUD-06g). */
  entities?: readonly string[];
  entity?: string;
  /** "Final TB released … → FY2026 Form 1120 · …": the hand-off's tooltip (AUD-06h). */
  handOffToTax?: string;
}

export interface TrialBalanceOptions {
  /** Read only while the pane is shown (the cockpit asks on every render). */
  enabled?: boolean;
  /** What the pane opens on (an artboard's state). */
  initial?: { tab?: TbTab; layer?: TbLayer; line?: string; area?: string };
  /** Planned controls' facts (dev, fixture and gallery builds only). */
  planned?: PlannedFacts;
  /** A line was clicked and its citation resolved: the host shows its Viewer. */
  onLink?: () => void;
  /** "Sign off…": the host opens `?ov=signoff:trial_balance:<tb>:L2` (SHL-12, P-04-T48). */
  onSignOff?: (tbId: string) => void;
  /** A-02-T35: the evidence version open in the dock's viewer, for Agree to source…. */
  sourceVersionId?: string | null;
}

export interface TrialBalancePane {
  canvas: CockpitCanvas;
  /** The selected line's citation, as the dock viewer's target; null without one. */
  linked: EvidenceViewerTarget | null;
}

const layerWord = (layer: TbLayer): string => status("trial_balance_layer", layer).label;
const labelWord = (view: TbLayerViewOut): string =>
  status("trial_balance_label", view.label).label;

/** "2026-08-31" as "8/31/2026" (revision.md g): the date's own digits, reordered. */
function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${String(Number.parseInt(m ?? "", 10))}/${String(Number.parseInt(d ?? "", 10))}/${y ?? ""}`;
}

/** The R2 chip: Standard alone; any other label with its period end. */
function chipOf(view: TbLayerViewOut): string {
  return view.label === "standard"
    ? COPY.tbChip(labelWord(view))
    : COPY.tbChip(labelWord(view), shortDate(view.period_end));
}

/** A trial balance with no prior year shows one amount column (AUD-06g). */
function hasPrior(view: TbLayerViewOut): boolean {
  return (
    view.prior_period_end !== null || view.groups.some((g) => g.lines.some((l) => l.boy !== null))
  );
}

/** AUD-06b: every mark on the lines is the agent's (a draft no person has adopted or agreed). */
function isAgentDraft(view: TbLayerViewOut): boolean {
  const ticks = view.groups.flatMap((g) => g.lines.flatMap((l) => l.ticks ?? []));
  return ticks.length > 0 && ticks.every((t) => t.actor_kind === "agent");
}

function styleOf(view: TbLayerViewOut): AmountStyle {
  return view.display_unit === "whole_dollars" ? "whole" : "money";
}

function viewState(
  list: { isError: boolean; error: unknown; data: TrialBalancesOut | undefined },
  view: { isError: boolean; error: unknown; data: TbLayerViewOut | undefined },
  retry: () => void,
): ViewState {
  for (const q of [list, view]) {
    if (q.isError) {
      return isNotFound(q.error)
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry };
    }
  }
  if (list.data === undefined) return { kind: "loading" };
  if (list.data.trial_balances.length === 0) return { kind: "empty" };
  if (view.data === undefined) return { kind: "loading" };
  return { kind: "ready" };
}

// ---- Ticks and chips ---------------------------------------------------------------------------

/** The one mark a line's amounts carry: the reviewer's chip, the preparer's tick, or the agent's
 * outlined tick (no initials, INV-5). */
function markOf(ticks: readonly TbTickOut[]): TbTickOut | undefined {
  return (
    ticks.find((t) => t.actor_kind === "human" && t.kind === "reviewed") ??
    ticks.find((t) => t.actor_kind === "human" && t.kind === "agreed") ??
    ticks.find((t) => t.actor_kind === "agent")
  );
}

function Mark({ tick, pinned }: { tick: TbTickOut; pinned: boolean }): JSX.Element {
  const f = useFormat();
  const at = `${f.date(tick.at)} ${f.time(tick.at)}`;
  const place = pinned ? "absolute top-1/2 right-[10px] -translate-y-1/2" : "ml-[6px]";
  if (tick.actor_kind === "agent") {
    // An agent's mark is outlined and never carries initials (INV-5); it names the agent only.
    return (
      <span
        role="img"
        aria-label={COPY.agentDraft}
        title={AGENT_NAME}
        data-tick="agent"
        className={cn(place, "inline-flex size-[10px] rounded-pill inset-ring-1 inset-ring-ink-3")}
      />
    );
  }
  if (tick.kind === "reviewed" && tick.initials !== null) {
    return (
      <Tooltip
        content={COPY.signedOff(
          tick.by_name,
          COPY.levels[tick.level] ?? `L${String(tick.level)}`,
          at,
        )}
      >
        <button
          type="button"
          data-tick="chip"
          aria-label={COPY.signedOff(
            tick.by_name,
            COPY.levels[tick.level] ?? `L${String(tick.level)}`,
            at,
          )}
          className={cn(
            place,
            "inline-flex h-[18px] items-center gap-[3px] rounded-pill bg-green pr-[6px] pl-[5px] text-micro leading-none font-medium text-on-dark shadow-e1",
          )}
        >
          <Icon name="check" size={12} strokeWidth={2.4} className="size-[9px]" />
          {tick.initials}
        </button>
      </Tooltip>
    );
  }
  return (
    <Tooltip content={COPY.agreed(tick.by_name)}>
      <button
        type="button"
        data-tick="check"
        aria-label={COPY.agreed(tick.by_name)}
        className={cn(place, "inline-flex items-center text-ink-3")}
      >
        <Icon name="check" size={12} strokeWidth={2.2} className="size-[10px]" />
      </button>
    </Tooltip>
  );
}

// ---- The check strip ---------------------------------------------------------------------------

function CheckChip({ check }: { check: TieOutCheckOut }): JSX.Element {
  const r = check.result;
  const pill =
    r.status === "off" ? (
      <TallyPill code="off" vars={{ amount: amount(r.difference, "cents").text }} />
    ) : r.status === "tie" ? (
      <TallyPill code="tie" />
    ) : (
      <TallyPill code="pending" />
    );
  const chip = (
    <span
      tabIndex={r.formula === null ? undefined : 0}
      data-check={check.key}
      data-status={r.status}
      className="inline-flex h-[22px] items-center gap-[6px] rounded-pill bg-card pr-[3px] pl-[9px] text-meta shadow-e1"
    >
      {check.label}
      {pill}
    </span>
  );
  return r.formula === null ? chip : <Tooltip content={r.formula}>{chip}</Tooltip>;
}

function CheckStrip({ checks }: { checks: readonly TieOutCheckOut[] }): JSX.Element | null {
  if (checks.length === 0) return null;
  return (
    <div
      role="group"
      aria-label={COPY.checks}
      data-aud06="checks"
      className="flex h-[34px] flex-none items-center gap-[6px] px-[12px]"
    >
      {checks.map((c) => (
        <CheckChip key={c.id} check={c} />
      ))}
    </div>
  );
}

// ---- The table ---------------------------------------------------------------------------------

function AmountCell({
  value,
  style,
  tick,
  flagged,
}: {
  value: string | null;
  style: AmountStyle;
  tick: TbTickOut | undefined;
  flagged: boolean;
}): JSX.Element {
  return (
    <td
      className={cn(
        "relative pr-[62px] pl-[8px] text-right whitespace-nowrap tabular-nums",
        flagged && "font-medium text-red-ink",
      )}
      {...(flagged ? { "data-flagged": "" } : {})}
    >
      {value === null ? null : flagged ? (
        amount(value, style, { zero: "explicit" }).text
      ) : (
        <Amount value={value} style={style} zero="explicit" />
      )}
      {tick !== undefined && value !== null && <Mark tick={tick} pinned />}
    </td>
  );
}

function LineRow({
  line,
  view,
  checks,
  selected,
  onSelect,
  sourceVersionId,
}: {
  line: TbLayerLineOut;
  view: TbLayerViewOut;
  checks: readonly TieOutCheckOut[];
  selected: boolean;
  onSelect: () => void;
  sourceVersionId: string | null;
}): JSX.Element {
  const style = styleOf(view);
  const final = view.layer === "final";
  const tick = markOf(line.ticks ?? []);
  const flags = line.flags ?? [];
  const flaggedColumns = new Set(
    flags.map((f) => checks.find((c) => c.id === f.check_id)?.column ?? "eoy"),
  );
  const refs = line.adjustment_refs ?? [];
  return (
    <tr
      data-account={line.account_code}
      {...(selected ? { "data-selected": "" } : {})}
      className={cn("h-[29px] hairline-b", selected && "bg-sel-bg")}
    >
      <td className="max-w-[196px] truncate pr-[8px] pl-[12px]">
        <button type="button" aria-pressed={selected} onClick={onSelect} className="text-left">
          {line.account_name}
        </button>
        {tick?.kind === "reviewed" && tick.actor_kind === "human" && (
          <Mark tick={tick} pinned={false} />
        )}
        {flags.map((f) => (
          <span
            key={f.check_id}
            role="img"
            aria-label={COPY.doesNotTie}
            data-flag={f.kind}
            data-issue={f.issue_id ?? undefined}
            className="ml-[6px] inline-flex text-red-ink"
          >
            <Icon name="flag" size={12} />
          </span>
        ))}
      </td>
      {hasPrior(view) && (
        <AmountCell
          value={line.boy}
          style={style}
          tick={tick}
          flagged={flaggedColumns.has("boy")}
        />
      )}
      <AmountCell
        value={final ? (line.final ?? line.eoy) : line.eoy}
        style={style}
        tick={tick}
        flagged={flaggedColumns.has("eoy")}
      />
      {final && (
        <td data-col="aje" className="pr-[8px] pl-[8px] text-right whitespace-nowrap tabular-nums">
          {line.aje === null ? null : <Amount value={line.aje} style={style} />}
          {refs.map((r) => (
            <span
              key={r}
              data-ref={r}
              className="ml-[6px] inline-flex h-[18px] items-center rounded-pill bg-nested px-[7px] text-micro font-medium text-ink-2"
            >
              {r}
            </span>
          ))}
        </td>
      )}
      <td className="pr-[12px] pl-[8px] text-meta text-ink-3">
        {line.wp_ref ?? ""}
        {(view.allowed_actions ?? []).includes("trial_balance.annotate") && (
          <Suspense fallback={null}>
            <LineActions
              tbId={view.trial_balance_id}
              line={line}
              sourceVersionId={sourceVersionId}
            />
          </Suspense>
        )}
      </td>
    </tr>
  );
}

function TrialBalanceTable({
  view,
  checks,
  selected,
  onSelect,
  sourceVersionId,
}: {
  view: TbLayerViewOut;
  checks: readonly TieOutCheckOut[];
  selected: string | null;
  onSelect: (line: TbLayerLineOut) => void;
  sourceVersionId: string | null;
}): JSX.Element {
  const style = styleOf(view);
  const final = view.layer === "final";
  const prior = hasPrior(view);
  const span = (final ? 5 : 4) - (prior ? 0 : 1);
  const last = view.totals.length - 1;
  const eoyHeader =
    view.label === "standard"
      ? COPY.columns.eoy
      : COPY.labelColumn(labelWord(view), shortDate(view.period_end));
  return (
    <table data-aud06="lines" aria-label={COPY.title} className="w-full text-cell">
      <thead>
        <tr className="h-[28px] bg-surface text-th text-ink-2 hairline-t hairline-b">
          <th className="pl-[12px] text-left font-normal">{COPY.columns.description}</th>
          {prior && <th className="pr-[62px] text-right font-normal">{COPY.columns.boy}</th>}
          <th className="pr-[62px] text-right font-normal">{eoyHeader}</th>
          {final && <th className="pr-[8px] text-right font-normal">{COPY.columns.aje}</th>}
          <th className="pr-[12px] text-left font-normal">{COPY.columns.wpRef}</th>
        </tr>
      </thead>
      <tbody>
        {view.groups.map((g) => (
          <GroupRows
            key={g.key}
            label={g.label}
            span={span}
            rows={g.lines.map((l) => (
              <LineRow
                key={l.account_code}
                line={l}
                view={view}
                checks={checks}
                selected={l.account_code === selected}
                onSelect={() => {
                  onSelect(l);
                }}
                sourceVersionId={sourceVersionId}
              />
            ))}
          />
        ))}
        {view.totals.map((t, i) => (
          <tr
            key={t.key}
            data-total={t.key}
            className={cn(
              "h-[29px] font-medium hairline-t",
              i === last && "border-b-3 border-double border-ink-3",
            )}
          >
            <td className="pl-[12px]">{t.label}</td>
            {prior && (
              <td className="pr-[62px] text-right whitespace-nowrap tabular-nums">
                {t.boy === null ? null : <Amount value={t.boy} style={style} zero="explicit" />}
              </td>
            )}
            <td className="pr-[62px] text-right whitespace-nowrap tabular-nums">
              <Amount value={t.eoy} style={style} zero="explicit" />
            </td>
            {final && <td />}
            <td />
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function GroupRows({
  label,
  span,
  rows,
}: {
  label: string;
  span: number;
  rows: ReactNode;
}): JSX.Element {
  return (
    <>
      <tr data-group="" className="h-[29px] hairline-b">
        <td colSpan={span} className="pl-[12px] font-medium uppercase">
          {label}
        </td>
      </tr>
      {rows}
    </>
  );
}

function Caption({ view }: { view: TbLayerViewOut }): JSX.Element {
  const f = useFormat();
  const p = view.provenance;
  return (
    <p data-aud06="caption" className="px-[12px] py-[10px] text-meta text-ink-3">
      {COPY.caption(
        layerWord(view.layer),
        p.adopted_by_name,
        COPY.sources[p.source] ?? COPY.otherSource,
        `${f.date(p.adopted_at)}, ${f.time(p.adopted_at)}`,
      )}
    </p>
  );
}

// ---- Group by FS line (A-03-T12) ----------------------------------------------------------------

/** The trial balance's lines regrouped by the confirmed mapping's grouping › FS line, under the
 * server's grouping subtotals (C9 v2 `group_by=fs_line`). Nothing is summed here: each group's
 * figure is the mapping's subtotal, each line keeps its own figures, and a line the mapping does
 * not name stays in its original group after the mapped ones. */
export function byFsLine(view: TbLayerViewOut, mapping: MappingSetOut): TbLayerViewOut {
  const lines = view.groups.flatMap((g) => g.lines);
  const rowOf = new Map(mapping.rows.map((r) => [r.account_code, r]));
  const placed = new Set<string>();
  const groups: TbGroupOut[] = mapping.subtotals.flatMap((g) => {
    const mine = lines.filter(
      (l) => rowOf.get(l.account_code)?.grouping_label === g.grouping_label,
    );
    if (mine.length === 0) return [];
    for (const l of mine) placed.add(l.account_code);
    return [
      {
        key: `fs:${g.grouping_key}`,
        label: g.grouping_label,
        boy: null,
        eoy: g.subtotal,
        lines: mine,
      },
    ];
  });
  const rest = view.groups
    .map((g) => ({ ...g, lines: g.lines.filter((l) => !placed.has(l.account_code)) }))
    .filter((g) => g.lines.length > 0);
  return { ...view, groups: [...groups, ...rest] };
}

/** The engagement's confirmed mapping for this trial balance, read by FS line; undefined while
 * the flag is off, nothing is confirmed, or the read has not answered. */
function useFsLineMapping(
  engagementId: string,
  view: TbLayerViewOut | undefined,
  enabled: boolean,
): MappingSetOut | undefined {
  const on = useFlag("ledger.tb_mapping") === true && enabled;
  const sets = useQuery({
    ...mappingSetsOptions({ path: { engagement_id: engagementId } }),
    enabled: on && view !== undefined,
    retry: false,
  });
  const set = sets.data?.items.find(
    (m) =>
      m.trial_balance_id === view?.trial_balance_id &&
      (m.status === "prepared" || m.status === "reviewed"),
  );
  const mapping = useQuery({
    ...mappingSetOptions({
      path: { mapping_set_id: set?.id ?? "" },
      query: { group_by: "fs_line" },
    }),
    enabled: on && set !== undefined,
    retry: false,
  });
  return set === undefined ? undefined : mapping.data;
}

// ---- Leadsheets --------------------------------------------------------------------------------

/** The audit areas the server names on the lines, in the view's order, each once. */
function areasOf(view: TbLayerViewOut): string[] {
  const seen: string[] = [];
  for (const l of view.groups.flatMap((g) => g.lines)) {
    if (l.area !== null && !seen.includes(l.area)) seen.push(l.area);
  }
  return seen;
}

function Leadsheet({
  engagementId,
  view,
  enabled,
  initialArea,
}: {
  engagementId: string;
  view: TbLayerViewOut;
  enabled: boolean;
  initialArea?: string;
}): JSX.Element | null {
  // AUD-06e: one leadsheet per audit area the server names; the picker chooses which.
  const areas = areasOf(view);
  const [picked, setPicked] = useState<string | null>(
    initialArea !== undefined && areas.includes(initialArea) ? initialArea : null,
  );
  const area = picked ?? areas[0] ?? null;
  const sheet = useQuery({
    ...tbLeadsheetAreaOptions({
      path: { engagement_id: engagementId, tb_id: view.trial_balance_id, area: area ?? "" },
      query: { layer: view.layer },
    }),
    enabled: enabled && area !== null,
    retry: false,
  });
  if (sheet.data === undefined) return null;
  const s = sheet.data;
  const pctOf = (v: string | null): string => (v === null ? "" : `${v}%`);
  return (
    <>
      {areas.length > 1 && (
        <div data-aud06="areas" className="flex h-[36px] flex-none items-center px-[12px]">
          <Segmented
            size="small"
            label={COPY.areas}
            options={areas.slice(0, 7)}
            active={s.area}
            onChange={setPicked}
          />
        </div>
      )}
      <LeadsheetTable s={s} pctOf={pctOf} />
    </>
  );
}

function LeadsheetTable({
  s,
  pctOf,
}: {
  s: TbLeadsheetAreaOut;
  pctOf: (v: string | null) => string;
}): JSX.Element {
  return (
    <table data-aud06="leadsheet" aria-label={s.area} className="w-full text-cell">
      <thead>
        <tr className="h-[28px] bg-surface text-th text-ink-2 hairline-t hairline-b">
          <th className="pl-[12px] text-left font-normal">{COPY.leadsheet.account}</th>
          <th className="pr-[8px] text-right font-normal">{COPY.leadsheet.py}</th>
          <th className="pr-[8px] text-right font-normal">{COPY.leadsheet.cy}</th>
          <th className="pr-[8px] text-right font-normal">{COPY.leadsheet.change}</th>
          <th className="pr-[12px] text-right font-normal">{COPY.leadsheet.changePct}</th>
        </tr>
      </thead>
      <tbody>
        {s.rows.map((r) => (
          <tr key={r.account_code} data-row={r.account_code} className="h-[29px] hairline-b">
            <td className="pl-[12px]">{r.account_name}</td>
            <td className="pr-[8px] text-right tabular-nums">
              {r.py === null ? null : <Amount value={r.py} style="whole" />}
            </td>
            <td className="pr-[8px] text-right tabular-nums">
              <Amount value={r.cy} style="whole" />
            </td>
            <td className="pr-[8px] text-right tabular-nums">
              {r.change === null ? null : <Amount value={r.change} style="whole" />}
            </td>
            <td className="pr-[12px] text-right tabular-nums">{pctOf(r.change_pct)}</td>
          </tr>
        ))}
        <tr data-row="total" className="h-[29px] font-medium hairline-t">
          <td className="pl-[12px]">{s.area}</td>
          <td className="pr-[8px] text-right tabular-nums">
            {s.py === null ? null : <Amount value={s.py} style="whole" />}
          </td>
          <td className="pr-[8px] text-right tabular-nums">
            <Amount value={s.cy} style="whole" />
          </td>
          <td className="pr-[8px] text-right tabular-nums">
            {s.change === null ? null : <Amount value={s.change} style="whole" />}
          </td>
          <td className="pr-[12px] text-right tabular-nums">{pctOf(s.change_pct)}</td>
        </tr>
      </tbody>
    </table>
  );
}

// ---- The pane ----------------------------------------------------------------------------------

/** The first typed citation a line carries: its own, then a tick's. */
function citationOf(line: TbLayerLineOut): string | null {
  return (
    (line.citation_ids ?? [])[0] ??
    (line.ticks ?? []).find((t) => t.citation_id !== null)?.citation_id ??
    null
  );
}

export function useTrialBalancePane(
  engagementId: string,
  {
    enabled = true,
    initial = {},
    onLink,
    onSignOff,
    planned = {},
    sourceVersionId = null,
  }: TrialBalanceOptions = {},
): TrialBalancePane {
  const [tab, setTab] = useState<TbTab>(initial.tab ?? "trial_balance");
  const [layer, setLayer] = useState<TbLayer>(initial.layer ?? "unadjusted");
  const [selected, setSelected] = useState<string | null>(initial.line ?? null);
  const list = useQuery({
    ...trialBalancesOptions({ path: { engagement_id: engagementId } }),
    enabled,
    retry: false,
  });
  const tb = list.data?.trial_balances[0];
  const tbPath = { engagement_id: engagementId, tb_id: tb?.id ?? "" };
  const view = useQuery({
    ...tbLayerViewOptions({ path: { ...tbPath, layer } }),
    enabled: enabled && tb !== undefined,
    retry: false,
  });
  const checks = useQuery({
    ...tieOutChecksOptions({ path: tbPath }),
    enabled: enabled && tb !== undefined,
    retry: false,
  });
  const fsLine = useFsLineMapping(engagementId, view.data, enabled);
  const v =
    view.data === undefined || fsLine === undefined ? view.data : byFsLine(view.data, fsLine);
  const line = v?.groups.flatMap((g) => g.lines).find((l) => l.account_code === selected);
  const citationId = line === undefined ? null : citationOf(line);
  const citation = useQuery({
    ...getCitationOptions({ path: { citation_id: citationId ?? "" } }),
    enabled: enabled && citationId !== null,
    retry: false,
  });
  const c = citationId === null ? undefined : citation.data;
  const linked: EvidenceViewerTarget | null =
    c?.source.evidence_version_id == null || c.match_id === null
      ? null
      : { versionId: c.source.evidence_version_id, matchId: c.match_id, engagementId };

  const state = viewState(list, view, () => {
    void list.refetch();
    void view.refetch();
  });
  const allowed = new Set(v?.allowed_actions ?? []);
  const available = new Set(v?.layers_available ?? ["unadjusted"]);
  const someUnavailable = LAYERS.some((l) => !available.has(l));

  const layers = (
    <Segmented
      size="small"
      label={COPY.layers}
      options={LAYERS.map((l) => ({ label: layerWord(l), disabled: !available.has(l) }))}
      active={layerWord(layer)}
      onChange={(word) => {
        const next = LAYERS.find((l) => layerWord(l) === word);
        if (next !== undefined) setLayer(next);
      }}
    />
  );

  const snapshots = list.data?.snapshots ?? [];
  const [exporting, setExporting] = useState(false);
  const exportExcel = (): void => {
    if (v === undefined) return;
    setExporting(true);
    void import("./TbLive")
      .then(async (m) => m.downloadExport(engagementId, v.trial_balance_id, v.layer, v.version_no))
      .catch(() => undefined)
      .finally(() => {
        setExporting(false);
      });
  };

  const canvas: CockpitCanvas = {
    title: COPY.title,
    state,
    empty: {
      icon: "file-text",
      title: COPY.empty,
      ...(snapshots.length === 0
        ? {}
        : {
            action: (
              <Suspense fallback={null}>
                <AdoptAction engagementId={engagementId} snapshots={snapshots} />
              </Suspense>
            ),
          }),
    },
    actions: (
      <>
        {v !== undefined && isAgentDraft(v) && (
          <span
            data-aud06="draft"
            className="inline-flex h-[22px] items-center rounded-pill bg-nested px-[9px] text-meta text-ink-2"
          >
            {COPY.agentDraft}
          </span>
        )}
        {PLANNED_VISIBLE && planned.handOffToTax !== undefined && v?.layer === "final" && (
          <Tooltip content={planned.handOffToTax}>
            <span tabIndex={0} data-aud06="hand-off" aria-label={planned.handOffToTax}>
              <PaneAction label={COPY.handOffToTax} disabled />
            </span>
          </Tooltip>
        )}
        {PLANNED_VISIBLE && allowed.has("trial_balance.annotate") && (
          <PaneAction icon="pencil" label={COPY.edit} disabled />
        )}
        {allowed.has("sign_off.review") && onSignOff !== undefined && v !== undefined ? (
          <PaneAction
            icon="check"
            label={COPY.signOff}
            opensDialog
            onClick={() => {
              onSignOff(v.trial_balance_id);
            }}
          />
        ) : (
          PLANNED_VISIBLE &&
          allowed.has("sign_off.review") && (
            <PaneAction icon="check" label={COPY.signOff} opensDialog disabled />
          )
        )}
        {PLANNED_VISIBLE && <PaneAction icon="file-text" label={COPY.sourceDocs} disabled />}
      </>
    ),
    controls:
      v === undefined ? undefined : (
        <>
          <Segmented
            size="small"
            label={COPY.tabs.label}
            options={[COPY.tabs.trialBalance, COPY.tabs.leadsheets]}
            active={tab === "leadsheets" ? COPY.tabs.leadsheets : COPY.tabs.trialBalance}
            onChange={(word) => {
              setTab(word === COPY.tabs.leadsheets ? "leadsheets" : "trial_balance");
            }}
          />
          {someUnavailable ? (
            <Tooltip content={COPY.layerUnavailable}>
              <span tabIndex={0} data-aud06="layers" aria-label={COPY.layerUnavailable}>
                {layers}
              </span>
            </Tooltip>
          ) : (
            <span data-aud06="layers">{layers}</span>
          )}
          <PaneAction kind="picker" label={chipOf(v)} />
          <span className="flex-1" />
          <Suspense fallback={null}>
            <SourceActions engagementId={engagementId} view={v} />
          </Suspense>
          {allowed.has("trial_balance.export") && (
            <PaneAction
              icon="cloud-download"
              label={COPY.openInExcel}
              disabled={exporting}
              onClick={exportExcel}
            />
          )}
        </>
      ),
    children:
      v === undefined ? null : (
        <div data-aud06="body" className="flex flex-col">
          {PLANNED_VISIBLE && (planned.entities?.length ?? 0) > 1 && (
            <div
              data-aud06="entities"
              className="flex h-[36px] flex-none items-center gap-[8px] px-[12px]"
            >
              <Segmented
                size="small"
                label={COPY.entities}
                options={(planned.entities ?? []).map((e) => ({
                  label: e,
                  disabled: e !== planned.entity,
                }))}
                {...(planned.entity === undefined ? {} : { active: planned.entity })}
              />
              <span className="text-meta text-ink-3">{COPY.consolidated}</span>
            </div>
          )}
          {v.newer_snapshots > 0 && (
            <Suspense fallback={null}>
              <NewerBanner engagementId={engagementId} view={v} />
            </Suspense>
          )}
          {tab === "leadsheets" ? (
            <Leadsheet
              engagementId={engagementId}
              view={v}
              enabled={enabled}
              {...(initial.area === undefined ? {} : { initialArea: initial.area })}
            />
          ) : (
            <>
              <CheckStrip checks={checks.data ?? []} />
              <TrialBalanceTable
                view={v}
                checks={checks.data ?? []}
                selected={selected}
                onSelect={(l) => {
                  setSelected(l.account_code);
                  if (citationOf(l) !== null) onLink?.();
                }}
                sourceVersionId={sourceVersionId ?? linked?.versionId ?? null}
              />
              <Caption view={v} />
            </>
          )}
        </div>
      ),
  };
  return { canvas, linked };
}
