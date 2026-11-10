import type {
  ApprovalContextOut,
  ApprovalItemDetailOut,
  ApprovalItemOut,
  ApprovalsOut,
} from "@abacus/api-client";
import { entriesJournal, entriesJournalFile } from "@abacus/api-client";
import {
  acknowledgeUncorrectedMutation,
  askAboutItemMutation,
  decidePackageMutation,
  decideProposedEntryMutation,
  getApprovalOptions,
  listApprovalsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  FullSheet,
  Icon,
  Pill,
  Picker,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  SheetModal,
  amount,
  date as formatDate,
  prose,
  time as formatTime,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-08 · Approvals (R-02-T19; docs/screens/POR-08.md; SPEC-646) on T7 split and T7-M: the rail
// (period card, filters with the server's counts, Coming next) and the main pane (the statement
// package, the attest entries, the acknowledgement of the entries not recorded, and the entries
// the firm posted, read-only). Management decides here; the firm never does. Every amount, title,
// part, highlight, legend and decider's name is the API's: the browser adds nothing up (the net
// effect is the snapshot's 22,250). Each decision sends the `seen_hash` of what was read and an
// `Idempotency-Key`; a stale hash answers 409 and the screen reloads. A firm with the approvals
// flag off answers 404: the designed flag-off state, never a 404 page.
//
//   a   Ben, the August package waiting, six posted entries   a2  the approve confirm
//   b   approved by Tess Sep 15, 8:42 AM                       c   the O3 decline sheet
//   d   Ask about this entry on the 14,900 accrual            e   Dana's four attest entries
//   e2  her decisions and the 22,250 acknowledgement           f   nothing to approve

export type Filter = "waiting" | "posted" | "approved" | "declined";
export type Overlay = "confirm" | "decline" | "ask";

export interface Por08Props {
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** `?context=`: the period or audit open on arrival. */
  context?: string;
  /** `?filter=`: the rail's selection; none lists everything. */
  filter?: Filter;
  /** `?ov=`: an overlay held open on arrival (a2, c, d). */
  overlay?: Overlay;
  /** The posted entry expanded on arrival, by position (a, d: the 14,900 accrual). */
  expanded?: number;
  onNavigate?: (area: string) => void;
}

function isFlagOff(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { detail?: unknown }).detail === "not found"
  );
}

function money(v: string | null | undefined): string {
  return v === null || v === undefined ? "" : prose(v, "money");
}

/** Whole dollars with "$", as the posted-entry list shows them (bento-close-control). */
function dollars(v: string | null | undefined): string {
  return v === null || v === undefined ? "" : `$${amount(v, "whole").text}`;
}

function key(item: ApprovalItemOut, seen: string): string {
  return `${item.kind}:${item.id}:${seen}`;
}

function Disc({ done }: { done: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-disc={done ? "done" : "ring"}
      className={`inline-flex size-[22px] shrink-0 items-center justify-center rounded-full ${done ? "bg-green text-on-dark" : "inset-shadow-hair"}`}
    >
      {done && <Icon name="check" size={13} />}
    </span>
  );
}

function useWhen(): (at: string | null | undefined, withTime?: boolean) => string {
  const now = useNow();
  return (at, withTime = false) => {
    if (at === null || at === undefined) return "";
    const day = formatDate(at, { now });
    return withTime ? `${day}, ${formatTime(at)}` : day;
  };
}

function useDetail(item: ApprovalItemOut, enabled = true) {
  return useQuery({
    ...getApprovalOptions({ path: { kind: item.kind, item_id: item.id } }),
    enabled,
    retry: false,
  });
}

/** The decisions' common tail: refetch, and on 409 say the item changed. */
function useAfterDecision(): { onSuccess: () => void; onError: () => void } {
  const queryClient = useQueryClient();
  return {
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
    onError: () => {
      toast.show(COPY.changed);
      void queryClient.invalidateQueries();
    },
  };
}

function Lines({ detail }: { detail: ApprovalItemDetailOut }): JSX.Element | null {
  if (detail.lines.length === 0) return null;
  return (
    <table data-lines={detail.id} className="w-full text-[12.5px] tabular-nums">
      <thead>
        <tr className="h-[28px] bg-band-hd text-left text-meta font-medium text-ink-3">
          <th className="px-[10px] font-medium">{COPY.account}</th>
          <th className="px-[10px] text-right font-medium">{COPY.debit}</th>
          <th className="px-[10px] text-right font-medium">{COPY.credit}</th>
        </tr>
      </thead>
      <tbody>
        {detail.lines.map((l) => (
          <tr key={l.account} className="h-[32px] hairline-t">
            <td className="px-[10px]">{l.account}</td>
            <td className="px-[10px] text-right">{amount(l.debit ?? null, "money").text}</td>
            <td className="px-[10px] text-right">{amount(l.credit ?? null, "money").text}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Composer({
  item,
  prefill,
  onClose,
}: {
  item: ApprovalItemOut;
  prefill: string;
  onClose: () => void;
}): JSX.Element {
  const [body, setBody] = useState(prefill);
  const after = useAfterDecision();
  const ask = useMutation({
    ...askAboutItemMutation(),
    onSuccess: () => {
      after.onSuccess();
      onClose();
    },
  });
  return (
    <div data-composer={item.id} className="flex flex-col gap-[8px] px-[16px] pb-[12px]">
      <textarea
        aria-label={COPY.askEntry}
        value={body}
        onChange={(e) => {
          setBody(e.target.value);
        }}
        rows={3}
        className="w-full rounded-nested bg-card p-[10px] text-[12.5px] shadow-e1"
      />
      <div className="flex justify-end gap-[8px]">
        <Button size="sm" variant="ghost" onClick={onClose}>
          {COPY.cancel}
        </Button>
        <Button
          size="sm"
          disabled={body.trim() === "" || ask.isPending}
          onClick={() => {
            ask.mutate({
              path: { kind: item.kind, item_id: item.id },
              body: { body },
              headers: { "Idempotency-Key": `${item.id}:question:${body}` },
            });
          }}
        >
          {COPY.send}
        </Button>
      </div>
    </div>
  );
}

function DeclineSheet({
  title,
  codes,
  onClose,
  onDecline,
}: {
  title: string;
  /** The package's reason codes; an entry takes free text only. */
  codes: boolean;
  onClose: () => void;
  onDecline: (reason: keyof typeof COPY.reasons | null, note: string) => void;
}): JSX.Element {
  const [reason, setReason] = useState<keyof typeof COPY.reasons | null>(null);
  const [note, setNote] = useState("");
  const ready = codes ? reason !== null : note.trim() !== "";
  return (
    <SheetModal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={title}
      action={
        <Button
          size="sm"
          disabled={!ready}
          onClick={() => {
            onDecline(reason, note);
          }}
        >
          {title}
        </Button>
      }
    >
      <div data-sheet="decline" className="flex flex-col gap-[10px] p-[14px]">
        {codes && (
          <fieldset className="flex flex-col gap-[6px]">
            {(Object.keys(COPY.reasons) as (keyof typeof COPY.reasons)[]).map((code) => (
              <label key={code} className="flex items-center gap-[8px] text-[13px]">
                <input
                  type="radio"
                  name="reason"
                  checked={reason === code}
                  onChange={() => {
                    setReason(code);
                  }}
                />
                {COPY.reasons[code]}
              </label>
            ))}
          </fieldset>
        )}
        <label className="flex flex-col gap-[4px] text-[12.5px] text-ink-2">
          {codes ? COPY.note : COPY.entryReason}
          <textarea
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
            }}
            rows={3}
            className="rounded-nested bg-card p-[10px] text-[12.5px] text-ink shadow-e1"
          />
        </label>
      </div>
    </SheetModal>
  );
}

// --- Card A: the statement package ------------------------------------------------------------

function PackageCard({
  item,
  period,
  client,
  overlay,
  mobile,
  onNavigate,
}: {
  item: ApprovalItemOut;
  period: string;
  /** The client the statements are for: the person's scope (the toolbar's). */
  client: string;
  overlay: Overlay | undefined;
  mobile: boolean;
  onNavigate?: (area: string) => void;
}): JSX.Element {
  const when = useWhen();
  const branding = useBranding();
  const detail = useDetail(item);
  const after = useAfterDecision();
  const decide = useMutation({ ...decidePackageMutation(), ...after });
  const [confirm, setConfirm] = useState(overlay === "confirm");
  const [declining, setDeclining] = useState(overlay === "decline");
  const [asking, setAsking] = useState(false);
  const [sheet, setSheet] = useState(false);
  const d = detail.data;
  const canApprove = item.allowed_actions.includes("approve") && item.kind === "fs_package";
  const canDecline = item.allowed_actions.includes("decline") && item.kind === "fs_package";
  const send = (
    decision: "approve" | "decline",
    reason: keyof typeof COPY.reasons | null,
    note: string,
  ): void => {
    if (d === undefined) return;
    decide.mutate({
      path: { package_id: item.id },
      body: {
        decision,
        seen_hash: d.seen_hash,
        ...(reason === null ? {} : { reason_code: reason }),
        ...(note === "" ? {} : { note }),
      },
      headers: { "Idempotency-Key": key(item, d.seen_hash) },
    });
  };
  const firm = branding.data?.portal_name ?? branding.data?.firm_name ?? "";
  let sub: ReactNode = `${firm} · ${COPY.waitingSub}`;
  if (item.state === "approved") {
    sub = COPY.approvedBy(item.decided_by ?? "", when(item.decided_at, true));
  } else if (item.state === "declined") {
    sub = (
      <Pill variant="red-tint">
        {COPY.declinedBecause(item.reason_code ? COPY.reasons[item.reason_code] : COPY.declined)}
      </Pill>
    );
  }
  const body = (
    <>
      <ul>
        {(d?.parts ?? []).map((p) => (
          <li
            key={p.label}
            data-part={p.label}
            className="flex h-[40px] items-center gap-[8px] px-[16px] hairline-t"
          >
            <Icon name="file-text" size={14} className="text-ink-3" />
            <span className="flex-1 text-[13px]">{p.label}</span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                onNavigate?.("Deliverables");
              }}
            >
              {COPY.view}
            </Button>
          </li>
        ))}
      </ul>
      {d?.highlights !== null && d?.highlights !== undefined && (
        <p
          data-highlights
          className="mx-[12px] mb-[12px] rounded-nested bg-shell px-[16px] py-[10px] text-[12.5px] leading-[1.55] text-ink-2 inset-shadow-hair"
        >
          {d.highlights}
        </p>
      )}
      {d?.legend !== null && d?.legend !== undefined && (
        <p data-legend className="px-[16px] pb-[12px] text-[12.5px] text-ink-2">
          {d.legend}
        </p>
      )}
      {(canApprove || canDecline || item.allowed_actions.includes("ask")) && (
        <footer
          className={`flex gap-[8px] px-[16px] py-[12px] hairline-t ${mobile ? "flex-col" : ""}`}
        >
          {canApprove && (
            <Button
              size={mobile ? "lg" : "sm"}
              icon="check"
              onClick={() => {
                setConfirm(true);
              }}
            >
              {COPY.approve}
            </Button>
          )}
          {canDecline && (
            <Button
              size={mobile ? "lg" : "sm"}
              variant="secondary"
              opensDialog
              onClick={() => {
                setDeclining(true);
              }}
            >
              {COPY.decline}
            </Button>
          )}
          {item.allowed_actions.includes("ask") && !mobile && (
            <Button
              size="sm"
              variant="ghost"
              icon="message-circle"
              onClick={() => {
                setAsking(true);
              }}
            >
              {COPY.ask}
            </Button>
          )}
        </footer>
      )}
      {asking && (
        <Composer
          item={item}
          prefill={COPY.about(item.title, null, period)}
          onClose={() => {
            setAsking(false);
          }}
        />
      )}
    </>
  );
  const head = (
    <header className="flex min-h-[56px] items-center gap-[10px] px-[16px] py-[8px]">
      <Disc done={item.state === "approved"} />
      <div className="min-w-0 flex-1">
        <h3 className="text-[14px] font-medium">{item.title}</h3>
        <div className="text-[12.5px] text-ink-2">{sub}</div>
      </div>
      {d !== undefined && (d.parts ?? []).length > 0 && (
        <Pill variant="neutral">{COPY.parts((d.parts ?? []).length)}</Pill>
      )}
    </header>
  );
  return (
    <section
      aria-label={item.title}
      data-approval={item.kind}
      data-state={item.state}
      className="rounded-pane bg-card shadow-e1"
    >
      {head}
      {mobile ? (
        <>
          <p className="px-[16px] pb-[8px] text-meta text-ink-3">{COPY.reviewRequired}</p>
          <div className="p-[12px]">
            <Button
              size="lg"
              className="w-full"
              onClick={() => {
                setSheet(true);
              }}
            >
              {COPY.review}
            </Button>
          </div>
          <FullSheet open={sheet} onOpenChange={setSheet} title={item.title}>
            {body}
          </FullSheet>
        </>
      ) : (
        body
      )}
      <ConfirmDialog
        open={confirm && canApprove && d !== undefined}
        onOpenChange={setConfirm}
        title={COPY.approveTitle(item.title, client)}
        confirmLabel={COPY.approve}
        destructive={false}
        onConfirm={() => {
          send("approve", null, "");
        }}
      />
      {declining && canDecline && d !== undefined && (
        <DeclineSheet
          title={COPY.declineTitle}
          codes
          onClose={() => {
            setDeclining(false);
          }}
          onDecline={(reason, note) => {
            setDeclining(false);
            send("decline", reason, note);
          }}
        />
      )}
    </section>
  );
}

// --- the attest entries (e, e2) ---------------------------------------------------------------

function EntryCard({ item, period }: { item: ApprovalItemOut; period: string }): JSX.Element {
  const when = useWhen();
  const detail = useDetail(item);
  const after = useAfterDecision();
  const decide = useMutation({ ...decideProposedEntryMutation(), ...after });
  const [open, setOpen] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [asking, setAsking] = useState(false);
  const d = detail.data;
  const send = (decision: "accept" | "decline", reason: string | null): void => {
    if (d === undefined) return;
    decide.mutate({
      path: { entry_id: item.id },
      body: { decision, seen_hash: d.seen_hash, ...(reason === null ? {} : { reason }) },
      headers: { "Idempotency-Key": key(item, d.seen_hash) },
    });
  };
  let status: ReactNode = null;
  if (item.state === "accepted") {
    status = COPY.acceptedBy(item.decided_by ?? "", when(item.decided_at));
  } else if (item.state === "not_recorded" || item.state === "declined") {
    status = [COPY.notRecorded(when(item.decided_at)), d?.reason]
      .filter((s) => s !== null && s !== undefined && s !== "")
      .join(" · ");
  } else if (item.question_sent_at !== null && item.question_sent_at !== undefined) {
    status = COPY.questionSent(when(item.question_sent_at));
  }
  return (
    <section
      aria-label={item.title}
      data-approval="proposed_entry"
      data-entry={item.id}
      data-state={item.state}
      className="rounded-pane bg-card shadow-e1"
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className="flex min-h-[52px] w-full items-center gap-[10px] px-[16px] py-[8px] text-left"
      >
        <Disc done={item.state === "accepted"} />
        <span className="min-w-0 flex-1">
          <span className="block text-[14px]">{item.title}</span>
          {status !== null && <span className="block text-meta text-ink-3">{status}</span>}
        </span>
        <span className="text-[14px] font-medium tabular-nums">{money(item.amount)}</span>
      </button>
      {open && d !== undefined && (
        <div className="mx-[12px] mb-[10px] overflow-hidden rounded-nested bg-shell inset-shadow-hair">
          <Lines detail={d} />
        </div>
      )}
      {item.allowed_actions.some((a) => a !== "ask") && (
        <footer className="flex gap-[8px] px-[16px] py-[10px] hairline-t">
          {item.allowed_actions.includes("accept") && (
            <Button
              size="sm"
              disabled={d === undefined || decide.isPending}
              onClick={() => {
                send("accept", null);
              }}
            >
              {COPY.accept}
            </Button>
          )}
          {item.allowed_actions.includes("decline") && (
            <Button
              size="sm"
              variant="secondary"
              opensDialog
              onClick={() => {
                setDeclining(true);
              }}
            >
              {COPY.decline}
            </Button>
          )}
          {item.allowed_actions.includes("ask") && (
            <Button
              size="sm"
              variant="ghost"
              icon="message-circle"
              onClick={() => {
                setAsking(true);
              }}
            >
              {COPY.ask}
            </Button>
          )}
        </footer>
      )}
      {asking && (
        <Composer
          item={item}
          prefill={COPY.about(item.title, money(item.amount), period)}
          onClose={() => {
            setAsking(false);
          }}
        />
      )}
      {declining && d !== undefined && (
        <DeclineSheet
          title={COPY.declineEntryTitle}
          codes={false}
          onClose={() => {
            setDeclining(false);
          }}
          onDecline={(_, note) => {
            setDeclining(false);
            send("decline", note);
          }}
        />
      )}
    </section>
  );
}

// --- the acknowledgement of the entries not recorded (e2) -------------------------------------

function AcknowledgementCard({ item }: { item: ApprovalItemOut }): JSX.Element {
  const detail = useDetail(item);
  const after = useAfterDecision();
  const acknowledge = useMutation({ ...acknowledgeUncorrectedMutation(), ...after });
  const d = detail.data;
  const plus = d?.lines.find((l) => l.debit !== null && l.debit !== undefined)?.debit;
  const minus = d?.lines.find((l) => l.credit !== null && l.credit !== undefined)?.credit;
  // The sentence's three figures are the snapshot's; the browser only writes them out.
  const sentence =
    plus !== undefined && plus !== null && minus !== undefined && minus !== null
      ? COPY.acknowledgement(money(item.amount), money(plus), money(minus))
      : COPY.acknowledgementShort(money(item.amount));
  return (
    <section
      aria-label={item.title}
      data-approval="uncorrected_misstatements"
      data-state={item.state}
      className="rounded-pane bg-shell p-[14px] inset-shadow-hair"
    >
      <p className="text-[12.5px] leading-[1.55] text-ink-2">{sentence}</p>
      {item.allowed_actions.includes("acknowledge") && (
        <div className="pt-[10px]">
          <Button
            size="sm"
            variant="secondary"
            disabled={d === undefined || acknowledge.isPending}
            onClick={() => {
              if (d === undefined) return;
              acknowledge.mutate({
                path: { item_id: item.id },
                body: { seen_hash: d.seen_hash },
                headers: { "Idempotency-Key": key(item, d.seen_hash) },
              });
            }}
          >
            {COPY.acknowledge}
          </Button>
        </div>
      )}
      {item.state === "acknowledged" && (
        <div className="pt-[8px]">
          <RegistryStatus object="client_approval_item" code="acknowledged" client />
        </div>
      )}
    </section>
  );
}

// --- Card B: the entries the firm posted (read-only) ------------------------------------------

function PostedRow({
  item,
  period,
  expanded,
  asking,
}: {
  item: ApprovalItemOut;
  period: string;
  expanded: boolean;
  asking: boolean;
}): JSX.Element {
  const when = useWhen();
  const [open, setOpen] = useState(expanded);
  const [ask, setAsk] = useState(asking);
  const detail = useDetail(item, open);
  const d = detail.data;
  return (
    <li data-posted={item.id} className="hairline-t first:shadow-none">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className="flex min-h-[52px] w-full items-center gap-[10px] px-[16px] py-[6px] text-left"
      >
        <Disc done />
        <span className="min-w-0 flex-1">
          <span className="block text-[14px]">{item.title}</span>
          {item.question_sent_at !== null && item.question_sent_at !== undefined && (
            <span className="block text-meta text-ink-3">
              {COPY.questionSent(when(item.question_sent_at))}
            </span>
          )}
        </span>
        <span className="text-[14px] font-medium tabular-nums">{dollars(item.amount)}</span>
      </button>
      {open && d !== undefined && (
        <div className="mx-[12px] mb-[10px] overflow-hidden rounded-nested bg-shell inset-shadow-hair">
          <Lines detail={d} />
          {(d.support ?? []).length > 0 && (
            <div className="flex flex-wrap gap-[6px] p-[10px]">
              {(d.support ?? []).map((s) => (
                <span
                  key={s.label}
                  data-support
                  className="inline-flex h-[28px] items-center gap-[6px] rounded-nested bg-card px-[8px] text-dense shadow-e1"
                >
                  <Icon name="file-text" size={13} className="text-ink-3" />
                  {s.label}
                </span>
              ))}
            </div>
          )}
          <div className="flex justify-end p-[8px]">
            <Button
              size="sm"
              variant="ghost"
              icon="message-circle"
              onClick={() => {
                setAsk(true);
              }}
            >
              {COPY.askEntry}
            </Button>
          </div>
        </div>
      )}
      {ask && (
        <Composer
          item={item}
          prefill={COPY.about(item.title, money(item.amount), period)}
          onClose={() => {
            setAsk(false);
          }}
        />
      )}
    </li>
  );
}

function PostedCard({
  context,
  period,
  month,
  expanded,
  asking,
}: {
  context: string | undefined;
  period: string;
  /** The period's month, as the card names it ("Entries posted for August"). */
  month: string;
  expanded: number | undefined;
  asking: boolean;
}): JSX.Element | null {
  const posted = useQuery({
    ...listApprovalsOptions({
      query: { filter: "posted", ...(context === undefined ? {} : { context }) },
    }),
    retry: false,
  });
  const items = posted.data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <section
      aria-label={COPY.postedEntries(month, items.length)}
      className="rounded-pane bg-card shadow-e1"
    >
      <h3 className="flex h-[46px] items-center px-[16px] text-[14px] font-medium">
        {COPY.postedEntries(month, items.length)}
      </h3>
      <ul>
        {items.map((item, i) => (
          <PostedRow
            key={item.id}
            item={item}
            period={period}
            expanded={expanded === i}
            asking={asking && expanded === i}
          />
        ))}
      </ul>
    </section>
  );
}

// --- the rail ---------------------------------------------------------------------------------

/** "August 2026 Close" → "August"; a period's month, as the rail's filter names it. */
function monthOf(label: string): string {
  return label.split(" ")[0] ?? label;
}

function Rail({
  data,
  context,
  client,
  filter,
  onFilter,
}: {
  data: ApprovalsOut;
  client: string;
  context: ApprovalContextOut | undefined;
  filter: Filter | undefined;
  onFilter: (f: Filter | undefined) => void;
}): JSX.Element {
  const rows: { f: Filter; label: string; n: number }[] = [
    { f: "waiting", label: COPY.waiting, n: data.counts.waiting },
    ...(data.counts.posted > 0
      ? [
          {
            f: "posted" as const,
            label: COPY.posted(monthOf(context?.label ?? "")),
            n: data.counts.posted,
          },
        ]
      : []),
    { f: "approved", label: COPY.approved, n: data.counts.approved },
    { f: "declined", label: COPY.declined, n: data.counts.declined },
  ];
  const later = data.contexts.filter((c) => c.key !== context?.key && c.state === null);
  return (
    <nav aria-label={COPY.title} className="flex flex-col gap-[8px]">
      {context !== undefined && (
        <div
          data-period={context.key}
          className="flex items-center gap-[10px] rounded-pane bg-shell px-[12px] py-[14px] inset-shadow-hair"
        >
          <span className="inline-flex size-[34px] items-center justify-center rounded-nested bg-espresso text-on-dark">
            <Icon name="book-open" size={17} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[13.5px] font-medium">{context.label}</span>
            <span className="block text-meta text-ink-3">{client}</span>
          </span>
          {context.state !== null && context.state !== undefined && (
            <RegistryStatus object="client_approval_item" code={context.state} client />
          )}
        </div>
      )}
      <ul>
        {rows.map((r) => {
          const on = (filter ?? "waiting") === r.f;
          return (
            <li key={r.f}>
              <button
                type="button"
                data-filter={r.f}
                aria-current={on ? "true" : undefined}
                onClick={() => {
                  onFilter(r.f === "waiting" ? undefined : r.f);
                }}
                className={`flex h-[39px] w-full items-center rounded-nested px-[10px] text-left text-body ${on ? "bg-sel-bg" : "hover:bg-nested"}`}
              >
                <span className="flex-1">{r.label}</span>
                <span className="inline-flex h-[19px] min-w-[19px] items-center justify-center rounded-pill bg-nested px-[6px] text-meta tabular-nums">
                  {r.n}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {later.length > 0 && (
        <section aria-label={COPY.comingNext}>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[10px] text-dense font-medium">
            {COPY.comingNext}
          </h3>
          <ul>
            {later.map((c) => (
              <li
                key={c.key}
                data-coming-next
                className="flex h-[46px] items-center gap-[8px] px-[10px]"
              >
                <Disc done={false} />
                <span className="text-body">{c.label}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </nav>
  );
}

// --- the screen -------------------------------------------------------------------------------

async function save(blob: Blob, name: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
  await Promise.resolve();
}

function Approvals(props: Por08Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const branding = useBranding();
  const mobile = props.mobile === true;
  const [context, setContext] = useState(props.context);
  const [filter, setFilter] = useState<Filter | undefined>(props.filter);
  const query = {
    ...(context === undefined ? {} : { context }),
    ...(filter === undefined || filter === "waiting" || filter === "posted" ? {} : { filter }),
  };
  const listed = useQuery({ ...listApprovalsOptions({ query }), retry: false });
  const data = listed.data;
  const current = data?.contexts.find((c) => c.key === context) ?? data?.contexts[0];
  const period = current?.label ?? "";
  const flagOff = listed.isError && isFlagOff(listed.error);
  const items = data?.items ?? [];
  const empty =
    data !== undefined && items.length === 0 && data.counts.posted === 0 && filter === undefined;
  const packages = items.filter((i) => i.kind === "fs_package" || i.kind === "fs_draft");
  const entries = items.filter((i) => i.kind === "proposed_entry");
  const acknowledgements = items.filter((i) => i.kind === "uncorrected_misstatements");
  const journalOf = packages[0] ?? entries[0];
  const download = async (): Promise<void> => {
    if (journalOf === undefined) return;
    try {
      await entriesJournal({
        path: { kind: journalOf.kind, item_id: journalOf.id },
        throwOnError: true,
      });
      const { data: file } = await entriesJournalFile({
        path: { kind: journalOf.kind, item_id: journalOf.id },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(file, `${period}.pdf`);
    } catch {
      toast.show(COPY.downloadFailed);
    }
  };

  let main: ReactNode = null;
  if (flagOff) {
    main = <EmptyState title={COPY.flagOff} icon="circle-check" />;
  } else if (empty) {
    main = (
      <EmptyState title={COPY.empty} icon="circle-check">
        {COPY.emptyBody(branding.data?.portal_name ?? branding.data?.firm_name ?? "")}
      </EmptyState>
    );
  } else if (data !== undefined) {
    main = (
      <>
        {!mobile && (
          <header className="flex h-[46px] shrink-0 items-center gap-[10px] px-[12px] hairline-b">
            {data.contexts.length > 1 ? (
              <Picker
                label={COPY.period}
                variant="fill"
                value={current?.key ?? ""}
                options={data.contexts.map((c) => ({ value: c.key, label: c.label }))}
                onChange={setContext}
              />
            ) : (
              <span className="inline-flex h-[29px] items-center rounded-nested bg-nested px-[10px] text-dense">
                {period}
              </span>
            )}
            <h2 className="mx-auto text-[14.5px] font-medium">{COPY.title}</h2>
            {journalOf !== undefined && (
              <Button
                size="sm"
                variant="ghost"
                icon="download"
                onClick={() => {
                  void download();
                }}
              >
                {COPY.downloadEntries}
              </Button>
            )}
          </header>
        )}
        <div className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-y-auto bg-shell p-[8px]">
          {filter !== "posted" &&
            packages.map((p) => (
              <PackageCard
                key={p.id}
                item={p}
                period={period}
                client={bar?.scope?.label ?? ""}
                overlay={props.overlay}
                mobile={mobile}
                {...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate })}
              />
            ))}
          {filter !== "posted" && entries.length > 0 && (
            <p className="px-[4px] text-[12.5px] leading-[1.55] text-ink-2">{COPY.attestIntro}</p>
          )}
          {filter !== "posted" &&
            entries.map((e) => <EntryCard key={e.id} item={e} period={period} />)}
          {filter !== "posted" &&
            acknowledgements.map((a) => <AcknowledgementCard key={a.id} item={a} />)}
          {(filter === undefined || filter === "posted") && data.counts.posted > 0 && (
            <PostedCard
              context={context}
              period={period}
              month={monthOf(period)}
              expanded={props.expanded}
              asking={props.overlay === "ask"}
            />
          )}
        </div>
      </>
    );
  }

  return (
    <PortalLayout
      variant={mobile ? "mobile" : "split"}
      user={bar?.user ?? ""}
      nav={bar?.nav ?? []}
      active={COPY.active}
      frame={props.frame === true}
      {...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate })}
    >
      <div
        data-screen="POR-08"
        className={`flex min-h-0 flex-1 gap-[10px] ${mobile ? "flex-col" : ""}`}
      >
        {!mobile && data !== undefined && !flagOff && !empty && (
          <section
            aria-label={COPY.title}
            className="w-[336px] shrink-0 overflow-y-auto rounded-pane bg-card p-[10px] shadow-e2"
          >
            <h2 className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
              {COPY.title}
            </h2>
            <Rail
              data={data}
              context={current}
              client={bar?.scope?.label ?? ""}
              filter={filter}
              onFilter={setFilter}
            />
          </section>
        )}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2">
          {main}
        </div>
      </div>
    </PortalLayout>
  );
}

export function POR08(props: Por08Props = {}): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <Approvals {...props} />
    </PortalBrandProvider>
  );
}
