// TXP-09 · Review › States & PTET (T-06-T32; docs/screens/TXP-09.md; T-06 §3 F4): T6 inside the
// entity return's layout. The control bar (Apportionment & PTET · Partner credits · Nexus), the
// tally strip and either the apportionment table with its inline share bars, the NYC opportunity
// row (a recommendation only: it opens TAX-15, it never records an election) and the PTET note, the
// partner credits that flow to the state K-1s, or the nexus facts. "Approve sourcing…" opens SHL-10
// (the reviewer's). Pills read their words, never colour alone. Figures are the server's (ADR-050).
import type { TaxDepthStateOut, TaxDepthStatesOut } from "@abacus/api-client";
import {
  Button,
  Pill,
  Segmented,
  SkeletonRows,
  type TallyItem,
  TallyStrip,
  amount,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";

export type Txp09View = "apportionment" | "credits" | "nexus";
const whole = (v: string | null | undefined): string => amount(v ?? "0", "whole").text;
const day = (iso: string): string =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
const short = (iso: string): string =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

export function tallyItems(s: TaxDepthStatesOut | undefined): TallyItem[] {
  if (s === undefined) return [];
  const elected = s.states.filter((r) => r.ptet === "elected").length;
  const firstPaid = s.states.find((r) => r.ptet_paid_on)?.ptet_paid_on;
  const allPaid = s.paid_count === s.payable_count;
  return [
    s.apportionment_tally === "tie"
      ? { label: COPY.tallies.sums, tally: "tie" }
      : { label: COPY.tallies.sums, pill: { text: "Check", variant: "amber" } },
    { label: COPY.tallies.base, value: whole(s.base) },
    { label: COPY.tallies.elected, value: COPY.of(elected, s.states.length) },
    { label: COPY.tallies.total, value: whole(s.ptet_total) },
    allPaid && firstPaid
      ? { label: COPY.tallies.paid, value: day(firstPaid) }
      : {
          label: COPY.tallies.paid,
          pill: { text: COPY.of(s.paid_count, s.payable_count), variant: "amber" },
        },
    { label: COPY.tallies.creditsEqual, tally: "tie" },
    {
      label: COPY.tallies.sourcing,
      pill: {
        text: s.sourcing === "approved" ? COPY.status.approved : COPY.inReview,
        variant: s.sourcing === "approved" ? "green" : "neutral",
      },
    },
  ];
}

function PtetPill({ ptet }: { ptet: TaxDepthStateOut["ptet"] }): JSX.Element {
  const variant = ptet === "elected" ? "green" : ptet === "recommend" ? "amber" : "neutral";
  return (
    <Pill variant={variant} data-ptet={ptet}>
      {COPY.ptet[ptet]}
    </Pill>
  );
}

function ShareBar({ pct }: { pct: string }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-[6px]">
      <span className="tabular-nums">{`${pct}%`}</span>
      <span aria-hidden className="relative inline-block h-[4px] w-[80px] rounded-full bg-hair">
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-ink"
          style={{ width: `${pct}%` }}
        />
      </span>
    </span>
  );
}

export interface TXP09Props {
  states: TaxDepthStatesOut | undefined;
  view: Txp09View;
  onView?: (v: Txp09View) => void;
  onApproveSourcing?: () => void;
  onMap?: (state: string) => void;
  onRecommend?: () => void;
  onCredits?: () => void;
}

const VIEW_LABEL: Record<Txp09View, string> = {
  apportionment: COPY.apportionment,
  credits: COPY.credits,
  nexus: COPY.nexus,
};

export function TXP09({
  states,
  view,
  onView,
  onApproveSourcing,
  onMap,
  onRecommend,
  onCredits,
}: TXP09Props): JSX.Element {
  const approved = states?.sourcing === "approved";
  return (
    <div data-screen="TXP-09" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.apportionment, COPY.credits, COPY.nexus]}
          active={VIEW_LABEL[view]}
          {...(onView === undefined
            ? {}
            : {
                onChange: (label: string) => {
                  onView(
                    (Object.keys(VIEW_LABEL) as Txp09View[]).find(
                      (k) => VIEW_LABEL[k] === label,
                    ) ?? "apportionment",
                  );
                },
              })}
        />
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.title}</span>
        <Button variant="ghost" size="sm">
          {COPY.openInExcel}
        </Button>
        {approved ? null : (
          <Button variant="secondary" size="sm" opensDialog onClick={onApproveSourcing}>
            {COPY.approveSourcing}
          </Button>
        )}
      </div>
      <TallyStrip label={COPY.tally} items={tallyItems(states)} className="px-[12px] pb-[10px]" />
      <div className="min-h-0 flex-1 overflow-auto px-[12px] pb-[12px]">
        {states === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.title} />
        ) : view === "nexus" ? (
          <table aria-label={COPY.nexus} className="w-full text-body">
            <thead>
              <tr className="h-[30px] text-left text-dense text-ink-2">
                {COPY.nexusColumns.map((c) => (
                  <th key={c} className="px-[8px] font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(states.nexus ?? []).map((n) => (
                <tr key={n.state} data-nexus={n.state} className="h-[34px] border-t border-hair">
                  <td className="px-[8px]">{n.state}</td>
                  <td className="px-[8px]">{n.fact}</td>
                  <td className="px-[8px]">
                    {n.evidence_name ? <Pill variant="neutral">{n.evidence_name}</Pill> : "—"}
                  </td>
                  <td className="px-[8px]">{n.conclusion}</td>
                  <td className="px-[8px]">{n.owner_initials ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : view === "credits" ? (
          <Credits states={states} onCredits={onCredits} />
        ) : (
          <section aria-label={COPY.paneTitle} className="rounded-card bg-card shadow-e1">
            <div className="flex h-[40px] items-center justify-between px-[12px]">
              <h2 className="text-[13.5px] font-medium text-ink">{COPY.paneTitle}</h2>
              {approved ? null : <Pill variant="amber">{COPY.reviewPointOpen}</Pill>}
            </div>
            {states.apportionment_tally === "check" ? (
              <p
                role="status"
                className="mx-[12px] mb-[8px] rounded-[8px] bg-amber-tint px-[10px] py-[6px] text-dense text-amber-ink"
              >
                {COPY.missingBanner}
              </p>
            ) : null}
            <table aria-label={COPY.apportionment} className="w-full text-body">
              <thead>
                <tr className="h-[30px] bg-nested text-dense text-ink-2">
                  {COPY.columns.map((c) => (
                    <th key={c} className="px-[8px] text-left font-medium">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {states.states.map((r) => (
                  <tr key={r.state} data-state={r.state} className="h-[34px] border-t border-hair">
                    <td className="px-[8px]">
                      <span className="block font-medium text-ink">{r.name ?? r.state}</span>
                      <span className="block text-[11px] text-ink-3">{r.property_name}</span>
                    </td>
                    <td className="px-[8px] tabular-nums">
                      {r.numerator == null ? (
                        <button
                          type="button"
                          className="text-amber-ink underline"
                          onClick={() => onMap?.(r.state)}
                        >
                          {COPY.map}
                        </button>
                      ) : (
                        whole(r.numerator)
                      )}
                    </td>
                    <td className="px-[8px] tabular-nums">{whole(r.denominator)}</td>
                    <td className="px-[8px]">
                      <ShareBar pct={r.apportionment_pct} />
                    </td>
                    <td className="px-[8px]">{r.nexus_basis}</td>
                    <td className="px-[8px]">
                      <PtetPill ptet={r.ptet} />
                    </td>
                    <td className="px-[8px] tabular-nums">
                      {r.rate_pct ? `${r.rate_pct}%` : "—"}
                    </td>
                    <td className="px-[8px] tabular-nums">{whole(r.ptet_amount)}</td>
                    <td className="px-[8px]" data-payment={r.ptet_paid_on ? "paid" : "not_paid"}>
                      {r.ptet_paid_on ? (
                        COPY.paidOn(day(r.ptet_paid_on))
                      ) : (
                        <Pill variant="red">{COPY.notPaid}</Pill>
                      )}
                    </td>
                    <td className="px-[8px]">{r.return_form}</td>
                    <td className="px-[8px]">
                      {r.status === "approved" && r.approved_by_initials && r.approved_on ? (
                        <Pill variant="green">
                          {COPY.approvedBy(r.approved_by_initials, short(r.approved_on))}
                        </Pill>
                      ) : (
                        <Pill variant="neutral">{COPY.status.in_review}</Pill>
                      )}
                    </td>
                  </tr>
                ))}
                <tr className="h-[34px] border-t border-hair font-medium">
                  <td className="px-[8px]">{COPY.total}</td>
                  <td className="px-[8px] tabular-nums">{whole(states.base)}</td>
                  <td />
                  <td className="px-[8px] tabular-nums">100.0%</td>
                  <td colSpan={3} />
                  <td className="px-[8px] tabular-nums">{whole(states.ptet_total)}</td>
                  <td colSpan={3} />
                </tr>
                {(states.opportunities ?? []).map((o) => (
                  <tr
                    key={o.jurisdiction}
                    data-opportunity=""
                    className="h-[34px] border-t border-hair bg-nested"
                  >
                    <td className="px-[8px] pl-[20px]">
                      <span className="block text-ink">{o.jurisdiction}</span>
                      <span className="block text-[11px] text-ink-3">{o.subject}</span>
                    </td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">{o.basis}</td>
                    <td className="px-[8px]">
                      <button
                        type="button"
                        onClick={onRecommend}
                        aria-label={`${COPY.ptet.recommend}: ${o.jurisdiction}`}
                      >
                        <PtetPill ptet="recommend" />
                      </button>
                    </td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">—</td>
                    <td className="px-[8px]">{o.deadline_note}</td>
                    <td className="px-[8px]">
                      <Pill variant="neutral">{COPY.ptet.not_elected}</Pill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-[12px] py-[8px] text-[11.5px] text-ink-3">{COPY.note}</p>
          </section>
        )}
      </div>
    </div>
  );
}

function Credits({
  states,
  onCredits,
}: {
  states: TaxDepthStatesOut;
  onCredits?: (() => void) | undefined;
}): JSX.Element {
  const codes = states.states.map((s) => s.state);
  return (
    <section aria-label={COPY.creditsTitle} className="rounded-card bg-card shadow-e1">
      <h2 className="px-[12px] py-[10px] text-[13.5px] font-medium text-ink">
        {COPY.creditsTitle}
      </h2>
      <table aria-label={COPY.creditsTitle} className="w-full text-body">
        <thead>
          <tr className="h-[30px] bg-nested text-dense text-ink-2">
            {COPY.creditColumns.map((c) => (
              <th key={c} className="px-[8px] text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(states.credits ?? []).map((p) => (
            <tr
              key={p.partner_id}
              data-credit={p.partner_id}
              className="h-[34px] border-t border-hair"
            >
              <td className="px-[8px]">
                <button type="button" onClick={onCredits} className="text-left">
                  {p.name}
                  {p.note ? <span className="text-ink-3"> ({p.note})</span> : null}
                </button>
              </td>
              {codes.map((c) => (
                <td key={c} className="px-[8px] tabular-nums">
                  {whole(p.by_state[c])}
                </td>
              ))}
              <td className="px-[8px] tabular-nums">{whole(p.total)}</td>
            </tr>
          ))}
          <tr className="h-[34px] border-t border-hair font-medium">
            <td className="px-[8px]">{COPY.total}</td>
            {states.states.map((s) => (
              <td key={s.state} className="px-[8px] tabular-nums">
                {whole(s.ptet_amount)}
              </td>
            ))}
            <td className="px-[8px] tabular-nums">{whole(states.ptet_total)}</td>
          </tr>
        </tbody>
      </table>
      <p className="px-[12px] py-[8px] text-[11.5px] text-ink-3">{COPY.creditsCaption}</p>
    </section>
  );
}
