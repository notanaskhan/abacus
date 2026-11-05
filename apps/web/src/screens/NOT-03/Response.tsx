import type { BlockOut, NoticeOut, ResponseOut } from "@abacus/api-client";
import {
  agencyReplyMutation,
  markSentMutation,
  responseEditMutation,
  responseOptions,
  responseRegenerateMutation,
  sendForSignatureMutation,
} from "@abacus/api-client/query";
import { Button, PaperCard, Pill, Skeleton, Toggle, amount, cn } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { COPY } from "./copy";

// NOT-03 · Response letter editor & approval (N-04-T20; N-04 US-5; the handoff spec): T10 document on
// the well (structure 470 · paper 896) under NOT-02's Response tab. Blocks and amounts are the
// server's, so every figure equals NOT-02. The primary control follows `readiness`: Approve…, Send for
// client signature…, Mark as sent… Each is a person's control: Approve only opens SHL-12 (`onApprove`),
// and no agent reaches these writes (the matrix denies them). Nothing is sent to an agency from here:
// Mark as sent records what the firm sent through DUT, fax or mail.

const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? "—" : amount(v, "cents").text;

const PANE = "flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e1";

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section data-band={title}>
      <h4 className="flex h-[31px] items-center bg-band-hd px-[14px] text-[13.5px] font-medium hairline-b">
        {title}
      </h4>
      {children}
    </section>
  );
}

function Kv({ k, v, strong = false }: { k: string; v: ReactNode; strong?: boolean }): JSX.Element {
  return (
    <div
      className={cn(
        "flex min-h-[33px] items-center justify-between gap-[12px] px-[14px] text-[13px] hairline-b",
        strong && "font-medium",
      )}
    >
      <span className="text-ink-2">{k}</span>
      <span className="text-right tabular-nums">{v}</span>
    </div>
  );
}

function Disc({ state }: { state: ResponseOut["approvals"][number]["state"] }): JSX.Element {
  return (
    <span
      data-disc={state}
      aria-hidden="true"
      className={cn(
        "inline-block size-[15px] rounded-full",
        state === "done" && "bg-green",
        state === "in_progress" && "bg-gradient-to-r from-green to-green/0 ring-[1px] ring-green",
        state === "pending" && "ring-[1px] ring-ink-3",
        state === "stale" && "bg-amber",
      )}
    />
  );
}

function Structure({
  found,
  notice,
  onDecision,
  onEnclosure,
}: {
  found: ResponseOut;
  notice: NoticeOut;
  onDecision?: () => void;
  onEnclosure: (n: number, on: boolean) => void;
}): JSX.Element {
  const payment = found.payment;
  const amounts = payment?.amounts;
  const position = found.position === null ? null : COPY.position[found.position];
  return (
    <aside data-not03="structure" className={cn(PANE, "w-[470px] shrink-0 overflow-y-auto")}>
      <div className="flex h-[32px] items-center bg-band-hd px-[14px] text-[12.5px] font-medium text-ink-2">
        {COPY.breadcrumb}
      </div>
      <Band title={COPY.bands.position}>
        <Kv
          k={COPY.position.decision}
          v={
            position === null ? (
              <span className="text-amber-ink">{COPY.position.pending}</span>
            ) : (
              <button type="button" className="text-ink" onClick={onDecision}>
                {position} <span className="text-ink-3">→</span>
              </button>
            )
          }
        />
      </Band>
      {amounts !== undefined && (
        <Band title={COPY.bands.payment}>
          <Kv k={COPY.payment.tax} v={money(amounts.tax)} />
          <Kv k={COPY.payment.interest} v={money(amounts.interest)} />
          <Kv k={COPY.payment.penalty} v={money(amounts.penalty)} />
          <Kv
            k={COPY.payment.total}
            v={<span data-not03="total">{money(amounts.total)}</span>}
            strong
          />
          {payment?.method_label != null && (
            <Kv k={COPY.payment.method} v={COPY.payment.methods[payment.method_label]} />
          )}
        </Band>
      )}
      <Band title={COPY.bands.signers}>
        <p className="px-[14px] py-[6px] text-[11.5px] text-ink-3">{COPY.signersHelper}</p>
      </Band>
      <Band title={COPY.bands.enclosures}>
        {found.enclosures.map((e) => (
          <div
            key={e.n}
            data-enclosure={e.n}
            className="flex h-[34px] items-center justify-between px-[14px] text-[13px] hairline-b"
          >
            <span>
              {e.n} {e.label}
            </span>
            <Toggle
              label={e.label}
              checked={e.on}
              disabled={found.locked}
              onChange={(on) => {
                onEnclosure(e.n, on);
              }}
            />
          </div>
        ))}
      </Band>
      <Band title={COPY.bands.send}>
        <Kv
          k={COPY.send.channel}
          v={found.channel === null ? "—" : COPY.send.channels[found.channel]}
        />
        <Kv k={COPY.send.followUp} v={COPY.send.followUpValue(found.follow_up_days)} />
        <Kv k={COPY.send.owner} v={found.owner?.name ?? notice.row.assignee?.name ?? "—"} />
      </Band>
      <Band title={COPY.bands.approvals}>
        {found.approvals.map((step) => (
          <div
            key={step.level}
            data-approval={step.level}
            className="flex h-[33px] items-center gap-[8px] px-[14px] text-[13px] hairline-b"
          >
            <Disc state={step.state} />
            <span>{step.level}</span>
            {step.person !== null && <span className="text-ink-3">{step.person.initials}</span>}
          </div>
        ))}
      </Band>
    </aside>
  );
}

function Paragraph({ block }: { block: BlockOut }): JSX.Element {
  return (
    <p
      data-block={block.key}
      data-origin={block.origin}
      className="mb-[10px] text-[12px] leading-[1.55]"
    >
      {block.text}
      {block.citation_ids.map((id, i) => (
        <span
          key={id}
          className="ml-[3px] rounded-[3px] bg-chip px-[4px] text-[10.5px] hover:bg-match-bg"
        >
          {i + 1}
        </span>
      ))}
      {block.edited && <span className="ml-[4px] text-[10.5px] text-ink-3">edited</span>}
    </p>
  );
}

function MarkSentSheet({
  noticeId,
  found,
  onDone,
}: {
  noticeId: string;
  found: ResponseOut;
  onDone: () => void;
}): JSX.Element {
  const client = useQueryClient();
  const [confirmation, setConfirmation] = useState("");
  const [sentOn, setSentOn] = useState("2026-09-17");
  const send = useMutation({
    ...markSentMutation(),
    onSuccess: () => {
      void client.invalidateQueries();
      onDone();
    },
  });
  return (
    <form
      data-not03="mark-sent"
      aria-label={COPY.sent.title}
      className="flex flex-col gap-[8px] p-[14px] hairline-t"
      onSubmit={(event) => {
        event.preventDefault();
        send.mutate({
          path: { notice_id: noticeId },
          body: {
            channel: found.channel ?? "dut",
            sent_on: sentOn,
            ...(confirmation === "" ? {} : { confirmation_no: confirmation }),
            follow_up_days: found.follow_up_days,
          },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        });
      }}
    >
      <label className="text-[12.5px]">
        {COPY.sent.confirmation}
        <input
          className="ml-[8px] rounded-[6px] px-[6px] ring-[1px] ring-hair"
          value={confirmation}
          onChange={(event) => {
            setConfirmation(event.target.value);
          }}
        />
      </label>
      <label className="text-[12.5px]">
        {COPY.sent.sentOn}
        <input
          type="date"
          className="ml-[8px] rounded-[6px] px-[6px] ring-[1px] ring-hair"
          value={sentOn}
          onChange={(event) => {
            setSentOn(event.target.value);
          }}
        />
      </label>
      <Button type="submit" variant="primary" disabled={send.isPending}>
        {COPY.sent.submit}
      </Button>
    </form>
  );
}

function ReplySheet({ noticeId, onDone }: { noticeId: string; onDone: () => void }): JSX.Element {
  const client = useQueryClient();
  const reply = useMutation({
    ...agencyReplyMutation(),
    onSuccess: () => {
      void client.invalidateQueries();
      onDone();
    },
  });
  const save = (outcome: "resolved" | "escalated"): void => {
    reply.mutate({
      path: { notice_id: noticeId },
      body: { outcome, ...(outcome === "resolved" ? { closed_on: "2026-12-02" } : {}) },
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  };
  return (
    <div data-not03="reply" className="flex gap-[8px] p-[14px] hairline-t">
      <Button
        variant="secondary"
        onClick={() => {
          save("resolved");
        }}
      >
        {COPY.reply.resolved}
      </Button>
      <Button
        variant="secondary"
        onClick={() => {
          save("escalated");
        }}
      >
        {COPY.reply.escalated}
      </Button>
    </div>
  );
}

export interface ResponseEditorProps {
  noticeId: string;
  notice: NoticeOut;
  /** SHL-12: Approve… only opens the sign-off, as a person. */
  onApprove?: () => void;
  /** SIG-02 d, on the envelope the server drafted. */
  onEnvelope?: (envelopeId: string) => void;
  onDecision?: () => void;
}

export function ResponseEditor({
  noticeId,
  notice,
  onApprove,
  onEnvelope,
  onDecision,
}: ResponseEditorProps): JSX.Element {
  const client = useQueryClient();
  const [sheet, setSheet] = useState<"sent" | "reply" | null>(null);
  const query = useQuery(responseOptions({ path: { notice_id: noticeId } }));
  const refresh = (): void => {
    void client.invalidateQueries();
  };
  const edit = useMutation({ ...responseEditMutation(), onSuccess: refresh });
  const regenerate = useMutation({ ...responseRegenerateMutation(), onSuccess: refresh });
  const signature = useMutation({
    ...sendForSignatureMutation(),
    onSuccess: (made) => {
      refresh();
      onEnvelope?.(made.envelope_id);
    },
  });
  const found = query.data;
  if (found === undefined) return <Skeleton className="m-[12px] h-[420px] flex-1" />;
  const watermark = found.readiness === "waiting_decision" || found.readiness === "in_review";
  const version = found.row_version;
  const primary = (): JSX.Element | null => {
    switch (found.readiness) {
      case "waiting_decision":
        return (
          <span className="flex items-center gap-[8px]">
            <span data-not03="blocked" className="text-[12px] text-ink-3">
              {COPY.position.pending}
            </span>
            <Button variant="primary" size="sm" disabled>
              {COPY.approve}
            </Button>
          </span>
        );
      case "in_review":
        return (
          <Button
            variant="primary"
            size="sm"
            {...(onApprove === undefined ? {} : { onClick: onApprove })}
          >
            {COPY.approve}
          </Button>
        );
      case "approved":
        return (
          <Button
            variant="primary"
            size="sm"
            disabled={signature.isPending}
            onClick={() => {
              signature.mutate({
                path: { notice_id: noticeId },
                headers: { "Idempotency-Key": crypto.randomUUID() },
              });
            }}
          >
            {COPY.sendForSignature}
          </Button>
        );
      case "out_for_signature":
        return (
          <Pill size="chip" variant="neutral">
            {COPY.envelope.sent}
          </Pill>
        );
      case "ready_to_send":
        return (
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setSheet("sent");
            }}
          >
            {COPY.markSent}
          </Button>
        );
      case "sent":
        return (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setSheet("reply");
            }}
          >
            {COPY.logReply}
          </Button>
        );
    }
  };
  return (
    <div
      data-screen="NOT-03"
      data-readiness={found.readiness}
      className="flex min-h-0 flex-1 gap-[10px] p-[10px]"
    >
      <Structure
        found={found}
        notice={notice}
        {...(onDecision === undefined ? {} : { onDecision })}
        onEnclosure={(n, on) => {
          edit.mutate({
            path: { notice_id: noticeId },
            body: { enclosures: [{ n, on }] },
            headers: { "If-Match": version },
          });
        }}
      />
      <section data-not03="paper" className={cn(PANE, "min-w-0 flex-1")}>
        <header className="relative flex h-[46px] shrink-0 items-center justify-center text-pane-title font-medium hairline-b">
          {COPY.paper}
          <span className="absolute right-[10px] flex items-center gap-[6px] font-normal">
            {!found.locked && (
              <Button
                variant="ghost"
                size="sm"
                disabled={regenerate.isPending}
                onClick={() => {
                  regenerate.mutate({
                    path: { notice_id: noticeId },
                    headers: { "If-Match": version },
                  });
                }}
              >
                {COPY.regenerate}
              </Button>
            )}
            {primary()}
          </span>
        </header>
        {found.position_mismatch && (
          <div
            role="status"
            data-not03="mismatch"
            className="bg-amber-tint px-[14px] py-[6px] text-[12.5px] text-amber-ink"
          >
            {COPY.mismatch}
          </div>
        )}
        {found.readiness === "out_for_signature" && (
          <div
            role="status"
            data-not03="waiting"
            className="bg-shell px-[14px] py-[6px] text-[12.5px] text-ink-2"
          >
            {COPY.envelope.waiting}
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto bg-shell p-[14px]">
          <PaperCard {...(watermark ? { watermark: COPY.draftWatermark } : {})}>
            {found.blocks.map((block) => (
              <Paragraph key={block.key} block={block} />
            ))}
          </PaperCard>
        </div>
        {sheet === "sent" && (
          <MarkSentSheet
            noticeId={noticeId}
            found={found}
            onDone={() => {
              setSheet(null);
            }}
          />
        )}
        {sheet === "reply" && (
          <ReplySheet
            noticeId={noticeId}
            onDone={() => {
              setSheet(null);
            }}
          />
        )}
      </section>
    </div>
  );
}
