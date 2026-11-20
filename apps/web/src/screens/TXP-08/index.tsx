// TXP-08 · Review › Basis (T-06-T31; docs/screens/TXP-08.md; T-06 §3 F3): T6 inside the entity
// return's layout. The control bar (Inside / outside basis · §752 shares, the partner picker, the
// title), the tally strip (4 of 5 reconcile, inside against outside, §754) and either the basis
// cards (one per partner, or the picked one) with Pell Street II's off tile and its 28,595 §743(b)
// placeholder (its two figures; the difference is the server's to send), or the §752 shares by partner. "Review §754…" opens the inline DecisionCard: Elect
// (the agent's recommendation, a tag, never a choice) or Do not elect; the partners decide, so the
// firm's control is Send to client…, which shows the existing waiting-on-client issue, never a new
// one. "Request more analysis…" (PRJ-01) is fixture-only until T-09 (DV-3). Figures are the
// server's; the screen adds nothing (ADR-050).
import type { TaxDepthBasisOut, TaxDepthPartnerBasisOut } from "@abacus/api-client";
import {
  Button,
  DataGrid,
  DecisionCard,
  Picker,
  Pill,
  Segmented,
  SkeletonRows,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  amount,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export type Txp08View = TaxDepthBasisOut["view"];
export interface WaitingIssue {
  title: string;
  step: string;
}

const MONEY = { type: "num", format: "whole" } as const;
const whole = (v: string | null | undefined): string => amount(v ?? "0", "whole").text;
const ALL = "all";

export function tallyItems(b: TaxDepthBasisOut | undefined, of: number): TallyItem[] {
  if (b === undefined) return [];
  return [
    b.reconciled === of
      ? { label: COPY.cards.reconciled, tally: "tie" }
      : {
          label: COPY.cards.reconciled,
          pill: { text: COPY.reconciledOf(b.reconciled, of), variant: "amber" },
        },
    { label: COPY.cards.inside, value: whole(b.inside_total) },
    { label: COPY.cards.outside, value: whole(b.outside_total) },
    {
      label: COPY.cards.s754,
      pill: {
        text: COPY.s754State[b.section_754],
        variant: b.section_754 === "decided" ? "green" : "neutral",
      },
    },
  ];
}

function BasisCard({
  p,
  large,
  onReview754,
}: {
  p: TaxDepthPartnerBasisOut;
  large: boolean;
  onReview754?: (() => void) | undefined;
}): JSX.Element {
  const off = p.tally === "off";
  return (
    <section
      aria-label={p.name}
      data-basis-card={p.partner_id}
      data-tally={p.tally}
      className={`flex flex-col gap-[6px] rounded-nested bg-card p-[12px] shadow-e1 ${large ? "w-[460px]" : "w-[260px]"} ${off ? "inset-ring-[1px] inset-ring-amber" : ""}`}
    >
      <div className="flex items-center gap-[6px]">
        <span className="flex-1 truncate text-body font-medium text-ink">{p.name}</span>
        {off ? (
          <Pill variant="amber">{COPY.off}</Pill>
        ) : (
          <Pill variant="green">{COPY.reconciles}</Pill>
        )}
      </div>
      <dl className="grid grid-cols-[1fr_auto] gap-y-[2px] text-body">
        <dt className="text-ink-3">{COPY.inside}</dt>
        <dd className="tabular-nums">{whole(p.inside)}</dd>
        <dt className="text-ink-3">{COPY.outside}</dt>
        <dd className="tabular-nums">{whole(p.outside)}</dd>
      </dl>
      {off ? (
        <>
          <p className="text-dense text-amber-ink">
            {COPY.versus(whole(p.inside), whole(p.outside))} · {COPY.placeholder}
          </p>
          {onReview754 === undefined ? null : (
            <Button variant="secondary" size="sm" opensDialog onClick={onReview754}>
              {COPY.review754}
            </Button>
          )}
        </>
      ) : null}
    </section>
  );
}

const S752_COLUMNS: TableColumn[] = [
  { key: "partner", header: COPY.columns.partner, type: "label", width: 300 },
  { key: "qnr", header: COPY.columns.qnr, ...MONEY, width: 180 },
  { key: "other", header: COPY.columns.other, ...MONEY, width: 180 },
];

export function s752Rows(b: TaxDepthBasisOut): TableRow[] {
  return b.partners.map((p) => ({
    id: p.partner_id,
    label: p.name,
    cells: {
      qnr: { value: p.qualified_nonrecourse ?? null },
      other: { value: p.other_nonrecourse ?? null },
    },
  }));
}

export interface TXP08Props {
  basis: TaxDepthBasisOut | undefined;
  /** Every partner on the return (the picker and "n of 5"). */
  partners: readonly { id: string; name: string }[];
  view: Txp08View;
  partnerId: string | null;
  cardOpen?: boolean;
  /** The §754 waiting-on-client issue the decision already rides on. */
  waitingIssue?: WaitingIssue | undefined;
  /** PRJ-01 is fixture-only until T-09: "fixture" draws it marked, "hidden" leaves it out. */
  requestMore?: "fixture" | "hidden";
  onView?: (view: Txp08View) => void;
  onPartner?: (partnerId: string | null) => void;
  onCard?: (open: boolean) => void;
  onOpenIssue?: () => void;
  onRequestMore?: () => void;
}

export function TXP08({
  basis: b,
  partners,
  view,
  partnerId,
  cardOpen = false,
  waitingIssue,
  requestMore = "hidden",
  onView,
  onPartner,
  onCard,
  onOpenIssue,
  onRequestMore,
}: TXP08Props): JSX.Element {
  const [sent, setSent] = useState(false);
  const [choice, setChoice] = useState<string | undefined>(undefined);
  const placeholder = b?.partners.find((p) => p.tally === "off");
  return (
    <div data-screen="TXP-08" className="flex min-h-0 flex-1 flex-col">
      <div
        data-entity="control-bar"
        className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]"
      >
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.basis, COPY.s752]}
          active={view === "s752" ? COPY.s752 : COPY.basis}
          {...(onView === undefined
            ? {}
            : {
                onChange: (label: string) => {
                  onView(label === COPY.s752 ? "s752" : "basis");
                },
              })}
        />
        <Picker
          label={COPY.partner}
          value={partnerId ?? ALL}
          onChange={(v) => onPartner?.(v === ALL ? null : v)}
          options={[
            { value: ALL, label: COPY.allPartners },
            ...partners.map((p) => ({ value: p.id, label: p.name })),
          ]}
        />
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.title}</span>
      </div>
      <TallyStrip
        label={COPY.tally}
        items={tallyItems(b, partners.length)}
        className="px-[12px] pb-[10px]"
      />
      <div className="min-h-0 flex-1 overflow-auto px-[12px] pb-[12px]">
        {b === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.title} />
        ) : view === "s752" ? (
          <>
            <DataGrid
              label={COPY.table}
              grammar="statement"
              columns={S752_COLUMNS}
              rows={s752Rows(b)}
            />
            <p className="mt-[8px] text-[11.5px] text-ink-3">{COPY.s752Note}</p>
          </>
        ) : (
          <div className="flex flex-col gap-[12px]">
            <div className="flex flex-wrap gap-[10px]">
              {b.partners.map((p) => (
                <BasisCard
                  key={p.partner_id}
                  p={p}
                  large={partnerId !== null}
                  onReview754={
                    onCard === undefined
                      ? undefined
                      : () => {
                          onCard(true);
                        }
                  }
                />
              ))}
            </div>
            {cardOpen && placeholder !== undefined ? (
              <div className="flex max-w-[560px] flex-col gap-[8px]">
                <DecisionCard
                  title={COPY.card.title}
                  reservedNote={COPY.card.reserved}
                  actor={{ kind: "human", name: "" }}
                  options={[
                    {
                      key: "elect",
                      label: COPY.card.elect,
                      detail: COPY.card.electDetail,
                      recommended: true,
                    },
                    { key: "do_not_elect", label: COPY.card.doNotElect },
                  ]}
                  {...(choice === undefined ? {} : { value: choice })}
                  onChange={setChoice}
                  openDecision={{
                    label: COPY.card.send,
                    onOpen: () => {
                      setSent(true);
                    },
                  }}
                />
                <p className="text-dense text-ink-3">{COPY.card.reserved}</p>
                {sent && waitingIssue !== undefined ? (
                  <div
                    role="status"
                    data-waiting-issue=""
                    className="flex flex-wrap items-center gap-[6px] rounded-[8px] bg-nested px-[10px] py-[8px] text-body"
                  >
                    <span className="text-ink-2">{COPY.alreadyWithClient}</span>
                    <span className="text-ink">{waitingIssue.title}</span>
                    <span className="text-ink-3">· {waitingIssue.step}</span>
                    <Button variant="ghost" size="sm" onClick={onOpenIssue}>
                      {COPY.openIssue}
                    </Button>
                  </div>
                ) : null}
                {requestMore === "fixture" ? (
                  <div className="flex items-center gap-[8px]">
                    <Button variant="secondary" size="sm" opensDialog onClick={onRequestMore}>
                      {COPY.card.requestMore}
                    </Button>
                    <Pill variant="neutral">{COPY.card.fixtureOnly}</Pill>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
