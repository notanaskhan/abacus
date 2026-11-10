import type { ExtensionRowOut, ProposedPaymentIn } from "@abacus/api-client";
import {
  extensionsApproveMutation,
  extensionsOptions,
  extensionsPrepareMutation,
  extensionsSubmitMutation,
} from "@abacus/api-client/query";
import { Button, Icon, SheetModal, Skeleton, cn, date, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";
import { figure } from "./figure";

// TAX-13 d · Extend sheet (T-03-T16; the handoff's O3 sheet): per-row projected liability, safe-harbor
// target, an editable payment and a check line. "Send confirmation requests" is one human click and
// one call: it prepares, approves the amounts as the person clicking, and sends one request per
// client, all in one unit of work on the server. Someone without the reviewer function gets
// "Submit for approval" instead. The check line is a preview of the edit; the server recomputes it.

const FEDERAL = "federal";

function toCents(value: string): bigint | null {
  const found = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.replaceAll(",", "").trim());
  if (found === null) return null;
  return BigInt(found[1] ?? "0") * 100n + BigInt((found[2] ?? "").padEnd(2, "0"));
}

function fromCents(cents: bigint): string {
  return `${String(cents / 100n)}.${String(cents % 100n).padStart(2, "0")}`;
}

const extensionPayments = (row: ExtensionRowOut): ExtensionRowOut["payments"] =>
  row.payments.filter((p) => p.kind === "extension_payment");

const federalAmount = (row: ExtensionRowOut): string =>
  extensionPayments(row).find((p) => p.jurisdiction === FEDERAL)?.amount ?? "";

function formOf(row: ExtensionRowOut, jurisdiction: string): string {
  return row.lines.find((l) => l.jurisdiction === jurisdiction)?.form ?? "";
}

/** The payments as edited, on the wire: the federal figure typed, the state lines as proposed. */
function paymentsOf(
  rows: readonly ExtensionRowOut[],
  typed: Readonly<Record<string, string>>,
): ProposedPaymentIn[] {
  return rows.flatMap((row) => {
    const entered = typed[row.tax_return_id] ?? federalAmount(row);
    const cents = toCents(entered);
    const federal: ProposedPaymentIn[] =
      cents === null || cents === 0n
        ? []
        : [
            {
              return_id: row.tax_return_id,
              jurisdiction: FEDERAL,
              kind: "extension_payment",
              amount: fromCents(cents),
            },
          ];
    const states = extensionPayments(row)
      .filter((p) => p.jurisdiction !== FEDERAL)
      .map((p): ProposedPaymentIn => ({
        return_id: row.tax_return_id,
        jurisdiction: p.jurisdiction,
        kind: "extension_payment",
        amount: p.amount,
        form: formOf(row, p.jurisdiction) || null,
      }));
    return [...federal, ...states];
  });
}

function CheckLine({
  row,
  entered,
}: {
  row: ExtensionRowOut;
  entered: string;
}): JSX.Element | null {
  const now = useNow();
  const have = toCents(row.withholding_plus_estimates ?? "");
  const target = toCents(row.safe_harbor_target ?? "");
  const paying = toCents(entered === "" ? "0" : entered);
  if (have === null || target === null || paying === null) return null;
  const total = have + paying;
  const meets = total >= target;
  const pct = row.safe_harbor_pct ?? "";
  return (
    <p
      data-check={meets ? "meets" : "below"}
      className={cn(
        "flex items-center gap-[6px] px-[14px] pb-[12px] text-[12.5px]",
        meets ? "text-green-ink" : "text-red-ink",
      )}
    >
      <Icon name={meets ? "check" : "triangle-alert"} size={14} />
      {COPY.extend.paidBy(
        date(row.original_due_on, { now }),
        figure(fromCents(have)),
        figure(fromCents(paying)),
        figure(fromCents(total)),
      )}
      {meets ? COPY.extend.meets(pct) : COPY.extend.below(pct)}
    </p>
  );
}

function ReturnCard({
  row,
  entered,
  onEntered,
}: {
  row: ExtensionRowOut;
  entered: string;
  onEntered: (value: string) => void;
}): JSX.Element {
  const invalid = entered !== "" && toCents(entered) === null;
  const states = extensionPayments(row).filter((p) => p.jurisdiction !== FEDERAL);
  return (
    <section data-extend-row={row.tax_return_id} className="rounded-pane bg-card shadow-e1">
      <header className="flex h-[44px] items-center justify-between px-[14px] hairline-b">
        <span className="text-[13px] font-medium">{row.client_name}</span>
        <span className="text-meta text-ink-3">
          {row.return_form} · {row.lines.map((l) => l.form).join(" + ")}
        </span>
      </header>
      <div className="grid grid-cols-3 gap-[12px] px-[14px] py-[12px] text-[12.5px]">
        <div>
          <div className="text-meta text-ink-3">{COPY.columns.projected}</div>
          <div data-field="projected" className="mt-[6px] tabular-nums">
            {figure(row.projected_liability)}
          </div>
        </div>
        <div>
          <div className="text-meta text-ink-3">{COPY.columns.target}</div>
          <div data-field="target" className="mt-[6px] tabular-nums">
            {figure(row.safe_harbor_target)}
            {row.safe_harbor_pct != null && (
              <span className="ml-[3px] text-ink-3">({row.safe_harbor_pct}%)</span>
            )}
          </div>
        </div>
        <div>
          <div className="text-meta text-ink-3">{COPY.extend.payment}</div>
          <input
            aria-label={COPY.extend.paymentFor(row.client_name)}
            aria-invalid={invalid}
            inputMode="decimal"
            className="mt-[6px] h-[30px] w-full rounded-full bg-card px-[12px] text-right text-[13px] tabular-nums shadow-e1"
            value={entered}
            onChange={(event) => {
              onEntered(event.target.value);
            }}
          />
          {invalid && (
            <p role="alert" className="mt-[4px] text-meta text-red-ink">
              {COPY.extend.invalid}
            </p>
          )}
          {states.map((p) => (
            <p key={p.id} className="mt-[4px] text-right text-meta text-ink-3">
              {COPY.extend.withForm(p.jurisdiction, figure(p.amount), formOf(row, p.jurisdiction))}
            </p>
          ))}
        </div>
      </div>
      <CheckLine row={row} entered={entered} />
    </section>
  );
}

export interface ExtendSheetProps {
  taxYear: number;
  returnIds: readonly string[];
  /** `true` when the sheet sent or submitted, so the screen clears its selection. */
  onClose: (sent: boolean) => void;
}

export function ExtendSheet({ taxYear, returnIds, onClose }: ExtendSheetProps): JSX.Element {
  const session = useSession();
  const queries = useQueryClient();
  const found = useQuery(
    extensionsOptions({ query: { tax_year: taxYear, return_id: [...returnIds] } }),
  );
  const rows = useMemo(() => found.data?.items ?? [], [found.data]);
  const [typed, setTyped] = useState<Readonly<Record<string, string>>>({});
  const payments = useMemo(() => paymentsOf(rows, typed), [rows, typed]);
  const ids = rows.map((r) => r.tax_return_id);
  // One key per body: a double click or a retry sends the same requests once; an edit is new.
  const asked = JSON.stringify([ids, payments]);
  const [keyed, setKeyed] = useState({ asked, key: crypto.randomUUID() });
  if (keyed.asked !== asked) setKeyed({ asked, key: crypto.randomUUID() });
  const { key } = keyed;
  const approve = useMutation(extensionsApproveMutation());
  const prepare = useMutation(extensionsPrepareMutation());
  const submitForApproval = useMutation(extensionsSubmitMutation());
  const reviewer = rows.every((r) =>
    r.allowed_actions.includes("filing_extension.approve_payment"),
  );
  const pending = approve.isPending || prepare.isPending || submitForApproval.isPending;
  const failed = approve.isError || prepare.isError || submitForApproval.isError;
  const invalid = rows.some((r) => {
    const entered = typed[r.tax_return_id] ?? federalAmount(r);
    return entered !== "" && toCents(entered) === null;
  });
  const done = (): void => {
    void queries.invalidateQueries({
      queryKey: extensionsOptions({ query: { tax_year: taxYear } }).queryKey,
    });
    onClose(true);
  };
  const send = (): void => {
    approve.mutate(
      {
        body: { return_ids: ids, payments, send_confirmations: true },
        headers: { "Idempotency-Key": key },
      },
      {
        onSuccess: (out) => {
          toast.show(COPY.extend.sent(out.confirmation_request_item_ids.length));
          done();
        },
      },
    );
  };
  const submit = (): void => {
    prepare.mutate(
      { body: { return_ids: ids, payments }, headers: { "Idempotency-Key": key } },
      {
        onSuccess: (out) => {
          submitForApproval.mutate(
            {
              body: {
                extension_ids: out.extensions.flatMap((r) => r.lines.map((l) => l.extension_id)),
              },
              headers: { "Idempotency-Key": key },
            },
            {
              onSuccess: () => {
                toast.show(COPY.extend.submitted(ids.length));
                done();
              },
            },
          );
        },
      },
    );
  };
  const missing = found.data === undefined ? 0 : returnIds.length - rows.length;
  const name = session.user?.displayName ?? "";
  return (
    <SheetModal
      open
      onOpenChange={(open) => {
        if (!open) onClose(false);
      }}
      title={COPY.extend.title(rows.length || returnIds.length)}
      dirty={Object.keys(typed).length > 0}
      footer={
        <div className="flex flex-col gap-[8px]">
          {failed && (
            <p role="alert" className="text-meta text-red-ink">
              {COPY.extend.failed}
            </p>
          )}
          <Button
            variant="primary"
            size="footer"
            disabled={rows.length === 0 || invalid || pending}
            onClick={reviewer ? send : submit}
          >
            {reviewer ? COPY.extend.send : COPY.extend.submit}
          </Button>
          <Button
            variant="secondary"
            size="footer"
            onClick={() => {
              onClose(false);
            }}
          >
            {COPY.extend.cancel}
          </Button>
        </div>
      }
    >
      <div data-extend-sheet className="flex flex-col gap-[10px]">
        {found.data === undefined ? (
          <Skeleton className="h-[200px]" />
        ) : (
          rows.map((row) => (
            <ReturnCard
              key={row.tax_return_id}
              row={row}
              entered={typed[row.tax_return_id] ?? federalAmount(row).replace(/\.0+$/, "")}
              onEntered={(value) => {
                setTyped((was) => ({ ...was, [row.tax_return_id]: value }));
              }}
            />
          ))
        )}
        {found.data !== undefined && (rows.length === 0 || missing > 0) && (
          <p data-extend-missing className="text-para text-ink-3">
            {rows.length === 0 ? COPY.extend.none : COPY.extend.missing(missing)}
          </p>
        )}
        {rows.length > 0 && (
          <p className="flex gap-[8px] rounded-pane bg-card px-[14px] py-[12px] text-para text-ink-2 shadow-e1">
            <Icon name="shield-check" size={14} className="mt-[2px] shrink-0" />
            {reviewer ? COPY.extend.approveNote(name) : COPY.extend.submitNote}
          </p>
        )}
      </div>
    </SheetModal>
  );
}
