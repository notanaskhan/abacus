import type {
  ConsolidationEntityOut,
  ConsolidationOut,
  TrialBalanceSlotOut,
} from "@abacus/api-client";
import {
  groupFinalizeMutation,
  groupGetConsolidationOptions,
  groupMarkNotNeededMutation,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  Icon,
  Menu,
  Pill,
  SearchField,
  Skeleton,
  Tag,
  Tooltip,
  cn,
  date,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useId, useMemo, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { COPY } from "./copy";

// AUD-32 Consolidation setup (A-09-T14; SPEC-658; handoff AUD-32): the O6 wizard over AUD-02, on
// C9 v2.1 (`GET …/consolidations/{id}`). Steps Details · Structure · Trial balances · Review; Next
// stays disabled with its reason while a trial balance is missing; "Mark not needed…" needs a
// reason; Finalize is the manager's (allowed_actions) and never green. Every total is the
// server's (ADR-050); the agent's structure proposal is a suggestion a person uses or edits.

export type Aud32Step = "details" | "structure" | "trial_balances" | "review";
const STEP_ORDER: readonly Aud32Step[] = ["details", "structure", "trial_balances", "review"];
const COLS = "grid grid-cols-[minmax(0,1fr)_92px_92px_92px_72px_120px_104px_28px] items-center";

function day(iso: string): string {
  return date(iso, { now: 0, withYear: true });
}

function slotsOf(c: ConsolidationOut): TrialBalanceSlotOut[] {
  return c.entities.flatMap((e) => e.trial_balances);
}

function done(c: ConsolidationOut): number {
  return slotsOf(c).filter((t) => t.state === "attached" || t.state === "not_needed").length;
}

function Disc({ state }: { state: "done" | "current" | "todo" }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-[18px] shrink-0 items-center justify-center rounded-full",
        state === "done" && "bg-green text-on-dark",
        state === "current" && "inset-ring-[1.5px] inset-ring-ink-2",
        state === "todo" && "inset-ring-[1px] inset-ring-ink-3",
      )}
    >
      {state === "done" && <Icon name="check" size={12} strokeWidth={2.4} />}
    </span>
  );
}

function StepList({
  c,
  step,
  onStep,
}: {
  c: ConsolidationOut;
  step: Aud32Step;
  onStep: (s: Aud32Step) => void;
}): JSX.Element {
  const S = COPY.steps;
  const all = slotsOf(c).length;
  const subs: Record<Aud32Step, string> = {
    details: S.details.sub,
    structure: S.structure.sub(c.entities.length, c.tiers),
    trial_balances: S.trial_balances.sub(done(c), all),
    review: S.review.sub,
  };
  const at = STEP_ORDER.indexOf(step);
  return (
    <nav
      aria-label={COPY.title}
      className="flex w-[220px] shrink-0 flex-col gap-[4px] bg-card px-[12px] py-[16px] shadow-[inset_-1px_0_0_var(--color-hair)]"
    >
      <ol>
        {STEP_ORDER.map((s, i) => (
          <li key={s}>
            <button
              type="button"
              aria-current={s === step ? "step" : undefined}
              disabled={i > at && c.status !== "finalized"}
              onClick={() => {
                onStep(s);
              }}
              className={cn(
                "flex h-[44px] w-full items-center gap-[10px] rounded-[8px] px-[8px] text-left",
                s === step && "bg-sel-bg",
              )}
            >
              <Disc
                state={
                  i < at || c.status === "finalized" ? "done" : s === step ? "current" : "todo"
                }
              />
              <span className="flex flex-col">
                <span className={cn("text-[13px]", s === step && "font-medium")}>
                  {S[s].label}
                </span>
                <span className="text-[11.5px] text-ink-3">{subs[s]}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <p className="mt-[10px] rounded-[10px] bg-shell px-[12px] py-[10px] text-[11.5px] leading-[1.45] text-ink-2">
        {COPY.note}
      </p>
    </nav>
  );
}

function SlotStatus({ t }: { t: TrialBalanceSlotOut }): JSX.Element | null {
  if (t.state === "attached") {
    return (
      <Pill variant="green-tint" check>
        {COPY.balanced}
      </Pill>
    );
  }
  if (t.state === "needs_reauth") return <Pill variant="amber">{COPY.needsReauth}</Pill>;
  if (t.state === "not_needed") return <Pill variant="muted">{COPY.notNeeded}</Pill>;
  return null;
}

function SlotRow({
  t,
  depth,
  onMissing,
}: {
  t: TrialBalanceSlotOut;
  depth: number;
  onMissing: (t: TrialBalanceSlotOut) => void;
}): JSX.Element {
  const indent = { paddingLeft: `${String(16 * (depth + 1) + 14)}px` };
  if (t.state === "missing") {
    return (
      <div
        role="row"
        data-slot={t.id}
        data-state="missing"
        className={cn(COLS, "h-[34px] hairline-b")}
      >
        <span
          role="cell"
          style={indent}
          className="flex items-center gap-[8px] text-[12.5px] text-ink-3" // ink-4 fails AA for content (axe, J20 2)
        >
          {COPY.noTb}
          <span>{`${COPY.labels[t.label] ?? t.label} · ${day(t.period_end)}`}</span>
        </span>
        <span role="cell" className="col-span-6" />
        <span role="cell">
          <Menu
            label={COPY.add}
            trigger={<Button variant="ghost" size="sm">{`+ ${COPY.add}`}</Button>}
            width={260}
            sections={[
              [
                {
                  label: COPY.addMenu.upload[0],
                  hint: COPY.addMenu.upload[1],
                  icon: "upload",
                  onSelect: () => {
                    onMissing(t);
                  },
                },
                {
                  label: COPY.addMenu.connection[0],
                  hint: COPY.addMenu.connection[1],
                  icon: "refresh-cw",
                  onSelect: () => {
                    onMissing(t);
                  },
                },
                {
                  label: COPY.addMenu.evidence[0],
                  hint: COPY.addMenu.evidence[1],
                  icon: "file-search",
                  onSelect: () => {
                    onMissing(t);
                  },
                },
              ],
            ]}
          />
        </span>
      </div>
    );
  }
  return (
    <div
      role="row"
      data-slot={t.id}
      data-state={t.state}
      className={cn(COLS, "h-[34px] text-[12px] hairline-b")}
    >
      <span role="cell" style={indent} className="flex items-center gap-[6px] text-[12.5px]">
        <Icon name="link-2" size={12} className="text-ink-3" />
        {t.file_name ?? "—"}
      </span>
      <span role="cell">
        <Pill variant={t.label === "interim" ? "amber" : "neutral"}>
          {COPY.labels[t.label] ?? t.label}
        </Pill>
      </span>
      <span role="cell" className="tabular-nums">
        {day(t.period_start)}
      </span>
      <span role="cell" className="tabular-nums">
        {day(t.period_end)}
      </span>
      <span role="cell">{COPY.period[t.period_kind]}</span>
      <span role="cell" className="text-right">
        {t.total_debits === null ? (
          <Tooltip content={COPY.priorDash}>
            <span tabIndex={0}>—</span>
          </Tooltip>
        ) : (
          <Amount value={t.total_debits} style="whole" />
        )}
      </span>
      <span role="cell">
        <SlotStatus t={t} />
      </span>
      <span role="cell" />
    </div>
  );
}

function EntityRows({
  e,
  onMissing,
}: {
  e: ConsolidationEntityOut;
  onMissing: (t: TrialBalanceSlotOut) => void;
}): JSX.Element {
  const depth = e.level - 1;
  const reauth = e.trial_balances.some((t) => t.state === "needs_reauth");
  return (
    <>
      <div role="row" data-entity={e.client_entity_id} className={cn(COLS, "h-[38px] hairline-b")}>
        <span
          role="cell"
          style={{ paddingLeft: `${String(16 * depth + 10)}px` }}
          className="flex items-center gap-[8px]"
        >
          <Icon name="building-2" size={14} className="text-ink-2" />
          <span className="text-[13px] font-medium">{e.name}</span>
          <span className="text-[11.5px] text-ink-3">
            {`${e.level === 1 ? COPY.parent : COPY.owned}${e.city === null ? "" : ` · ${e.city}`}`}
          </span>
          {e.component_auditor_name !== null && (
            <Tag>{`Component auditor · ${e.component_auditor_name}`}</Tag>
          )}
        </span>
        <span role="cell" className="col-span-7" />
      </div>
      {e.trial_balances.map((t) => (
        <SlotRow key={t.id} t={t} depth={depth} onMissing={onMissing} />
      ))}
      {reauth && (
        <div
          role="row"
          className="flex items-center gap-[10px] py-[6px] text-[11.5px] text-ink-3 hairline-b"
          style={{ paddingLeft: `${String(16 * (depth + 1) + 14)}px` }}
        >
          <span>{COPY.reauthHelp}</span>
          <Button variant="ghost" size="sm">
            {COPY.requestReconnection}
          </Button>
        </div>
      )}
    </>
  );
}

function TrialBalances({
  c,
  onMissing,
}: {
  c: ConsolidationOut;
  onMissing: (t: TrialBalanceSlotOut) => void;
}): JSX.Element {
  const [query, setQuery] = useState("");
  const shown = c.entities.filter((e) => e.name.toLowerCase().includes(query.toLowerCase()));
  return (
    <section data-step="trial_balances" className="flex flex-col gap-[12px]">
      <h2 className="text-[15px] font-medium">{COPY.tbTitle}</h2>
      <p className="text-[12.5px] leading-[1.5] text-ink-2">{COPY.tbIntro}</p>
      <div className="flex h-[36px] items-center gap-[8px]">
        <SearchField label={COPY.search} value={query} onChange={setQuery} className="w-[220px]" />
        <span className="ml-auto" />
        <Button variant="secondary" size="sm">
          {COPY.pullAll}
        </Button>
        <Button variant="ghost" size="sm">
          {COPY.bulk}
        </Button>
      </div>
      <div
        role="table"
        aria-label={COPY.tbTitle}
        className="overflow-hidden rounded-pane bg-card shadow-e1"
      >
        <div
          role="row"
          className={cn(COLS, "h-[30px] bg-nested text-[11.5px] font-medium text-ink-3")}
        >
          {COPY.columns.map((h, i) => (
            <span
              key={h}
              role="columnheader"
              className={cn(i === 0 && "pl-[10px]", i === 5 && "text-right")}
            >
              {h}
            </span>
          ))}
          <span role="columnheader" />
        </div>
        {shown.map((e) => (
          <EntityRows key={e.id} e={e} onMissing={onMissing} />
        ))}
      </div>
      <p className="text-[11.5px] text-ink-3">{COPY.source}</p>
    </section>
  );
}

function Details({ c }: { c: ConsolidationOut }): JSX.Element {
  const D = COPY.details;
  const rows: [string, [string, string][]][] = [
    [
      D.consolidation,
      [
        [D.name, c.name],
        [D.engagement, D.engagementValue],
        [D.yearEnd, day(c.year_end)],
        [D.currency, c.reporting_currency],
      ],
    ],
    [
      D.periods,
      [
        [D.interim, D.interimValue],
        [D.prior, D.priorValue],
      ],
    ],
    [
      D.source,
      [
        [D.source, D.sourceValue],
        [D.labels, D.labelsValue],
      ],
    ],
  ];
  return (
    <section data-step="details" className="flex flex-col gap-[14px]">
      {rows.map(([legend, kv]) => (
        <fieldset key={legend} className="rounded-pane bg-card px-[14px] py-[10px] shadow-e1">
          <legend className="text-[13px] font-medium">{legend}</legend>
          <dl>
            {kv.map(([k, v]) => (
              <div
                key={k}
                className="flex h-[33px] items-center gap-[12px] text-cell hairline-b last:shadow-none"
              >
                <dt className="w-[140px] text-ink-2">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </fieldset>
      ))}
    </section>
  );
}

function Structure({ c }: { c: ConsolidationOut }): JSX.Element {
  const S = COPY.structure;
  return (
    <section data-step="structure" className="flex flex-col gap-[12px]">
      <div
        data-agent-banner
        className="flex items-center gap-[10px] rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1"
      >
        <Icon name="atom" size={12} className="text-ink-2" />
        <p className="flex-1 text-[12.5px] text-ink-2">{S.banner}</p>
        <Button variant="secondary" size="sm">
          {S.use}
        </Button>
        <Button variant="ghost" size="sm">
          {S.edit}
        </Button>
      </div>
      <ul
        aria-label={COPY.steps.structure.label}
        className="overflow-hidden rounded-pane bg-card shadow-e1"
      >
        {c.entities.map((e) => (
          <li
            key={e.id}
            data-entity={e.client_entity_id}
            className="flex h-[38px] items-center gap-[8px] hairline-b"
            style={{ paddingLeft: `${String(16 * (e.level - 1) + 10)}px` }}
          >
            <Icon name="grip-vertical" size={12} className="text-ink-3" />
            <Icon name="building-2" size={14} className="text-ink-2" />
            <span className="text-[13px] font-medium">{e.name}</span>
            <span className="text-[11.5px] text-ink-3">{COPY.owned}</span>
          </li>
        ))}
      </ul>
      <Button variant="ghost" size="sm" className="self-start">
        {`+ ${S.addEntity}`}
      </Button>
    </section>
  );
}

function Review({ c }: { c: ConsolidationOut }): JSX.Element {
  const R = COPY.review;
  const names = new Map(c.entities.map((e) => [e.id, e.name]));
  return (
    <section data-step="review" className="flex flex-col gap-[12px]">
      <p
        data-review-summary
        className="rounded-pane bg-card px-[14px] py-[10px] text-[13px] font-medium shadow-e1"
      >
        {R.summary(c.entities.length, c.tiers, slotsOf(c).length)}
      </p>
      <table className="w-full border-collapse overflow-hidden rounded-pane bg-card shadow-e1">
        <caption className="sr-only">{COPY.steps.review.label}</caption>
        <thead>
          <tr className="h-[30px] bg-nested text-[11.5px] text-ink-3">
            {R.columns.map((h, i) => (
              <th
                key={h}
                scope="col"
                className={cn("px-[10px] font-medium", i === 3 ? "text-right" : "text-left")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {c.entities.map((e) => {
            const interim = e.trial_balances.find((t) => t.period_kind === "current");
            return (
              <tr key={e.id} className="h-[34px] text-cell hairline-b">
                <th scope="row" className="px-[10px] text-left font-normal">
                  {e.name}
                </th>
                <td className="px-[10px]">{e.level}</td>
                <td className="px-[10px]">
                  {e.parent_id === null ? "—" : names.get(e.parent_id)}
                </td>
                <td className="px-[10px] text-right">
                  {interim?.total_debits ? (
                    <Amount value={interim.total_debits} style="whole" />
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-[10px]">
                  <Icon name="check" size={12} className="text-green-ink" />
                </td>
                <td className="px-[10px]">{e.component_auditor_name ?? ""}</td>
              </tr>
            );
          })}
          <tr className="h-[34px] text-cell font-medium">
            <th scope="row" className="px-[10px] text-left font-medium">
              {R.total}
            </th>
            <td colSpan={2} />
            <td className="px-[10px] text-right" data-total>
              <Amount value={c.interim_total_debits} style="whole" />
            </td>
            <td colSpan={2} />
          </tr>
        </tbody>
      </table>
    </section>
  );
}

export interface Aud32Props {
  workItemId: string;
  consolidationId: string;
  step?: Aud32Step;
  onClose?: () => void;
}

export function AUD32({
  workItemId,
  consolidationId,
  step: initial = "trial_balances",
  onClose,
}: Aud32Props): JSX.Element {
  const path = { work_item_id: workItemId, consolidation_id: consolidationId };
  const client = useQueryClient();
  const openOverlay = useOpenOverlay();
  const read = useQuery(groupGetConsolidationOptions({ path }));
  const [step, setStep] = useState<Aud32Step>(initial);
  const [reasonFor, setReasonFor] = useState<TrialBalanceSlotOut | null>(null);
  const [reason, setReason] = useState("");
  const reasonId = useId();
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey: groupGetConsolidationOptions({ path }).queryKey });
  };
  const notNeeded = useMutation({ ...groupMarkNotNeededMutation(), onSuccess: refresh });
  const finalize = useMutation({
    ...groupFinalizeMutation(),
    onSuccess: () => {
      toast.show({
        kind: "success",
        text: COPY.toast,
        action: COPY.view,
        onAction: () => {
          openOverlay(ov.AUD33(workItemId, consolidationId));
        },
      });
      refresh();
    },
  });
  const c = read.data;
  const missing = useMemo(() => (c === undefined ? [] : c.missing), [c]);
  if (c === undefined) return <Skeleton className="m-[24px] h-[480px]" />;
  const all = slotsOf(c).length;
  const firstMissing = slotsOf(c).find((t) => t.state === "missing") ?? null;
  const canNext = step !== "trial_balances" || missing.length === 0;
  const at = STEP_ORDER.indexOf(step);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={COPY.title}
      data-aud32={step}
      data-status={c.status}
      className="flex h-full flex-col overflow-hidden rounded-[14px] bg-shell shadow-modal"
    >
      <header className="flex h-[46px] items-center justify-center gap-[8px] bg-card hairline-b">
        <h1 className="text-[14.5px] font-medium">{COPY.title}</h1>
        <span className="text-[11.5px] text-ink-3">{COPY.subtitle}</span>
        {c.status === "finalized" && (
          <Pill variant="green-tint" check>
            {COPY.finalized}
          </Pill>
        )}
        <span className="absolute right-[24px]">
          <Button variant="ghost" size="sm" aria-label={COPY.close} onClick={onClose}>
            <Icon name="x" size={14} />
          </Button>
        </span>
      </header>
      <div className="flex min-h-0 flex-1">
        <StepList c={c} step={step} onStep={setStep} />
        <div className="min-w-0 flex-1 overflow-auto px-[22px] py-[18px]">
          {step === "details" && <Details c={c} />}
          {step === "structure" && <Structure c={c} />}
          {step === "trial_balances" && <TrialBalances c={c} onMissing={setReasonFor} />}
          {step === "review" && <Review c={c} />}
          {reasonFor !== null && (
            <form
              data-not-needed
              className="mt-[12px] flex items-end gap-[8px] rounded-pane bg-card p-[12px] shadow-e1"
              onSubmit={(event) => {
                event.preventDefault();
                notNeeded.mutate({
                  path: { ...path, tb_id: reasonFor.id },
                  body: { reason: reason.trim() },
                });
                setReasonFor(null);
                setReason("");
              }}
            >
              <label htmlFor={reasonId} className="flex flex-1 flex-col gap-[4px] text-cell">
                {COPY.reason}
                <input
                  id={reasonId}
                  required
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                  }}
                  className="h-[32px] rounded-input bg-card px-[8px] inset-ring-[0.5px] inset-ring-stroke"
                />
              </label>
              <Button type="submit" variant="primary" disabled={reason.trim() === ""}>
                {COPY.confirmNotNeeded}
              </Button>
            </form>
          )}
        </div>
      </div>
      <footer className="flex h-[56px] items-center gap-[8px] bg-card px-[16px] shadow-[inset_0_1px_0_var(--color-hair)]">
        <Button
          variant="secondary"
          disabled={at === 0}
          onClick={() => {
            setStep(STEP_ORDER[Math.max(0, at - 1)] ?? "details");
          }}
        >
          {COPY.back}
        </Button>
        <p data-footer className="flex-1 text-center text-[12.5px] text-ink-3">
          {step === "review" ? COPY.review.hint : COPY.footer(done(c), all, missing)}
        </p>
        {step === "trial_balances" && firstMissing !== null && (
          <Button
            variant="ghost"
            onClick={() => {
              setReasonFor(firstMissing);
            }}
          >
            {COPY.markNotNeeded}
          </Button>
        )}
        {step === "review" ? (
          <Button
            variant="primary"
            disabled={!c.allowed_actions.includes("consolidation.finalize") || finalize.isPending}
            onClick={() => {
              finalize.mutate({
                path,
                body: { seen_version: c.row_version },
                headers: {
                  "Idempotency-Key": `finalize-${consolidationId}-${String(c.row_version)}`,
                },
              });
            }}
          >
            {COPY.review.finalize}
          </Button>
        ) : (
          <Tooltip content={canNext ? COPY.next : COPY.nextReason}>
            <span tabIndex={canNext ? -1 : 0}>
              <Button
                variant="primary"
                disabled={!canNext}
                onClick={() => {
                  setStep(STEP_ORDER[at + 1] ?? "review");
                }}
              >
                {COPY.next}
              </Button>
            </span>
          </Tooltip>
        )}
      </footer>
    </div>
  );
}
