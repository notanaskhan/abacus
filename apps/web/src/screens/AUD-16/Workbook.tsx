import type {
  EntryOut,
  SumOut,
  SumRowOut,
  AbacusModulesAssuranceFindingsContractMisstatementOut as MisstatementOut,
} from "@abacus/api-client";
import {
  misstatementsOptions,
  proposedEntriesOptions,
  sumOptions,
  sumRequestConclusionMutation,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  Icon,
  PaneAction,
  Pill,
  Segmented,
  ViewStateBody,
  type ViewState,
  amount,
  cn,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useEntitlement } from "../../app-core/flags";
import { COPY } from "./copy";

// AUD-16 · Misstatements & adjustments (A-06-T22; A-06 §3 F3, F4; the handoff spec): the T6 workbook
// under the Evaluation tabs. The control bar's segmented views (Proposed AJEs · Reclassifications ·
// Passed (SUM) · Below CT) carry the server's counts; the tally strip, the SUM statement table and
// the evaluation pane render `GET …/sum` (A-06-T13) and compute nothing (ADR-050): parentheses for
// negatives, "—" for nil, no "$" in any table. The AJE and RJE lists are C8's proposed entries in
// the bento entry-list grammar (the one place "$" appears); Below CT lists the logged items. The
// threshold bar is a bar, never a donut; approaching PM turns the fill and the AGGREGATE card amber.
// Request conclusion… raises the reserved `sum_conclusion` card; Send to client… opens O3
// (`?ov=send-entries`). Nothing here posts or books.

export type MisstatementView = "proposed" | "reclass" | "passed" | "below_ct";
const VIEWS: readonly MisstatementView[] = ["proposed", "reclass", "passed", "below_ct"];

const CARD =
  "flex h-[40px] flex-1 flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1";
const LABEL = "text-micro font-medium uppercase tracking-[.07em] text-ink-3";
const COLS = "grid grid-cols-[64px_300px_96px_92px_92px_112px_112px_88px] items-center gap-[0px]";

const whole = (v: string | null | undefined): string => amount(v ?? "", "whole").text;

export interface WorkbookProps {
  /** The assurance work item (`$auditId`). */
  auditId: string;
  view: MisstatementView;
  onView: (view: MisstatementView) => void;
  /** F-07 → AUD-15 with that finding selected. */
  onFinding?: (ref: string) => void;
  /** O3 over the entries still to send. */
  onSend?: (entryIds: readonly string[]) => void;
  /** SHL-11 on the raised `sum_conclusion` card. */
  onDecision?: (cardId: string) => void;
  onSignOff?: () => void;
}

function Tally({ sum }: { sum: SumOut }): JSX.Element | null {
  const t = sum.thresholds;
  if (t === null || t === undefined) return null;
  const warn = sum.approaching_pm || sum.above_pm;
  return (
    <div data-aud16="tally" className="flex h-[52px] items-center gap-[8px] px-[12px]">
      <div className={CARD} data-tally="ct">
        <span className={LABEL}>{COPY.tally.ct}</span>
        <Amount value={t.ct} style="whole" className="text-[15px]" />
      </div>
      <div className={CARD} data-tally="pm">
        <span className={LABEL}>{COPY.tally.pm}</span>
        <Amount value={t.pm} style="whole" className="text-[15px]" />
      </div>
      <div className={CARD} data-tally="overall">
        <span className={LABEL}>{COPY.tally.overall}</span>
        <span className="flex items-center gap-[6px] text-[15px]">
          <Amount value={t.overall} style="whole" />
          {t.label !== null && (
            <Pill variant="tag" size="tally">
              {t.label}
            </Pill>
          )}
        </span>
      </div>
      <div className={CARD} data-tally="rollover">
        <span className={LABEL}>{COPY.tally.rollover}</span>
        <Amount value={sum.rollover} style="whole" className="text-[15px]" />
      </div>
      <div className={CARD} data-tally="iron_curtain">
        <span className={LABEL}>{COPY.tally.ironCurtain}</span>
        <Amount value={sum.iron_curtain} style="whole" className="text-[15px]" />
      </div>
      <div
        className={cn(CARD, warn && "bg-amber-tint")}
        data-tally="aggregate"
        data-warn={warn ? "true" : "false"}
      >
        <span className={cn(LABEL, "flex items-center gap-[4px]")}>
          {warn && <Icon name="triangle-alert" size={12} />}
          {COPY.tally.aggregate}
        </span>
        <span className="flex items-center gap-[6px] text-[15px] tabular-nums">
          {`${sum.pct_of_pm}%`}
          <Pill variant={sum.above_pm ? "red-tint" : warn ? "amber" : "green-tint"} size="tally">
            {sum.above_pm
              ? COPY.tally.abovePm
              : warn
                ? COPY.tally.approaching
                : COPY.tally.belowPm}
          </Pill>
        </span>
      </div>
    </div>
  );
}

function SumRow({
  row,
  onFinding,
}: {
  row: SumRowOut;
  onFinding?: ((ref: string) => void) | undefined;
}): JSX.Element {
  const prior = row.group === "prior_year";
  const cell = (v: string | null | undefined): JSX.Element => (
    <Amount value={v ?? ""} style="whole" className="pr-[10px] text-right" />
  );
  return (
    <div
      data-sum-row={row.ref}
      className={cn(COLS, "min-h-[34px] text-dense hairline-b", prior && "text-ink-3")}
    >
      <span className="px-[10px]">{row.ref}</span>
      <span className="flex min-w-0 flex-col py-[6px]">
        <span className="truncate">{row.description}</span>
        {row.client_note !== null && (
          <span className="truncate text-meta text-ink-3">
            {row.finding_ref !== null && (
              <>
                {onFinding === undefined ? (
                  row.finding_ref
                ) : (
                  <button
                    type="button"
                    className="font-medium text-ink-2"
                    onClick={() => {
                      onFinding(row.finding_ref as string);
                    }}
                  >
                    {row.finding_ref}
                  </button>
                )}
                {" · "}
              </>
            )}
            {[row.workpaper_ref, row.client_note].filter((t) => t !== null).join(" · ")}
          </span>
        )}
      </span>
      <span>
        <Pill variant="tag" size="sm" data-type={row.type}>
          {COPY.type[row.type] ?? row.type}
        </Pill>
      </span>
      {cell(row.assets)}
      {cell(row.liabilities)}
      {cell(row.net_assets)}
      {cell(row.change_in_net_assets)}
      {cell(row.carried_from_py)}
    </div>
  );
}

function SumTable({
  sum,
  onFinding,
  onSignOff,
}: {
  sum: SumOut;
  onFinding?: ((ref: string) => void) | undefined;
  onSignOff?: (() => void) | undefined;
}): JSX.Element {
  const C = COPY.sum.columns;
  const rows = sum.rows ?? [];
  const current = rows.filter((r) => r.group === "current");
  const prior = rows.filter((r) => r.group === "prior_year");
  const t = sum.totals;
  const head = "px-[10px] text-[11.5px] font-medium text-ink-3";
  return (
    <section
      data-aud16="sum"
      className="flex min-h-0 flex-1 flex-col rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[46px] shrink-0 items-center gap-[6px] px-[14px] hairline-b">
        <h2 className="flex-1 text-[14.5px] font-medium">{COPY.sum.title}</h2>
        <PaneAction icon="pencil" label={COPY.sum.edit} />
        <PaneAction
          icon="check"
          label={COPY.sum.signOff}
          {...(onSignOff === undefined ? { disabled: true } : { onClick: onSignOff })}
        />
        <PaneAction icon="file" label={COPY.sum.sourceDocs} />
      </header>
      <div className="min-h-0 flex-1 overflow-auto">
        <div role="row" className={cn(COLS, "h-[30px] bg-nested hairline-b")}>
          <span className={head}>{C.ref}</span>
          <span className={head}>{C.description}</span>
          <span className={head}>{C.type}</span>
          <span className={cn(head, "text-right")}>{C.assets}</span>
          <span className={cn(head, "text-right")}>{C.liabilities}</span>
          <span className={cn(head, "text-right")}>{C.net_assets}</span>
          <span className={cn(head, "text-right")}>{C.change}</span>
          <span className={cn(head, "text-right")}>{C.py}</span>
        </div>
        <p className="flex h-[24px] items-center px-[10px] text-meta text-ink-3">
          {COPY.sum.note}
        </p>
        <p className={cn(LABEL, "flex h-[24px] items-center px-[10px]")}>{COPY.sum.current}</p>
        {current.map((r) => (
          <SumRow key={r.ref} row={r} onFinding={onFinding} />
        ))}
        {t !== null && t !== undefined && (
          <div
            data-aud16="total"
            className={cn(
              COLS,
              "h-[34px] border-t-[0.5px] border-b-[3px] border-double border-stroke text-dense font-medium",
            )}
          >
            <span className="col-span-3 px-[10px]">{COPY.sum.total}</span>
            {[
              t.assets,
              t.liabilities,
              t.net_assets,
              t.change_in_net_assets,
              t.carried_from_py,
            ].map((v, i) => (
              <Amount key={i} value={v ?? ""} style="whole" className="pr-[10px] text-right" />
            ))}
          </div>
        )}
        {prior.length > 0 && (
          <>
            <p className={cn(LABEL, "flex h-[24px] items-center px-[10px] text-ink-3")}>
              {COPY.sum.prior}
            </p>
            {prior.map((r) => (
              <SumRow key={r.ref} row={r} />
            ))}
          </>
        )}
        {sum.footnote !== null && sum.footnote !== undefined && (
          <p data-aud16="footnote" className="px-[14px] py-[10px] text-[11.5px] text-ink-3">
            {sum.footnote}
          </p>
        )}
      </div>
      {sum.sign_off !== null && sum.sign_off !== undefined && (
        <footer
          data-aud16="sign-off"
          className="flex h-[30px] shrink-0 items-center gap-[12px] px-[14px] text-meta text-ink-3 hairline-t"
        >
          {sum.sign_off.prepared_label !== null && sum.sign_off.prepared_label !== undefined && (
            <span className="flex items-center gap-[4px]">
              <Icon name="check" size={12} />
              {sum.sign_off.prepared_label}
            </span>
          )}
          <span
            className="flex items-center gap-[4px]"
            data-partner-signed={sum.sign_off.partner_signed}
          >
            {sum.sign_off.partner_signed ? (
              <Icon name="check" size={12} />
            ) : (
              <span aria-hidden>○</span>
            )}
            {sum.sign_off.partner_label ?? COPY.sum.awaitingPartner}
          </span>
        </footer>
      )}
    </section>
  );
}

function Entries({
  entries,
  onSend,
}: {
  entries: readonly EntryOut[];
  onSend?: ((ids: readonly string[]) => void) | undefined;
}): JSX.Element {
  const [open, setOpen] = useState<string | null>(null);
  const toSend = entries.filter(
    (e) =>
      e.status === "review_required" &&
      e.allowed_actions.includes("proposed_entry.send_to_client"),
  );
  return (
    <section data-aud16="entries" className="flex flex-col gap-[10px]">
      <ul className="flex flex-col rounded-[12px] bg-card shadow-e1">
        {entries.map((e) => {
          const done = e.status === "client_approved" || e.status === "approved";
          return (
            <li
              key={e.id}
              data-entry={e.ref}
              data-status={e.status}
              className="hairline-b last:shadow-none"
            >
              <button
                type="button"
                aria-expanded={open === e.id}
                className="flex min-h-[52px] w-full items-center gap-[10px] px-[14px] text-left"
                onClick={() => {
                  setOpen(open === e.id ? null : e.id);
                }}
              >
                <span
                  aria-hidden
                  className={cn(
                    "flex size-[22px] shrink-0 items-center justify-center rounded-full",
                    done ? "bg-green text-on-dark" : "inset-ring-[1.5px] inset-ring-ink-4",
                  )}
                >
                  {done && <Icon name="check" size={12} />}
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-dense">{`${e.ref} · ${e.description ?? ""}`}</span>
                  <span className="truncate text-meta text-ink-3">
                    {e.status === "review_required"
                      ? COPY.entries.reviewRequired
                      : (e.approval_label ?? "")}
                  </span>
                </span>
                {/* The entry list is the one place "$" appears (bento grammar); tables never. */}
                <span className="text-[13.5px] font-medium tabular-nums" data-entry-amount>
                  {`$${whole(e.amount)}`}
                </span>
                <Icon name={open === e.id ? "chevron-up" : "chevron-down"} size={12} />
              </button>
              {open === e.id && (
                <table
                  aria-label={COPY.entries.lines(e.ref)}
                  className="mx-[14px] mb-[10px] text-meta"
                >
                  <tbody>
                    {e.lines.map((l) => {
                      const dr = amount(l.debit, "whole").tone !== "zero";
                      return (
                        <tr key={l.line_no} className="h-[22px]">
                          <td className="w-[28px] text-ink-3">
                            {dr ? COPY.entries.dr : COPY.entries.cr}
                          </td>
                          <td className="w-[48px] tabular-nums">{l.account_code}</td>
                          <td className="w-[360px] truncate">{l.account_name ?? ""}</td>
                          <td className="text-right">
                            <Amount value={dr ? l.debit : l.credit} style="whole" />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </li>
          );
        })}
      </ul>
      <p className="text-[11.5px] text-ink-3">{COPY.entries.policy}</p>
      {onSend !== undefined && (
        <Button
          variant="primary"
          size="lg"
          className="w-full"
          disabled={toSend.length === 0}
          onClick={() => {
            onSend(toSend.map((e) => e.id));
          }}
        >
          {toSend.length === 0 ? COPY.allSent : COPY.sendToClient}
        </Button>
      )}
    </section>
  );
}

function BelowCt({ items }: { items: readonly MisstatementOut[] }): JSX.Element {
  return (
    <ul data-aud16="below-ct" className="flex flex-col rounded-[12px] bg-card shadow-e1">
      {items.map((m) => (
        <li
          key={m.id}
          data-below-ct={m.ref}
          className="flex min-h-[44px] items-center gap-[10px] px-[14px] text-dense hairline-b"
        >
          <span className="min-w-0 flex-1 truncate">{`${m.ref} · ${m.description ?? ""}`}</span>
          <Pill variant="tag" size="sm">
            {COPY.type[m.type] ?? m.type}
          </Pill>
          <Amount value={m.amount} style="whole" />
          <span className="text-meta text-ink-3">{COPY.belowCt.logged}</span>
        </li>
      ))}
    </ul>
  );
}

function Evaluation({
  sum,
  auditId,
  onDecision,
}: {
  sum: SumOut;
  auditId: string;
  onDecision?: ((cardId: string) => void) | undefined;
}): JSX.Element {
  const fmt = useFormat();
  const t = sum.thresholds;
  const warn = sum.approaching_pm || sum.above_pm;
  const request = useMutation({
    ...sumRequestConclusionMutation(),
    onSuccess: (out) => {
      onDecision?.(out.decision_card_id);
    },
  });
  const c = sum.conclusion;
  const canRequest = (sum.allowed_actions ?? []).includes("sum.request_conclusion");
  return (
    <section
      data-aud16="evaluation"
      className="flex w-[410px] shrink-0 flex-col overflow-y-auto rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[46px] shrink-0 items-center justify-center text-[14.5px] font-medium hairline-b">
        {COPY.evaluation.title}
      </header>
      {t !== null && t !== undefined && (
        <div data-aud16="threshold-bar" className="flex flex-col gap-[6px] p-[14px]">
          <div className="flex justify-between text-[11.5px] text-ink-3">
            <span>{COPY.evaluation.zero}</span>
            <span>{whole(t.overall)}</span>
          </div>
          <div className="relative h-[6px] rounded-full bg-chip">
            <div
              data-fill={sum.fill_pct_of_overall}
              className={cn(
                "absolute inset-y-0 left-0 rounded-full",
                warn ? "bg-amber" : "bg-espresso",
              )}
              style={{ width: `${sum.fill_pct_of_overall}%` }}
            />
            {[
              [sum.ct_tick_pct, COPY.evaluation.ct(whole(t.ct))],
              [sum.pm_tick_pct, COPY.evaluation.pm(whole(t.pm))],
            ].map(([at, label]) => (
              <span
                key={label}
                data-tick={label}
                className="absolute -top-[3px] h-[12px] w-px bg-ink-3"
                style={{ left: `${at ?? "0"}%` }}
              />
            ))}
          </div>
          <div className="relative h-[14px] text-micro text-ink-3">
            <span className="absolute" style={{ left: `${sum.ct_tick_pct}%` }}>
              {COPY.evaluation.ct(whole(t.ct))}
            </span>
            <span className="absolute -translate-x-1/2" style={{ left: `${sum.pm_tick_pct}%` }}>
              {COPY.evaluation.pm(whole(t.pm))}
            </span>
            <span className="absolute right-0">{COPY.evaluation.overall(whole(t.overall))}</span>
          </div>
          <p data-aud16="caption" className="text-[12.5px] text-ink-2">
            {COPY.evaluation.caption(
              whole(sum.aggregate),
              COPY.evaluation.view[sum.aggregate_view ?? "rollover"] ?? "",
              sum.pct_of_pm,
              sum.below_ct_count ?? 0,
              whole(sum.below_ct_total),
            )}
          </p>
        </div>
      )}
      {(sum.factors ?? []).length > 0 && (
        <fieldset data-aud16="factors" className="px-[14px] pb-[10px]">
          <legend className={cn(LABEL, "pb-[4px]")}>{COPY.evaluation.factors}</legend>
          {(sum.factors ?? []).map((f) => (
            <div
              key={f.factor}
              data-factor={f.factor}
              className="flex h-[34px] items-center gap-[8px] hairline-b"
            >
              <span className="flex-1 truncate text-[12.5px]">{f.label}</span>
              <span
                className={cn(
                  "truncate text-[12.5px]",
                  f.flagged ? "text-amber-ink" : "text-ink-2",
                )}
              >
                {f.value}
              </span>
            </div>
          ))}
        </fieldset>
      )}
      {(sum.booked ?? []).length > 0 && (
        <fieldset data-aud16="booked" className="px-[14px] pb-[10px]">
          <legend className={cn(LABEL, "pb-[4px]")}>{COPY.evaluation.booked}</legend>
          {(sum.booked ?? []).map((b) => (
            <div
              key={b.ref}
              data-booked={b.ref}
              className="flex h-[34px] items-center gap-[8px] hairline-b text-[12.5px]"
            >
              <span className="min-w-0 flex-1 truncate">{`${b.ref} ${b.description}`}</span>
              <Amount value={b.amount} style="whole" />
              {b.approval_label !== null && (
                <Pill variant="green" size="sm">
                  {b.approval_label}
                </Pill>
              )}
            </div>
          ))}
        </fieldset>
      )}
      {c !== null && c !== undefined && (
        <div
          data-aud16="decision"
          data-state={c.state}
          className={cn(
            "mx-[14px] mb-[14px] flex flex-col gap-[8px] rounded-[10px] p-[12px] shadow-e1",
            c.state === "concluded" ? "bg-green-tint" : "bg-card",
          )}
        >
          <p className="text-[12.5px] font-medium">{COPY.evaluation.question}</p>
          {c.state === "concluded" ? (
            <p className="text-[12.5px] text-green-ink">
              {COPY.evaluation.concluded(
                c.outcome_label ?? "",
                c.decided_by_name ?? "",
                c.decided_at === null || c.decided_at === undefined
                  ? ""
                  : fmt.dateTime(c.decided_at),
              )}
            </p>
          ) : (
            <div className="flex items-center gap-[8px]">
              {c.reserved_user_name !== null && c.reserved_user_name !== undefined && (
                <span className="flex-1 text-[12.5px] text-amber-ink">
                  {COPY.evaluation.awaiting(c.reserved_user_name)}
                </span>
              )}
              {canRequest && c.state === "not_requested" && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={request.isPending}
                  onClick={() => {
                    request.mutate({
                      path: { work_item_id: auditId },
                      headers: { "Idempotency-Key": crypto.randomUUID() },
                    });
                  }}
                >
                  {COPY.evaluation.requestConclusion}
                </Button>
              )}
              {c.state === "awaiting" && c.decision_card_id && onDecision !== undefined && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    onDecision(c.decision_card_id as string);
                  }}
                >
                  {COPY.evaluation.requestConclusion}
                </Button>
              )}
            </div>
          )}
          {/* AUD-21 lands with A-07 (planned link: text only, no target). */}
          <p className="text-[12.5px] font-medium" data-planned-link="AUD-21">
            {COPY.evaluation.attach} <span className="text-ink-3">→</span>
          </p>
        </div>
      )}
    </section>
  );
}

export function MisstatementsWorkbook({
  auditId,
  view,
  onView,
  onFinding,
  onSend,
  onDecision,
  onSignOff,
}: WorkbookProps): JSX.Element {
  // A-06-T37 (DEC-2714): the `assurance_completion` entitlement replaces `adjustments.entries`.
  const on = useEntitlement("assurance_completion");
  const sum = useQuery({ ...sumOptions({ path: { work_item_id: auditId } }), enabled: on });
  const kind = view === "reclass" ? "rje" : "aje";
  const entries = useQuery({
    ...proposedEntriesOptions({ path: { work_item_id: auditId }, query: { kind } }),
    enabled: on && (view === "proposed" || view === "reclass"),
  });
  const belowCt = useQuery({
    ...misstatementsOptions({ path: { work_item_id: auditId }, query: { view: "below_ct" } }),
    enabled: on && view === "below_ct",
  });
  const counts = sum.data?.counts;
  const options = VIEWS.map((v) => ({
    label: COPY.views[v],
    ...(counts === null || counts === undefined ? {} : { count: counts[v] ?? 0 }),
  }));
  const pending = (entries.data?.items ?? []).filter((e) => e.status === "review_required");

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "assurance_completion" };
  else if (sum.isError) {
    const status = (sum.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void sum.refetch() };
  } else if (sum.data === undefined) state = { kind: "loading" };

  return (
    <div data-screen="AUD-16" data-view={view} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] shrink-0 items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.viewsLabel}
          options={options}
          active={COPY.views[view]}
          onChange={(label) => {
            const next = VIEWS.find((v) => COPY.views[v] === label);
            if (next !== undefined) onView(next);
          }}
        />
        <h1 className="flex-1 text-center text-[14.5px] font-medium">{COPY.title}</h1>
        <Button variant="ghost" size="sm" icon="cloud-download">
          {COPY.openInExcel}
        </Button>
        {onSend !== undefined && (
          <Button
            variant="secondary"
            size="sm"
            icon="send"
            disabled={pending.length === 0}
            onClick={() => {
              onSend(pending.map((e) => e.id));
            }}
          >
            {COPY.sendToClient}
          </Button>
        )}
      </div>
      <ViewStateBody state={state} empty={{ title: COPY.states.empty }}>
        {() =>
          sum.data === undefined ? null : (
            <>
              <Tally sum={sum.data} />
              <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pt-[10px] pb-[12px]">
                <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                  {view === "passed" && (
                    <SumTable sum={sum.data} onFinding={onFinding} onSignOff={onSignOff} />
                  )}
                  {(view === "proposed" || view === "reclass") && entries.data !== undefined && (
                    <Entries
                      entries={entries.data.items}
                      onSend={view === "proposed" ? onSend : undefined}
                    />
                  )}
                  {view === "below_ct" && belowCt.data !== undefined && (
                    <BelowCt items={belowCt.data.items} />
                  )}
                </div>
                <Evaluation sum={sum.data} auditId={auditId} onDecision={onDecision} />
              </div>
            </>
          )
        }
      </ViewStateBody>
    </div>
  );
}
