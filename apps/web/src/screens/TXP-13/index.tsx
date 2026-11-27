// TXP-13 d · 1120 from the audit (T-06-T45; TASK-8935; revision.md D; DEC-5937): Granite Peak's
// FY2026 Form 1120 after AUD-38's hand-off, at `/tax-returns/$returnId/review/workpapers`. The
// subbar is the return's record; the banner (HandoffProvenanceBanner, shared with TXP-02), the
// tally and the M-1 starting point read the hand-off landing (`…/handoff`): book income, tax per
// books, the account counts and the passed adjustments carried as candidates, flagged and never
// booked. Frames a–c (1120-S AAA, 1120 provision, 990) are T-06's other rows; a return with no
// hand-off says so. Nothing here changes the audited statements or the client's ledger.
import { returnHandoffOptions, returnRecordOptions } from "@abacus/api-client/query";
import type { TaxReturnRowOut } from "@abacus/api-client";
import {
  Button,
  EmptyState,
  FlagOffState,
  Segmented,
  Skeleton,
  TallyStrip,
  Tag,
  amount,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useOpenHref, useOpenOverlay } from "../../app-core/open";
import { HandoffProvenanceBanner } from "../../domain/tax";
import { hrefOf, ov, to } from "../../routes/to";
import { COPY as C } from "./copy";
import { AaaFrame, PartIxFrame, ProvisionFrame } from "./frames";

export interface TXP13Props {
  returnId: string;
}

const money = (v: string): string => amount(v, "whole").text;

/** T-06-T52 (DEC-6036): the frame is the return's form; a hand-off landing is frame d. */
export function TXP13({ returnId }: TXP13Props): JSX.Element {
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const row = record.data?.row;
  if (row === undefined) {
    return (
      <div data-screen="TXP-13" aria-busy="true" className="p-[12px]">
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  if (row.form === "1120s" || row.form === "990") {
    return (
      <FeatureGate
        flag="tax.other_entity_workpapers"
        fallback={
          <FlagOffState flag="tax.other_entity_workpapers" label="Other entity workpapers" />
        }
      >
        {row.form === "1120s" ? (
          <AaaFrame returnId={returnId} row={row} />
        ) : (
          <PartIxFrame returnId={returnId} row={row} />
        )}
      </FeatureGate>
    );
  }
  return <Corporation returnId={returnId} row={row} />;
}

/** An 1120: frame d when an audit handed the TB off, else frame b (the provision). */
function Corporation({ returnId, row }: { returnId: string; row: TaxReturnRowOut }): JSX.Element {
  const landing = useQuery({
    ...returnHandoffOptions({ path: { return_id: returnId } }),
    retry: false,
  });
  if (landing.isPending) {
    return (
      <div data-screen="TXP-13" aria-busy="true" className="p-[12px]">
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  if (landing.data?.handoff_id == null) {
    return (
      <FeatureGate
        flag="tax.other_entity_workpapers"
        fallback={
          <FlagOffState flag="tax.other_entity_workpapers" label="Other entity workpapers" />
        }
      >
        <ProvisionFrame
          returnId={returnId}
          row={row}
          fallback={
            <div data-screen="TXP-13" className="flex min-h-0 flex-1 flex-col">
              <EmptyState icon="link-2" title={C.none}>
                {C.noneBody}
              </EmptyState>
            </div>
          }
        />
      </FeatureGate>
    );
  }
  return (
    <FeatureGate
      flag="tax.tb_handoff"
      fallback={<FlagOffState flag="tax.tb_handoff" label="Hand-off workpapers" />}
    >
      <HandoffFrame returnId={returnId} />
    </FeatureGate>
  );
}

function HandoffFrame({ returnId }: TXP13Props): JSX.Element {
  const openHref = useOpenHref();
  const openOverlay = useOpenOverlay();
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const landing = useQuery({
    ...returnHandoffOptions({ path: { return_id: returnId } }),
    retry: false,
  });
  if (record.data === undefined || landing.isPending) {
    return (
      <div data-screen="TXP-13" aria-busy="true" className="p-[12px]">
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  const row = record.data.row;
  const land = landing.data;
  const book = land?.book_income;
  const counts = land?.counts;
  const candidates = land?.candidates ?? [];
  return (
    <div data-screen="TXP-13" data-frame="d" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[46px] flex-none items-center gap-[8px] px-[12px]">
        <span className="text-[15px] font-medium">{`${String(row.tax_year)} Form ${row.form}`}</span>
        <span className="text-[13px] text-ink-2">{row.client_name}</span>
      </div>
      <div className="flex h-[44px] flex-none items-center px-[12px]">
        <Segmented size="small" label={C.tabsLabel} options={C.tabs} active={C.active} />
      </div>
      {land?.handoff_id == null || book == null ? (
        <EmptyState icon="link-2" title={C.none}>
          {C.noneBody}
        </EmptyState>
      ) : (
        <>
          <HandoffProvenanceBanner
            returnId={returnId}
            onOpenSource={(l) => {
              if (l.source_work_item_id != null) {
                openHref(
                  hrefOf(to.AUD02({ auditId: l.source_work_item_id }), {
                    section: "trial_balance",
                  }),
                );
              }
            }}
            onDetails={(l) => {
              if (l.source_work_item_id != null) openOverlay(ov.AUD38(l.source_work_item_id));
            }}
          />
          <TallyStrip
            label={C.tally}
            className="flex-none px-[12px] py-[10px]"
            items={[
              { label: C.bookIncome, value: money(book.net_income), info: C.bookIncomeInfo },
              {
                label: C.taxPerBooks,
                value: money(book.income_tax_expense),
                info: C.taxPerBooksInfo,
              },
              ...(counts == null
                ? []
                : [
                    {
                      label: C.mapped,
                      value: C.mappedValue(counts.mapped, counts.total),
                      info: C.mappedInfo(counts.suggested, counts.review),
                    },
                  ]),
              ...(candidates[0] === undefined
                ? []
                : [
                    {
                      label: C.candidate,
                      value: money(candidates[0].amount),
                      info: C.candidateInfo,
                    },
                  ]),
            ]}
          />
          <section
            aria-label={C.pane}
            className="mx-[12px] mb-[12px] overflow-hidden rounded-[12px] bg-card shadow-e1"
          >
            <h2 className="flex h-[40px] items-center px-[14px] text-[14px] font-medium">
              {C.pane}
            </h2>
            <dl className="text-[13px]" data-txp13="m1">
              <div className="flex h-[34px] items-center justify-between px-[14px] hairline-b">
                <dt className="text-ink-2">{C.netIncome}</dt>
                <dd className="tabular-nums">{money(book.net_income)}</dd>
              </div>
              <div className="flex h-[34px] items-center justify-between px-[14px] hairline-b">
                <dt className="text-ink-2">{C.taxExpense}</dt>
                <dd className="tabular-nums">{money(book.income_tax_expense)}</dd>
              </div>
              {candidates.map((c) => (
                <div
                  key={c.ref}
                  data-candidate={c.ref}
                  className="flex min-h-[40px] items-center gap-[10px] bg-amber-tint px-[14px] py-[6px] hairline-b"
                >
                  <dt className="min-w-0 flex-1">
                    {`${C.deductions}: ${C.passed(c.ref)}`}
                    <Tag className="ml-[8px]">{C.fromSum}</Tag>
                  </dt>
                  <dd className="tabular-nums">{money(c.amount)}</dd>
                  <Button variant="tonal" size="sm" disabled>
                    {C.explain}
                  </Button>
                </div>
              ))}
            </dl>
            {counts == null ? null : (
              <p className="px-[14px] py-[10px] text-[11.5px] text-ink-3">
                {C.note(counts.suggested + counts.review)}
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
