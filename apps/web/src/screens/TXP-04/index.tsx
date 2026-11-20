// TXP-04 · Review › M-1/M-3 and Schedule M-2 (T-06-T30; docs/screens/TXP-04.md; T-06 §3 F2): one
// screen ID, two Group B frames on T6. M-1/M-3 (a, a′): Part I as key–value rows and Parts II–III in
// the statement grammar, (a) + (b) + (c) = (d) on every row, no-difference lines collapsed into
// one; the M-1 toggle draws the reference banner and the M-1 marked Not filed (M-1 and M-3 are never
// both filed). Schedule M-2 (b–d): As drafted · With proposed fix, the tally against Schedule L, the
// ghost chip on line 4 with Accept… (SHL-10, never applied inline) and Reject… with a reason, and
// the accepted state with its checkpoint. Figures are the server's; the screen adds nothing.
import type { RejectProposalIn, TaxDepthScheduleOut, WorkbookM2Out } from "@abacus/api-client";
import {
  Button,
  DataGrid,
  Picker,
  Pill,
  Segmented,
  SkeletonRows,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  Toggle,
  amount,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export type Txp04Frame = "m1-m3" | "schedule-m2";
export type M2Variant = WorkbookM2Out["variant"];
export type RejectReason = RejectProposalIn["reason_code"];

const MONEY = { type: "num", format: "whole" } as const;
const whole = (v: string): string => amount(v, "whole").text;

const M3_COLUMNS: TableColumn[] = [
  { key: "line", header: COPY.columns.line, type: "text", width: 52, line: true },
  { key: "item", header: COPY.columns.item, type: "label", width: 300 },
  { key: "a", header: COPY.columns.a, ...MONEY, width: 150 },
  { key: "b", header: COPY.columns.b, ...MONEY, width: 150 },
  { key: "c", header: COPY.columns.c, ...MONEY, width: 150 },
  { key: "d", header: COPY.columns.d, ...MONEY, width: 150 },
];
const M1_COLUMNS: TableColumn[] = [
  { key: "line", header: COPY.columns.line, type: "text", width: 52, line: true },
  { key: "item", header: COPY.columns.item, type: "label", width: 520 },
  { key: "amount", header: COPY.columns.amount, ...MONEY, width: 150 },
];
const M2_COLUMNS: TableColumn[] = [
  { key: "line", header: COPY.columns.line, type: "text", width: 52, line: true },
  { key: "item", header: COPY.columns.item, type: "label", width: 420 },
  { key: "amount", header: COPY.columns.amount, ...MONEY, width: 150 },
  { key: "ghost", header: "", type: "text", width: 140 },
];

export function m3Rows(s: TaxDepthScheduleOut): TableRow[] {
  return s.rows.map((r, i) => ({
    id: `m3:${r.line}`,
    ...(i === s.rows.length - 1 ? { kind: "total" as const } : {}),
    label: r.note == null ? r.label : `${r.label} · ${r.note}`,
    cells: {
      line: { value: r.line },
      a: { value: r.income_per_books },
      b: { value: r.temporary },
      c: { value: r.permanent },
      d: { value: r.per_return },
    },
  }));
}

export function m1Rows(s: TaxDepthScheduleOut): TableRow[] {
  return s.rows.map((r, i) => ({
    id: `m1:${r.line}`,
    ...(i === s.rows.length - 1 ? { kind: "total" as const } : {}),
    label: r.label,
    cells: { line: { value: r.line }, amount: { value: r.per_return } },
  }));
}

export function m2Rows(m2: WorkbookM2Out, ghost?: string): TableRow[] {
  return (m2.lines ?? []).map((l) => ({
    id: `m2:${String(l.line)}`,
    ...(l.line === 5 || l.line === 8 ? { kind: "total" as const } : {}),
    ...(l.line === 9 ? { kind: "grand" as const } : {}),
    label: l.label,
    cells: {
      line: { value: String(l.line) },
      amount: { value: l.amount },
      ...(l.line === 4 && ghost !== undefined ? { ghost: { value: COPY.proposed(ghost) } } : {}),
    },
  }));
}

export function m2Tally(m2: WorkbookM2Out | undefined): TallyItem[] {
  if (m2 === undefined) return [];
  const ties: TallyItem =
    m2.tie === "tie"
      ? { label: COPY.cards.ties, tally: "tie" }
      : {
          label: COPY.cards.ties,
          tally: "off",
          vars: { amount: whole((m2.difference ?? "0").replace("-", "")) },
        };
  return [
    ties,
    { label: COPY.cards.line9, value: whole(m2.ending) },
    { label: COPY.cards.schL, value: whole(m2.item_l?.m2_ending ?? m2.ending) },
  ];
}

function M3Frame({
  m3,
  m1,
  showM1,
  onShowM1,
}: {
  m3: TaxDepthScheduleOut | undefined;
  m1: TaxDepthScheduleOut | undefined;
  showM1: boolean;
  onShowM1?: (on: boolean) => void;
}): JSX.Element {
  if (m3 === undefined) return <SkeletonRows type="table" immediate label={COPY.m3Title} />;
  return (
    <div className="flex flex-col gap-[12px]">
      <div className="flex items-center gap-[8px]">
        <span className="text-body font-medium text-ink">{COPY.m3Title}</span>
        <Pill variant={m3.filed ? "green" : "neutral"}>
          {m3.filed ? COPY.filed : COPY.notFiled}
        </Pill>
        <span className="flex-1" />
        <Toggle
          label={COPY.m1Toggle}
          checked={showM1}
          {...(onShowM1 === undefined ? {} : { onChange: onShowM1 })}
        />
      </div>
      <section aria-label={COPY.partI} className="flex flex-col gap-[4px]">
        <h3 className="text-dense font-medium text-ink-2">{COPY.partI}</h3>
        <dl className="grid grid-cols-[260px_1fr] gap-y-[4px] text-body">
          <dt className="text-ink-3">{COPY.kv.totalAssets}</dt>
          <dd className="tabular-nums">{whole(m3.total_assets)}</dd>
          <dt className="text-ink-3">{COPY.kv.bookIncome}</dt>
          <dd className="tabular-nums">{whole(m3.book_income)}</dd>
          <dt className="text-ink-3">{COPY.kv.required}</dt>
          <dd>{m3.required ? COPY.kv.requiredYes : COPY.notFiled}</dd>
        </dl>
      </section>
      <section aria-label={COPY.partII}>
        <h3 className="mb-[6px] text-dense font-medium text-ink-2">{COPY.partII}</h3>
        <DataGrid
          label={COPY.table(COPY.m3Title)}
          grammar="statement"
          columns={M3_COLUMNS}
          rows={m3Rows(m3)}
        />
      </section>
      {showM1 && m1 !== undefined ? (
        <section
          data-m1-reference=""
          aria-label={COPY.m1Title}
          className="flex flex-col gap-[6px]"
        >
          <p
            role="note"
            className="rounded-[8px] bg-nested px-[10px] py-[8px] text-body text-ink-2"
          >
            {COPY.m1Banner}
          </p>
          <div className="flex items-center gap-[8px]">
            <span className="text-body font-medium text-ink">{COPY.m1Title}</span>
            {/* The reference is never filed beside an M-3 (TXP-04 deviation). */}
            <Pill variant="neutral">{COPY.notFiled}</Pill>
          </div>
          <DataGrid
            label={COPY.table(COPY.m1Title)}
            grammar="statement"
            columns={M1_COLUMNS}
            rows={m1Rows(m1)}
          />
        </section>
      ) : null}
    </div>
  );
}

const REASONS = Object.keys(COPY.reasons) as RejectReason[];

function M2Frame({
  m2,
  ghost,
  variant,
  accepted,
  canDecide,
  onVariant,
  onAccept,
  onReject,
  onOpenCheckpoint,
}: {
  m2: WorkbookM2Out | undefined;
  ghost: string | undefined;
  variant: M2Variant;
  accepted: boolean;
  canDecide: boolean;
  onVariant?: (v: M2Variant) => void;
  onAccept?: () => void;
  onReject?: (reason: RejectReason) => void;
  onOpenCheckpoint?: () => void;
}): JSX.Element {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState<RejectReason | undefined>(undefined);
  return (
    <div className="flex flex-col gap-[10px]">
      <div className="flex items-center gap-[8px]">
        <span className="text-body font-medium text-ink">{COPY.m2Title}</span>
        <span className="flex-1" />
        {accepted ? null : (
          <Segmented
            size="small"
            label={COPY.variants}
            options={[COPY.asDrafted, COPY.withFix]}
            active={variant === "with_fix" ? COPY.withFix : COPY.asDrafted}
            {...(onVariant === undefined
              ? {}
              : {
                  onChange: (label: string) => {
                    onVariant(label === COPY.withFix ? "with_fix" : "as_drafted");
                  },
                })}
          />
        )}
      </div>
      <TallyStrip label={COPY.tally} items={m2Tally(m2)} />
      {accepted ? (
        <div
          data-accepted=""
          className="flex items-center gap-[8px] rounded-[8px] bg-green-tint px-[10px] py-[8px] text-body text-green-ink"
        >
          <span>{COPY.accepted}</span>
          <Button variant="ghost" size="sm" onClick={onOpenCheckpoint}>
            {COPY.openCheckpoint}
          </Button>
          <span className="text-ink-2">{COPY.rerun}</span>
        </div>
      ) : null}
      {m2 === undefined ? (
        <SkeletonRows type="table" immediate label={COPY.m2Title} />
      ) : (
        <DataGrid
          label={COPY.table(COPY.m2Title)}
          grammar="statement"
          columns={M2_COLUMNS}
          rows={m2Rows(m2, variant === "as_drafted" && !accepted ? ghost : undefined)}
        />
      )}
      {variant === "as_drafted" && !accepted && ghost !== undefined && canDecide ? (
        <div data-ghost-actions="" className="flex items-center gap-[8px]">
          <span className="rounded-pill px-[8px] py-[2px] text-dense text-ink-3 inset-ring-[0.5px] inset-ring-hair">
            {COPY.proposed(ghost)}
          </span>
          <Button variant="secondary" size="sm" opensDialog onClick={onAccept}>
            {COPY.accept}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            opensDialog
            onClick={() => {
              setRejecting(true);
            }}
          >
            {COPY.reject}
          </Button>
        </div>
      ) : null}
      {rejecting ? (
        <div
          role="dialog"
          aria-label={COPY.rejectTitle}
          className="rounded-[10px] bg-nested p-[12px]"
        >
          <p className="mb-[8px] text-body font-medium text-ink">{COPY.rejectTitle}</p>
          <div className="mb-[8px]">
            <Picker
              label={COPY.reason}
              {...(reason === undefined ? {} : { value: reason })}
              placeholder={COPY.reason}
              onChange={(v) => {
                setReason(v as RejectReason);
              }}
              options={REASONS.map((r) => ({ value: r, label: COPY.reasons[r] }))}
            />
          </div>
          <div className="flex gap-[8px]">
            <Button
              variant="primary"
              size="sm"
              disabled={reason === undefined}
              onClick={() => {
                if (reason !== undefined) onReject?.(reason);
                setRejecting(false);
              }}
            >
              {COPY.rejectConfirm}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRejecting(false);
              }}
            >
              {COPY.cancel}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export interface TXP04Props {
  frame: Txp04Frame;
  m3?: TaxDepthScheduleOut | undefined;
  m1?: TaxDepthScheduleOut | undefined;
  showM1?: boolean;
  m2?: WorkbookM2Out | undefined;
  /** Line 4 of the proposed fix, the ghost on as drafted (formatted by the screen). */
  proposedLine4?: string | undefined;
  variant?: M2Variant;
  /** The fix is the workbook's (d). */
  accepted?: boolean;
  /** The viewer may decide the proposal (a person with the proposal's ref). */
  canDecide?: boolean;
  onShowM1?: (on: boolean) => void;
  onVariant?: (v: M2Variant) => void;
  onAccept?: () => void;
  onReject?: (reason: RejectReason) => void;
  onOpenCheckpoint?: () => void;
}

export function TXP04(props: TXP04Props): JSX.Element {
  const ghost =
    props.proposedLine4 === undefined || Number(props.proposedLine4) === 0
      ? undefined
      : whole(props.proposedLine4);
  return (
    <div data-screen="TXP-04" data-frame={props.frame} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-[12px] py-[10px]">
        {props.frame === "m1-m3" ? (
          <M3Frame
            m3={props.m3}
            m1={props.m1}
            showM1={props.showM1 === true}
            {...(props.onShowM1 === undefined ? {} : { onShowM1: props.onShowM1 })}
          />
        ) : (
          <M2Frame
            m2={props.m2}
            ghost={ghost}
            variant={props.variant ?? "as_drafted"}
            accepted={props.accepted === true}
            canDecide={props.canDecide === true}
            {...(props.onVariant === undefined ? {} : { onVariant: props.onVariant })}
            {...(props.onAccept === undefined ? {} : { onAccept: props.onAccept })}
            {...(props.onReject === undefined ? {} : { onReject: props.onReject })}
            {...(props.onOpenCheckpoint === undefined
              ? {}
              : { onOpenCheckpoint: props.onOpenCheckpoint })}
          />
        )}
      </div>
    </div>
  );
}
