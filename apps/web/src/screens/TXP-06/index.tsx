// TXP-06 · Allocation Structure (T-05-T44; docs/screens/TXP-06.md; handoff TXP-06 A–D): the O4 full
// sheet over TXP-05 at `?ov=allocation`. Rail (summary, the four KV stacks, reconciliation pills,
// partners), the rules or waterfall column (rung cards with stacked bars and ledger rows) and the
// right column (allocation by period or cumulative liquidation; the reconciliation table). Every
// figure is the server's (`GET …/allocation-structure`, `POST …/preview` while editing); the
// screen lays out and adds nothing. A2: a partner picked in the rail outlines its series; C: the
// agreement reader's reasoning with its two clause citations and Approve structure (SHL-12, L3); D:
// a rung's percentage edited inline previews live and the back-solve reads Pending until Save. Esc
// and X close (the sheet traps focus and returns it to the trigger).
import type {
  WorkbookAllocationPartnerOut,
  WorkbookAllocationPeriodOut,
  WorkbookAllocationStructureOut,
} from "@abacus/api-client";
import { AgentText, Button, FullSheet, Pill, Tag, Tooltip, amount, cn } from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";

const FILLS = ["bg-viz-p1", "bg-viz-p2", "bg-viz-p3", "bg-surface-deep", "bg-viz-p4"] as const;
const n = (v: string | null | undefined) => (v == null ? "—" : amount(v, "whole").text);

function fillOf(index: number, count: number): string {
  // Five partners: the fourth is --surface (handoff: "fifth partner uses --surface").
  if (count <= 4) return FILLS[index === 3 ? 4 : index] ?? FILLS[0];
  return FILLS[index] ?? FILLS[0];
}

function fmt(template: string, vars: Readonly<Record<string, string>>): string {
  return template.replace(/\{(\w+)\}/g, (_m, k: string) => vars[k] ?? "");
}

function dateOf(iso: string | null | undefined): string {
  if (iso == null) return "";
  const [, m, d] = iso.split("-");
  return `${String(Number(m))}/${String(Number(d))}`;
}

interface Segment {
  key: string;
  label: string;
  value: string;
  fill: string;
  tooltip?: string;
  outlined?: boolean;
}

/** A 26-tall stacked bar: partner fills, a white prior-tier segment and the remainder. Widths are
 * the server's amounts over the bar's total (layout, not arithmetic on figures). */
export function StackedBar({
  segments,
  total,
  label,
}: {
  segments: readonly Segment[];
  total: string;
  label: string;
}): JSX.Element {
  const whole = Number(total) || 1;
  return (
    <div
      role="img"
      aria-label={label}
      className="flex h-[26px] w-full overflow-hidden rounded-[6px] bg-nested"
    >
      {segments.map((s) => {
        const width = `${String((Number(s.value) / whole) * 100)}%`;
        const body = (
          <span
            key={s.key}
            data-segment={s.key}
            style={{ width }}
            className={cn(
              "flex h-full items-center justify-center truncate text-[11px] font-medium text-ink",
              s.fill,
              s.outlined === true && "outline -outline-offset-1 outline-ink",
            )}
          >
            {Number(s.value) / whole > 0.08 ? s.label : ""}
          </span>
        );
        return s.tooltip === undefined ? (
          body
        ) : (
          <Tooltip key={s.key} content={s.tooltip}>
            {body}
          </Tooltip>
        );
      })}
    </div>
  );
}

function Ledger({ rows }: { rows: readonly (readonly [string, string])[] }): JSX.Element {
  return (
    <dl className="mt-[6px] flex flex-col">
      {rows.map(([k, v]) => (
        <div key={k} className="flex h-[22px] items-center justify-between text-[11.5px]">
          <dt className="text-ink-2">{k}</dt>
          <dd className="tabular-nums text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

type Rung = WorkbookAllocationStructureOut["rungs"][number];

function rungTitle(r: Rung): [string, string] {
  const pct = r.percentage == null ? "" : String(Number(r.percentage));
  const lp = r.percentage == null ? "" : String(100 - Number(r.percentage));
  const found = (COPY.harborview.rungs as Readonly<Record<string, readonly [string, string]>>)[
    r.key
  ];
  if (found === undefined) return [r.label, ""];
  return [fmt(found[0], { pct, lp }), fmt(found[1], { pct, lp })];
}

export interface TXP06Props {
  structure: WorkbookAllocationStructureOut | undefined;
  /** D: the preview of the edited draft (`persisted: false`). */
  preview?: WorkbookAllocationStructureOut | undefined;
  open?: boolean;
  /** Hold the sheet in place (gallery and tests). */
  forceOpen?: boolean;
  /** A2: the partner whose series is outlined. */
  selected?: string | null;
  /** D: the rung being edited (its priority). */
  editing?: number | null;
  approvedBy?: string;
  approvedOn?: string;
  onClose?: () => void;
  onSelect?: (partnerId: string | null) => void;
  onEdit?: (priority: number | null) => void;
  /** D: a percentage typed in the rung's field (the host previews). */
  onRung?: (priority: number, percentage: string) => void;
  onSave?: () => void;
  /** C → C2: SHL-12 at L3 (the host opens it). */
  onApprove?: () => void;
  /** C: a clause citation opens SHL-08 with the clause lit. */
  onCitation?: (citationId: string) => void;
  /** The Item L rollforward check opens TXP-07. */
  onItemL?: () => void;
}

function Rail({
  s,
  selected,
  onSelect,
  onApprove,
  onCitation,
  onItemL,
  approvedBy,
  approvedOn,
}: Pick<
  TXP06Props,
  "selected" | "onSelect" | "onApprove" | "onCitation" | "onItemL" | "approvedBy" | "approvedOn"
> & {
  s: WorkbookAllocationStructureOut;
}): JSX.Element {
  const straight = s.kind === "straight_percentage";
  const pending = s.status === "pending_approval";
  const checks = straight ? COPY.checks.straight : COPY.checks.waterfall;
  const method = straight
    ? s.method === "proration"
      ? COPY.method.proration
      : `Interim closing, ${COPY.convention[s.convention ?? "monthly"]} convention`
    : COPY.method.waterfall;
  return (
    <aside className="flex w-[236px] flex-none flex-col gap-[10px] rounded-pane bg-card p-[12px] shadow-e1">
      <div className="flex justify-end">
        {pending ? (
          <Button variant="primary" size="sm" onClick={onApprove}>
            {COPY.approve}
          </Button>
        ) : approvedBy !== undefined && approvedOn !== undefined ? (
          <Pill variant="green" check>
            {COPY.approved(approvedBy, approvedOn)}
          </Pill>
        ) : null}
      </div>
      <h3 className="text-[14px] font-medium text-ink">{COPY.summary}</h3>
      <p className="text-[12px] leading-[1.45] text-ink-2">
        {straight ? COPY.ridgeline.summary : COPY.harborview.summary}
      </p>
      {pending && s.proposed_by === "agent" ? (
        <section aria-label={COPY.reasoning} className="rounded-[10px] bg-shell p-[10px]">
          <p className="mb-[4px] text-[12px] font-medium text-ink">{COPY.reasoning}</p>
          <AgentText text={COPY.ridgeline.reasoning} />
          <p className="mt-[6px] flex flex-wrap gap-[6px] text-[11.5px] text-ink-3">
            <span>{COPY.citations(s.citation_ids?.length ?? 0)}</span>
            {(s.citation_ids ?? []).map((c, i) => (
              <button key={c} type="button" className="underline" onClick={() => onCitation?.(c)}>
                {`[${String(i + 1)}]`}
              </button>
            ))}
          </p>
        </section>
      ) : null}
      <dl className="flex flex-col gap-[8px]">
        {(
          [
            [COPY.kv.structure, COPY.kind[s.kind], undefined],
            [COPY.kv.income, n(s.income), straight ? COPY.ridgeline.incomeSub : undefined],
            [COPY.kv.distributable, straight ? COPY.noWaterfall : n(s.distributable), undefined],
            [COPY.kv.method, method, undefined],
          ] as const
        ).map(([k, v, sub]) => (
          <div key={k}>
            <dt className="text-[9.5px] font-medium uppercase tracking-[0.07em] text-ink-3">
              {k}
            </dt>
            <dd className="text-[12.5px] tabular-nums text-ink">{v}</dd>
            {sub === undefined ? null : <dd className="text-[11px] text-ink-3">{sub}</dd>}
          </div>
        ))}
      </dl>
      <section aria-label={COPY.reconciliation}>
        <p className="flex h-[31px] items-center bg-band-hd px-[6px] text-[12px] font-medium">
          {COPY.reconciliation}
        </p>
        {checks.map((label) => {
          const itemL = label === "Item L rollforward";
          const pill = pending
            ? { text: COPY.pending, variant: "neutral" as const }
            : straight && itemL
              ? { text: "Check", variant: "amber" as const }
              : { text: "tie", variant: "green" as const };
          return (
            <div
              key={label}
              className="flex h-[31px] items-center justify-between px-[6px] text-[12px]"
            >
              {itemL && onItemL !== undefined ? (
                <button type="button" onClick={onItemL} className="text-left">
                  {label}
                </button>
              ) : (
                <span>{label}</span>
              )}
              <Pill variant={pill.variant} size="tally">
                {pill.text}
              </Pill>
            </div>
          );
        })}
      </section>
      <section aria-label={COPY.partners}>
        <p className="flex h-[31px] items-center bg-band-hd px-[6px] text-[12px] font-medium">
          {COPY.partners}
        </p>
        {(s.partners ?? []).map((p) => (
          <button
            key={p.partner_id}
            type="button"
            aria-pressed={selected === p.partner_id}
            onClick={() => onSelect?.(selected === p.partner_id ? null : p.partner_id)}
            className={cn(
              "flex h-[38px] w-full items-center justify-between px-[6px] text-left",
              selected === p.partner_id && "bg-sel-bg",
            )}
          >
            <span>
              <span className="block text-[12px] font-medium text-ink">{p.name}</span>
              <span className="block text-[11px] text-ink-3">{COPY.roles[p.kind]}</span>
            </span>
            <Tag>{COPY.tags[p.kind]}</Tag>
          </button>
        ))}
      </section>
    </aside>
  );
}

function periodSegments(
  s: WorkbookAllocationStructureOut,
  period: WorkbookAllocationPeriodOut,
  selected: string | null | undefined,
): Segment[] {
  const partners = s.partners ?? [];
  return partners.flatMap((p, i) => {
    const r = (s.results ?? []).find(
      (x) => x.partner_id === p.partner_id && x.period_key === period.key,
    );
    if (r === undefined) return [];
    return [
      {
        key: `${period.key}:${p.partner_id}`,
        label: `${p.name.split(" ")[0] ?? p.name} ${n(r.amount)}`,
        value: r.amount,
        fill: fillOf(i, partners.length),
        tooltip: COPY.tooltip(
          p.name,
          n(r.amount),
          String(Math.round((Number(r.amount) / Number(period.amount)) * 100)),
          n(period.amount),
        ),
        outlined: selected === p.partner_id,
      },
    ];
  });
}

function rungSegments(
  s: WorkbookAllocationStructureOut,
  rung: WorkbookAllocationPeriodOut,
  priority: number,
  selected: string | null | undefined,
): Segment[] {
  const partners = s.partners ?? [];
  const out: Segment[] = [];
  if (rung.prior != null) {
    out.push({
      key: `prior:${rung.key}`,
      label: `${COPY.priorTiers} ${n(rung.prior)}`,
      value: rung.prior,
      fill: "bg-card ring-1 ring-inset ring-hair",
    });
  }
  partners.forEach((p, i) => {
    const r = (s.results ?? []).find(
      (x) => x.partner_id === p.partner_id && x.rung_priority === priority,
    );
    if (r !== undefined) {
      out.push({
        key: `${rung.key}:${p.partner_id}`,
        label: n(r.amount),
        value: r.amount,
        fill: fillOf(i, partners.length),
        tooltip: `${p.name} · ${n(r.amount)}`,
        outlined: selected === p.partner_id,
      });
    }
  });
  if (rung.remaining != null && Number(rung.remaining) > 0) {
    out.push({
      key: `rest:${rung.key}`,
      label: n(rung.remaining),
      value: rung.remaining,
      fill: "bg-nested border border-dashed border-stroke",
    });
  }
  return out;
}

function Rules({
  s,
  selected,
  editing,
  onEdit,
  onRung,
  onSave,
}: Pick<TXP06Props, "selected" | "editing" | "onEdit" | "onRung" | "onSave"> & {
  s: WorkbookAllocationStructureOut;
}): JSX.Element {
  const straight = s.kind === "straight_percentage";
  const partners = s.partners ?? [];
  const periods = s.periods ?? [];
  return (
    <section
      aria-label={straight ? COPY.rules : COPY.waterfall}
      className="flex min-w-0 flex-1 flex-col rounded-pane bg-card shadow-e1"
    >
      <h3 className="flex h-[32px] items-center justify-center text-[12.5px] font-medium">
        {straight ? COPY.rules : COPY.waterfall}
      </h3>
      <div className="flex flex-col gap-[10px] overflow-auto p-[10px]">
        {straight ? (
          <>
            <article className="rounded-[10px] bg-shell p-[11px_12px_12px] ring-1 ring-inset ring-hair">
              <header className="flex items-center gap-[6px]">
                <span className="text-[13px] font-medium">{COPY.ridgeline.rung1}</span>
                <span className="rounded-full bg-chip px-[6px] text-[10.5px] font-medium text-ink-2">
                  {COPY.priority(1)}
                </span>
                <span className="flex-1" />
                <span className="text-[13px] font-medium tabular-nums">{n(s.income)}</span>
              </header>
              <p className="mb-[8px] text-[11.5px] text-ink-2">{COPY.ridgeline.rung1Sub}</p>
              {periods.map((p) => (
                <div key={p.key} className="mb-[8px]">
                  <p className="mb-[2px] text-[11.5px] text-ink-2">
                    {COPY.periodLabel(
                      dateOf(p.starts_on),
                      `${dateOf(p.ends_on)}/${(p.ends_on ?? "").slice(0, 4)}`,
                      n(p.amount),
                    )}
                  </p>
                  <StackedBar
                    segments={periodSegments(s, p, selected)}
                    total={p.amount}
                    label={p.key}
                  />
                </div>
              ))}
              <Ledger
                rows={[
                  [COPY.available, n(s.income)],
                  ...partners.map((p) => [p.name, n(p.total)] as const),
                  [COPY.remaining, "—"],
                ]}
              />
            </article>
            <article className="rounded-[10px] bg-shell p-[11px_12px_12px] text-ink-3 ring-1 ring-inset ring-hair">
              <header className="flex items-center gap-[6px]">
                <span className="text-[13px] font-medium">{COPY.ridgeline.rung2}</span>
                <span className="rounded-full bg-chip px-[6px] text-[10.5px] font-medium">
                  {COPY.priority(2)}
                </span>
                <span className="flex-1" />
                <span>—</span>
              </header>
              <p className="text-[11.5px]">{COPY.ridgeline.rung2Sub}</p>
            </article>
          </>
        ) : (
          s.rungs.map((rung, i) => {
            const priority = i + 1;
            const tier = periods.find((p) => p.key === `r${String(priority)}`);
            const [title, sub] = rungTitle(rung);
            const isEditing = editing === priority;
            return (
              <article
                key={rung.key}
                data-rung={priority}
                className="rounded-[10px] bg-shell p-[11px_12px_12px] ring-1 ring-inset ring-hair"
              >
                <header className="flex items-center gap-[6px]">
                  <span className="text-[13px] font-medium">{title}</span>
                  <span className="rounded-full bg-chip px-[6px] text-[10.5px] font-medium text-ink-2">
                    {COPY.priority(priority)}
                  </span>
                  <span className="flex-1" />
                  {rung.percentage != null && onEdit !== undefined && !isEditing ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        onEdit(priority);
                      }}
                    >
                      {COPY.edit}
                    </Button>
                  ) : null}
                  <span className="text-[13px] font-medium tabular-nums">{n(tier?.amount)}</span>
                </header>
                <p className="mb-[8px] text-[11.5px] text-ink-2">{sub}</p>
                {isEditing ? (
                  <div className="mb-[8px] flex items-center gap-[8px] rounded-[6px] bg-nested p-[6px]">
                    <label className="flex items-center gap-[6px] text-[11.5px]">
                      {rung.key === "preferred_return"
                        ? COPY.fields.rate
                        : rung.key === "catch_up"
                          ? COPY.fields.target
                          : COPY.fields.gp}
                      <input
                        aria-label={title}
                        inputMode="decimal"
                        defaultValue={
                          rung.percentage == null ? "" : String(Number(rung.percentage))
                        }
                        className="h-[24px] w-[56px] rounded-[4px] bg-card px-[6px] tabular-nums"
                        onChange={(e) => onRung?.(priority, e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            e.stopPropagation();
                            onEdit?.(null);
                          }
                        }}
                      />
                    </label>
                    <span className="flex-1" />
                    <Button variant="ghost" size="sm" onClick={() => onEdit?.(null)}>
                      {COPY.cancel}
                    </Button>
                    <Button variant="primary" size="sm" onClick={onSave}>
                      {COPY.save}
                    </Button>
                  </div>
                ) : null}
                {tier === undefined ? null : (
                  <>
                    <StackedBar
                      segments={rungSegments(s, tier, priority, selected)}
                      total={s.distributable ?? tier.amount}
                      label={`${title} · ${COPY.waterfall}`}
                    />
                    <Ledger
                      rows={[
                        ...(tier.prior == null ? [] : [[COPY.priorTiers, n(tier.prior)] as const]),
                        [COPY.available, n(tier.available)],
                        ...partners.flatMap((p) => {
                          const r = (s.results ?? []).find(
                            (x) => x.partner_id === p.partner_id && x.rung_priority === priority,
                          );
                          return r === undefined ? [] : [[p.name, n(r.amount)] as const];
                        }),
                        [COPY.remaining, n(tier.remaining)],
                      ]}
                    />
                  </>
                )}
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}

function Bars({
  title,
  rows,
}: {
  title: string;
  rows: readonly { name: string; value: string; fill: string }[];
}): JSX.Element {
  const max = Math.max(1, ...rows.map((r) => Number(r.value)));
  return (
    <section aria-label={title} className="rounded-pane bg-card p-[12px] shadow-e1">
      <h3 className="mb-[8px] text-[12.5px] font-medium">{title}</h3>
      {rows.map((r) => (
        <div key={r.name} className="mb-[8px]">
          <p className="flex justify-between text-[12.5px] font-medium">
            <span>{r.name}</span>
            <span className="tabular-nums">{n(r.value)}</span>
          </p>
          <div className="h-[24px] rounded-[6px] bg-nested">
            <div
              className={cn("h-full rounded-[6px]", r.fill)}
              style={{ width: `${String((Number(r.value) / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </section>
  );
}

function ReconTable({
  s,
  pendingBackSolve,
}: {
  s: WorkbookAllocationStructureOut;
  pendingBackSolve: boolean;
}): JSX.Element {
  const straight = s.kind === "straight_percentage";
  const partners = s.partners ?? [];
  const periods = s.periods ?? [];
  const head = straight
    ? [
        COPY.partner,
        ...periods.map((p) => `${dateOf(p.starts_on)}–${dateOf(p.ends_on)}`),
        COPY.total,
      ]
    : [COPY.partner, COPY.begin, COPY.target, COPY.plug];
  const cell = (p: WorkbookAllocationPartnerOut): string[] =>
    straight
      ? [
          ...periods.map((period) =>
            n(
              (s.results ?? []).find(
                (r) => r.partner_id === p.partner_id && r.period_key === period.key,
              )?.amount,
            ),
          ),
          n(p.total),
        ]
      : pendingBackSolve
        ? [n(p.beginning), COPY.pending, COPY.pending]
        : [n(p.beginning), n(p.target), n(p.total)];
  const totals = straight
    ? [...periods.map((p) => n(p.amount)), n(s.income)]
    : pendingBackSolve
      ? ["", COPY.pending, COPY.pending]
      : ["", n(s.distributable), n(s.income)];
  return (
    <section
      aria-label={straight ? COPY.reconPeriods : COPY.backSolve}
      className="rounded-pane bg-card p-[12px] shadow-e1"
    >
      <h3 className="mb-[8px] text-[12.5px] font-medium">
        {straight ? COPY.reconPeriods : COPY.backSolve}
      </h3>
      <table className="w-full text-[12px] tabular-nums">
        <thead>
          <tr className="h-[30px] bg-band-hd text-ink-2">
            {head.map((h, i) => (
              <th
                key={h}
                className={cn("font-medium", i === 0 ? "w-[152px] text-left" : "text-right")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {partners.map((p) => (
            <tr key={p.partner_id} className="h-[28px]">
              <td>{p.name}</td>
              {cell(p).map((v, i) => (
                <td key={`${p.partner_id}:${String(i)}`} className="text-right">
                  {v}
                </td>
              ))}
            </tr>
          ))}
          <tr className="h-[28px] border-t border-stroke font-medium">
            <td>{COPY.total}</td>
            {totals.map((v, i) => (
              <td key={`t:${String(i)}`} className="text-right">
                {v}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      {!straight && !pendingBackSolve && s.gp_profit_percent != null ? (
        <p className="mt-[6px] text-[11.5px] text-ink-3">
          {COPY.gpShare(String(Number(s.gp_profit_percent)))}
        </p>
      ) : null}
    </section>
  );
}

export function TXP06({
  structure,
  preview,
  open = true,
  forceOpen = false,
  selected = null,
  editing = null,
  approvedBy,
  approvedOn,
  onClose,
  onSelect,
  onEdit,
  onRung,
  onSave,
  onApprove,
  onCitation,
  onItemL,
}: TXP06Props): JSX.Element {
  const s = editing !== null && preview !== undefined ? preview : structure;
  const body =
    s === undefined ? (
      <div className="p-[12px]" />
    ) : (
      <div data-screen="TXP-06" className="flex min-h-0 flex-1 gap-[10px] p-[12px]">
        <Rail
          s={s}
          selected={selected}
          {...(onSelect === undefined ? {} : { onSelect })}
          {...(onApprove === undefined ? {} : { onApprove })}
          {...(onCitation === undefined ? {} : { onCitation })}
          {...(onItemL === undefined ? {} : { onItemL })}
          {...(approvedBy === undefined ? {} : { approvedBy })}
          {...(approvedOn === undefined ? {} : { approvedOn })}
        />
        <Rules
          s={s}
          selected={selected}
          editing={editing}
          {...(onEdit === undefined ? {} : { onEdit })}
          {...(onRung === undefined ? {} : { onRung })}
          {...(onSave === undefined ? {} : { onSave })}
        />
        <div className="flex w-[500px] flex-none flex-col gap-[10px]">
          <Bars
            title={s.kind === "straight_percentage" ? COPY.byPeriod : COPY.cumulative}
            rows={(s.partners ?? []).map((p, i) => ({
              name: p.name,
              value: (s.kind === "straight_percentage" ? p.total : p.target) ?? "0",
              fill: fillOf(i, (s.partners ?? []).length),
            }))}
          />
          <ReconTable s={s} pendingBackSolve={editing !== null} />
        </div>
      </div>
    );
  return (
    <FullSheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose?.();
      }}
      title={COPY.title}
      dirty={editing !== null}
      {...(forceOpen ? { forceState: "open" as const } : {})}
    >
      {body}
    </FullSheet>
  );
}
