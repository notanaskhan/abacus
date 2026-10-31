import type {
  DeliveryOut,
  DeliveryPacketOut,
  EfileAckOut,
  EnvelopeOut,
  FinalApprovalOut,
  SignerOut,
} from "@abacus/api-client";
import {
  approvePacketMutation,
  deliveryOptions,
  finalApprovalOptions,
  getEnvelopeOptions,
  patchPacketMutation,
  recordTransmissionMutation,
  regenerateLetterMutation,
  remindEnvelopesSendMutation,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  dateTime,
  Dialog,
  EmptyState,
  Icon,
  type Phase,
  Pill,
  RecordRail,
  Toggle,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

// TAX-12 · Delivery & e-file, part 1 (T-01-T24; docs/screens/TAX-12.md): the T2 cockpit's
// Delivery rail (nine checklist rows with discs and sub-lines) and the canvas for the selected
// row. Built here: the E-file authorizations canvas (the C7 envelope card with per-signer KBA rows
// and the evidence footer, the packet card, payment instructions, the transmission gate and
// acknowledgments) in states a, a2 (the pre-approved reminder, Grace sends) and b (blocked before
// final approval). Accrued records; the ERO transmits in CCH Axcess (R-04, D1): the gate is a
// person's record and stays locked until every signer has signed.
// Part 2 (T-01-T39, fixture mode): c and c2 (the gate opens; Daniel, the ERO, records the
// transmission through a confirm that names the four jurisdictions and the date; Grace waits with
// Notify), d (Accepted: the acknowledgment timeline, Delivered to portal, the estimate reminders
// row), e (Rejected with the engine's code and text, Create issue to TAX-06, and the agent's fix
// card only in fixture builds: chapter 04 §2.1 rule 4, until T-04-T09's flag exists), and the
// packet editor (voucher toggles, Regenerate letter, Approve for the signer or a manager).

/** The agent's fix card exists only in fixture builds (no `tax_agents.enabled` until S33). */
export const FIXTURE_BUILD = import.meta.env.VITE_FIXTURES === "1";
const JURISDICTIONS = ["federal", "NY", "IL", "CO"];
const TRANSMITTED_ON = "2026-09-18";

type Step =
  | "final-approval"
  | "exported"
  | "diagnostics"
  | "packet"
  | "authorizations"
  | "payments"
  | "transmission"
  | "acks"
  | "delivery";

const APPROVED_AT = "Sep 16, 11:20 AM";

function signedCount(envelope: EnvelopeOut | undefined): [number, number] {
  const signers = envelope?.signers ?? [];
  return [signers.filter((s) => s.status === "signed").length, signers.length];
}

function phases(
  approval: FinalApprovalOut | undefined,
  envelope: EnvelopeOut | undefined,
  delivery: DeliveryOut | undefined,
): Phase[] {
  const acks = delivery?.acks ?? [];
  const accepted = acks.length > 0 && acks.every((a) => a.status === "accepted");
  const rejected = acks.some((a) => a.status === "rejected");
  const approved = approval?.approved_at != null;
  const [signed, total] = signedCount(envelope);
  const all = total > 0 && signed === total;
  const later = (id: Step, title: string, sub: string, done = false): Phase => ({
    id,
    title,
    disc: approved && done ? "done" : "todo",
    live: { text: sub },
  });
  return [
    {
      id: "final-approval",
      title: COPY.rows.finalApproval,
      disc: approved ? "done" : "warn",
      live: approved
        ? { text: COPY.rows.approvedBy("Daniel Reyes", APPROVED_AT) }
        : { text: COPY.rows.blockedK1, tone: "amber" },
    },
    later("exported", COPY.rows.exported, COPY.rows.exportedSub, true),
    later("diagnostics", COPY.rows.diagnostics, COPY.rows.diagnosticsSub, true),
    later("packet", COPY.rows.packet, COPY.rows.packetSub, true),
    approved
      ? {
          id: "authorizations",
          title: COPY.rows.authorizations,
          disc: all ? "done" : "half",
          live: { text: COPY.rows.authorizationsSub(signed, total), tone: "amber" },
        }
      : later("authorizations", COPY.rows.authorizations, COPY.rows.authorizationsSub(0, 2)),
    later("payments", COPY.rows.payments, COPY.rows.paymentsSub, true),
    later("transmission", COPY.rows.transmission, COPY.rows.transmissionSub),
    rejected
      ? {
          id: "acks",
          title: COPY.rows.acks,
          disc: "warn",
          live: { text: COPY.status.rejected, tone: "amber" },
        }
      : later(
          "acks",
          COPY.rows.acks,
          accepted ? COPY.status.accepted : COPY.rows.acksSub,
          accepted,
        ),
    accepted
      ? { id: "delivery", title: COPY.rows.delivery, disc: "done", live: { text: COPY.delivered } }
      : later("delivery", COPY.rows.delivery, COPY.rows.deliverySub),
  ];
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2);
}

function SignerRow({ signer }: { signer: SignerOut }): JSX.Element {
  const signed = signer.status === "signed";
  return (
    <li className="flex h-[52px] items-center gap-[10px] px-[14px] [&+&]:border-t [&+&]:border-hair">
      <span
        aria-hidden
        className="flex size-[24px] items-center justify-center rounded-full bg-nested text-[11px] font-medium"
      >
        {initials(signer.name)}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[13px] font-medium">
          {signer.name}
          {signer.title ? ` (${signer.title})` : ""}
        </span>
        <span className="truncate text-[11.5px] text-ink-3">
          {signed
            ? signer.name === "Jonah Feld"
              ? "Signed · KBA passed 4 of 4 · Sep 17, 6:12 PM"
              : COPY.envelope.claire
            : COPY.envelope.jonah}
        </span>
      </span>
      <Pill variant={signed ? "green" : "amber"}>
        {signed ? COPY.envelope.signed : COPY.envelope.viewed}
      </Pill>
    </li>
  );
}

function Card({ title, children }: { title: string; children: JSX.Element }): JSX.Element {
  return (
    <section aria-label={title} className="rounded-[12px] bg-card shadow-e1">
      <h3 className="flex h-[40px] items-center px-[14px] text-[13.5px] font-medium">{title}</h3>
      {children}
    </section>
  );
}

function Reminder({
  open,
  onOpenChange,
  envelopeId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  envelopeId: string;
}): JSX.Element {
  const send = useMutation({
    ...remindEnvelopesSendMutation(),
    onSuccess: () => {
      toast.show(COPY.reminder.sent);
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={COPY.reminder.title}>
      <div className="flex flex-col gap-[10px]">
        <dl className="rounded-[10px] bg-card shadow-e1">
          <div className="flex items-center gap-[12px] px-[14px] py-[10px]">
            <dt className="w-[96px] text-[12.5px] text-ink-2">{COPY.reminder.toLabel}</dt>
            <dd className="flex-1 text-[13px] font-medium">{COPY.reminder.recipient}</dd>
            <dd className="text-[12px] text-ink-3">{COPY.reminder.channel}</dd>
          </div>
          <div className="flex items-center gap-[12px] border-t border-hair px-[14px] py-[10px]">
            <dt className="w-[96px] text-[12.5px] text-ink-2">{COPY.reminder.template}</dt>
            <dd className="flex-1 text-[13px]">{COPY.reminder.templateName}</dd>
            <dd>
              <Pill variant="green-tint">{COPY.reminder.approved}</Pill>
            </dd>
          </div>
        </dl>
        <article className="rounded-[10px] bg-card px-[16px] py-[14px] shadow-e1">
          <h4 className="text-[13.5px] font-medium">{COPY.reminder.templateName}</h4>
          <p className="mt-[8px] text-[12.5px] leading-[1.55] text-ink-2">{COPY.reminder.body}</p>
          <p className="mt-[8px] text-[12.5px] text-ink-2">{COPY.reminder.signature}</p>
        </article>
        <div className="flex items-center gap-[8px]">
          <span className="flex-1 text-[11.5px] text-ink-3">{COPY.reminder.footer}</span>
          <Button
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            {COPY.reminder.cancel}
          </Button>
          <Button
            variant="primary"
            icon="send"
            disabled={send.isPending}
            onClick={() => {
              send.mutate({
                body: { envelope_ids: [envelopeId] },
                headers: { "Idempotency-Key": `remind:${envelopeId}:tax12` },
              });
            }}
          >
            {COPY.reminder.send}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function jurisdictionName(code: string): string {
  return COPY.jurisdictions[code] ?? code;
}

function time(iso: string): string {
  return dateTime(iso, { tz: "America/Chicago" });
}

function Gate({
  envelope,
  delivery,
  returnId,
}: {
  envelope: EnvelopeOut;
  delivery: DeliveryOut | undefined;
  returnId: string;
}): JSX.Element {
  const [confirming, setConfirming] = useState(false);
  const record = useMutation({
    ...recordTransmissionMutation(),
    onSuccess: () => {
      toast.show(COPY.ero.recorded);
    },
  });
  const completed = envelope.row.status === "completed";
  const ero = delivery?.allowed_actions.includes("transmission.record") ?? false;
  const transmitted = delivery?.transmitted_on != null;
  return (
    <div className="flex flex-col gap-[8px] border-t border-hair px-[14px] py-[12px]">
      {!completed || transmitted ? (
        <Button variant="primary" icon="lock" disabled className="w-full">
          {COPY.gate.button}
        </Button>
      ) : ero ? (
        <Button
          variant="primary"
          className="w-full"
          aria-haspopup="dialog"
          onClick={() => {
            setConfirming(true);
          }}
        >
          {COPY.gate.button}
        </Button>
      ) : (
        <div className="flex items-center gap-[8px]">
          <span className="flex-1 text-[13px]">{COPY.ero.waiting}</span>
          <Button variant="secondary" size="sm" icon="bell">
            {COPY.ero.notify}
          </Button>
        </div>
      )}
      <p className="text-[12px] text-ink-2">{COPY.gate.body}</p>
      <p className="text-[11.5px] text-ink-3">{COPY.gate.who}</p>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={COPY.ero.confirmTitle}
        confirmLabel={COPY.ero.record}
        cancelLabel={COPY.ero.cancel}
        destructive={false}
        onConfirm={() => {
          record.mutate({
            path: { return_id: returnId },
            body: {
              jurisdictions: JURISDICTIONS,
              transmitted_on: TRANSMITTED_ON,
              method: "practitioner_pin",
              seen_binding_id: delivery?.binding_id ?? "",
            },
            headers: { "Idempotency-Key": `transmission:${returnId}:${TRANSMITTED_ON}` },
          });
        }}
      >
        {COPY.ero.confirm}
      </ConfirmDialog>
    </div>
  );
}

function Acks({ acks }: { acks: EfileAckOut[] }): JSX.Element {
  if (acks.length === 0) {
    return (
      <p className="border-t border-hair px-[14px] py-[12px] text-[12.5px] text-ink-3">
        {COPY.acks.none}
      </p>
    );
  }
  const rejected = acks.find((a) => a.status === "rejected");
  return (
    <div className="border-t border-hair">
      <ol aria-label={COPY.acks.title}>
        {acks.map((a) =>
          a.status === "accepted" ? (
            <li key={a.id} className="flex gap-[10px] px-[14px] py-[8px]">
              <Icon name="check" size={14} />
              <span className="w-[110px] shrink-0 text-[11.5px] text-ink-3">
                {time(a.received_at)}
              </span>
              <span className="flex flex-col">
                <span className="text-[12.5px]">
                  {COPY.acks.accepted(jurisdictionName(a.jurisdiction))}
                </span>
                {a.jurisdiction === "federal" && (
                  <span className="text-[11.5px] text-ink-3">
                    {COPY.acks.submission(a.submission_id_last4)}
                  </span>
                )}
              </span>
            </li>
          ) : (
            <li key={a.id} className="bg-red-tint px-[14px] py-[8px] text-[12.5px]">
              {COPY.acks.rejected(
                jurisdictionName(a.jurisdiction),
                a.reject_code ?? "",
                a.reject_text ?? "",
              )}
            </li>
          ),
        )}
      </ol>
      {rejected === undefined && (
        <p className="border-t border-hair px-[14px] py-[8px] text-[11.5px] text-ink-3">
          {COPY.delivered} · {COPY.estimates}
        </p>
      )}
      {rejected !== undefined && (
        <div className="flex flex-col gap-[8px] px-[14px] py-[10px]">
          {FIXTURE_BUILD && (
            <aside
              aria-label="Accrued Agent"
              data-agent-fix
              className="rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1"
            >
              <p className="text-[12.5px]">{COPY.fix.body}</p>
            </aside>
          )}
          <a
            href="/tax-returns/feld/issues?kind=engine_diagnostic"
            className="self-start rounded-[8px] bg-ink px-[12px] py-[6px] text-[12.5px] text-on-ink"
          >
            {COPY.fix.create}
          </a>
        </div>
      )}
    </div>
  );
}

function PacketEditor({
  packet,
  canApprove,
}: {
  packet: DeliveryPacketOut;
  canApprove: boolean;
}): JSX.Element {
  const [current, setCurrent] = useState(packet);
  const patch = useMutation({ ...patchPacketMutation(), onSuccess: setCurrent });
  const regenerate = useMutation({ ...regenerateLetterMutation(), onSuccess: setCurrent });
  const approve = useMutation({ ...approvePacketMutation(), onSuccess: setCurrent });
  const path = { path: { packet_id: current.id } };
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-[46px] items-center gap-[8px] px-[14px]">
        <h2 className="flex-1 text-[14.5px] font-medium">{COPY.editor.title}</h2>
        <Button
          variant="secondary"
          size="sm"
          icon="refresh-cw"
          disabled={current.status !== "draft"}
          onClick={() => {
            regenerate.mutate({ ...path, body: { seen_version: current.version } });
          }}
        >
          {COPY.editor.regenerate}
        </Button>
        {canApprove && (
          <Button
            variant="primary"
            size="sm"
            disabled={current.status !== "draft"}
            onClick={() => {
              approve.mutate({ ...path, body: { seen_version: current.version } });
            }}
          >
            {COPY.editor.approve}
          </Button>
        )}
      </header>
      <ul className="bg-shell p-[12px]">
        {current.items.map((item) => {
          const [name, meta] = COPY.packet.items[item.kind] ?? [item.kind, ""];
          const toggleable = item.kind.startsWith("voucher_");
          return (
            <li
              key={item.kind}
              className="flex min-h-[36px] items-center gap-[10px] bg-card px-[14px] py-[6px] [&+&]:border-t [&+&]:border-hair"
            >
              <Icon name="file-text" size={14} />
              <span className="flex-1 text-[13px]">{name}</span>
              {meta && <span className="text-[11.5px] text-ink-3">{meta}</span>}
              {toggleable && (
                <Toggle
                  label={COPY.editor.include(name)}
                  checked={item.included}
                  disabled={current.status !== "draft"}
                  onChange={(on) => {
                    patch.mutate({
                      ...path,
                      body: { included: { [item.kind]: on }, seen_version: current.version },
                    });
                  }}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Authorizations({
  envelope,
  delivery,
  returnId,
  defaultReminderOpen,
}: {
  envelope: EnvelopeOut;
  delivery: DeliveryOut | undefined;
  returnId: string;
  defaultReminderOpen: boolean;
}): JSX.Element {
  const [reminding, setReminding] = useState(defaultReminderOpen);
  const packetItems = COPY.packet.items;
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-[46px] items-center gap-[8px] px-[14px]">
        <h2 className="flex-1 text-[14.5px] font-medium">{COPY.canvas.title}</h2>
        <Button variant="secondary" size="sm">
          {COPY.canvas.openEnvelope}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon="bell"
          onClick={() => {
            setReminding(true);
          }}
        >
          {COPY.canvas.sendReminder}
        </Button>
      </header>
      <div className="grid flex-1 grid-cols-[612fr_388fr] gap-[12px] bg-shell p-[12px]">
        <div className="flex flex-col gap-[12px]">
          <section aria-label={envelope.row.title} className="rounded-[12px] bg-card shadow-e1">
            <header className="flex flex-col gap-[2px] px-[14px] py-[10px]">
              <span className="flex items-center gap-[8px]">
                <span className="flex-1 text-[13.5px] font-medium">{envelope.row.title}</span>
                {envelope.row.status === "completed" ? (
                  <Pill variant="green">{COPY.status.completed}</Pill>
                ) : (
                  <Pill variant="amber">{COPY.envelope.partly}</Pill>
                )}
              </span>
              <span className="text-[11.5px] text-ink-3">{COPY.envelope.sent}</span>
            </header>
            <ul className="border-t border-hair">
              {envelope.signers.map((s) => (
                <SignerRow key={s.id} signer={s} />
              ))}
            </ul>
            <p className="border-t border-hair px-[14px] py-[10px] text-[11.5px] text-ink-3">
              {COPY.envelope.evidence}
            </p>
          </section>
          <Card title={COPY.packet.title}>
            <ul>
              {Object.entries(packetItems).map(([kind, [name, meta]]) => (
                <li
                  key={kind}
                  className="flex min-h-[36px] items-center gap-[10px] border-t border-hair px-[14px] py-[6px]"
                >
                  <Icon name="file-text" size={14} />
                  <span
                    className={
                      kind === "engagement_invoice"
                        ? "flex-1 text-[13px] text-ink-3"
                        : "flex-1 text-[13px]"
                    }
                  >
                    {name}
                  </span>
                  {meta && <span className="text-[11.5px] text-ink-3">{meta}</span>}
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="flex flex-col gap-[12px]">
          <Card title={COPY.payments.title}>
            <dl>
              {COPY.payments.rows.map(([k, v]) => (
                <div key={k} className="flex gap-[12px] border-t border-hair px-[14px] py-[8px]">
                  <dt className="w-[150px] shrink-0 text-[12.5px] text-ink-2">{k}</dt>
                  <dd className="text-[12.5px]">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card title={COPY.gate.title}>
            <Gate envelope={envelope} delivery={delivery} returnId={returnId} />
          </Card>
          <Card title={COPY.acks.title}>
            <Acks acks={delivery?.acks ?? []} />
          </Card>
        </div>
      </div>
      <Reminder open={reminding} onOpenChange={setReminding} envelopeId={envelope.row.id} />
    </div>
  );
}

export interface Tax12Props {
  returnId: string;
  /** a2: the reminder sheet open. */
  defaultReminderOpen?: boolean;
}

export function TAX12({ returnId, defaultReminderOpen = false }: Tax12Props): JSX.Element {
  const path = { path: { return_id: returnId } };
  const approval = useQuery(finalApprovalOptions(path));
  const delivery = useQuery(deliveryOptions(path));
  const envelopeId = delivery.data?.envelope_id ?? null;
  const envelope = useQuery({
    ...getEnvelopeOptions({ path: { envelope_id: envelopeId ?? "" } }),
    enabled: envelopeId !== null,
  });
  const [step, setStep] = useState<Step>("authorizations");
  const approved = approval.data?.approved_at != null;
  return (
    <div className="flex h-full gap-[10px] p-[10px_12px_12px]" data-screen="TAX-12">
      <RecordRail
        title={COPY.rail.title}
        className="w-[330px] shrink-0"
        card={{
          icon: "send",
          title: COPY.rail.card,
          sub: COPY.rail.sub,
          state: !approved
            ? COPY.rail.inReview
            : (delivery.data?.acks ?? []).some((a) => a.status === "rejected")
              ? COPY.status.rejected
              : (delivery.data?.acks.length ?? 0) > 0
                ? COPY.status.accepted
                : COPY.rail.awaiting,
        }}
        sections={[
          {
            id: "checklist",
            title: COPY.rail.band,
            phases: phases(approval.data, envelope.data, delivery.data),
          },
        ]}
        selected={step}
        onOpen={(item) => {
          setStep(item.id as Step);
        }}
      />
      <main className="flex min-w-0 flex-1 flex-col rounded-[12px] bg-card shadow-e2">
        {!approved || envelope.data === undefined ? (
          approval.isPending || delivery.isPending ? (
            <div aria-busy className="flex-1" />
          ) : (
            <EmptyState title={COPY.canvas.blockedTitle} icon="lock">
              {COPY.canvas.blockedBody}
            </EmptyState>
          )
        ) : step === "packet" && delivery.data?.packet_id != null ? (
          <PacketEditor
            packet={{
              id: delivery.data.packet_id,
              return_id: returnId,
              version: 1,
              status: delivery.data.packet_status ?? "draft",
              items: delivery.data.items,
              letter_document_id: null,
              approved_by_name: null,
            }}
            canApprove={delivery.data.allowed_actions.includes("delivery_packet.approve")}
          />
        ) : (
          <Authorizations
            envelope={envelope.data}
            delivery={delivery.data}
            returnId={returnId}
            defaultReminderOpen={defaultReminderOpen}
          />
        )}
      </main>
    </div>
  );
}
