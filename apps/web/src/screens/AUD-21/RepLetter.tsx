import type { RepresentationLetterOut } from "@abacus/api-client";
import { Button, Icon, Segmented, Skeleton, StatusPill, Toggle } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY, GENERAL, PAPER, PLAN_PARAGRAPHS, SPECIFIC } from "./copy";

// AUD-21 · Representation letter builder in fixture mode on T10 (A-07-T28; handoff AUD-21): the
// structure pane (general representations locked, specific ones toggled with their reason chips,
// the SUM attachment, signer and dating) beside the paper on the well with its DRAFT watermark.
// Toggling a specific representation adds or removes its numbered paragraph, the numbers reflowing
// over 220 ms. The primary action follows the status: request approval, send for signature (SIG-02
// prefilled through `onSend`), remind, or start the re-date. Sending, reminding and re-dating are a
// person's actions; nothing here is agent-owned (frontend rule 3).

type Status = RepresentationLetterOut["status"];

export interface RepLetterProps {
  letter: RepresentationLetterOut;
  onBack?: () => void;
  onSend?: () => void;
  onRemind?: () => void;
  onRedate?: () => void;
  onRequestApproval?: () => void;
  onReason?: (reason: string) => void;
}

function StatusBand({ status }: { status: Status }): JSX.Element {
  const pill: Record<string, [string, "neutral" | "warning" | "success" | "danger"]> = {
    draft: ["Draft", "neutral"],
    drafting: ["Draft", "neutral"],
    awaiting_partner_approval: ["Draft", "neutral"],
    approved: ["Draft", "neutral"],
    sent: ["Sent · Oct 6", "warning"],
    signed: ["Signed", "success"],
    date_mismatch: ["Dated October 8, 2026 ≠ report date October 9", "danger"],
  };
  const [label, tone] = pill[status] ?? ["Draft", "neutral"];
  const note: Record<string, string> = {
    approved: "Approved by Margaret Okonkwo · Oct 5, 5:10 PM",
    awaiting_partner_approval: "Waiting on Margaret Okonkwo",
    sent: "Viewed Oct 6, 11:02 AM",
    signed: "Dana Kowalski · Oct 9, 2026 · 9:12 AM",
  };
  return (
    <div
      data-status-band={status}
      className="flex h-[33px] items-center gap-2 px-[12px] text-dense"
    >
      <span className="text-ink-3">Status</span>
      <StatusPill tone={tone}>{label}</StatusPill>
      {note[status] !== undefined && (
        <span
          className={
            status === "awaiting_partner_approval"
              ? "text-[11.5px] text-amber-ink"
              : "text-[11.5px] text-green-ink"
          }
        >
          {note[status]}
        </span>
      )}
      {status === "signed" && (
        <span className="rounded-pill bg-green-tint px-[6px] text-[11.5px] text-green-ink">
          Dated October 9, 2026 = report date ✓ · G7
        </span>
      )}
    </div>
  );
}

function Primary({
  status,
  props,
}: {
  status: Status;
  props: RepLetterProps;
}): JSX.Element | null {
  if (status === "awaiting_partner_approval" || status === "draft") {
    return (
      <Button size="sm" onClick={props.onRequestApproval}>
        {COPY.requestApproval}
      </Button>
    );
  }
  if (status === "approved") {
    return (
      <Button size="sm" onClick={props.onSend}>
        <Icon name="signature" size={14} />
        {COPY.send}
      </Button>
    );
  }
  if (status === "sent") {
    return (
      <Button size="sm" onClick={props.onRemind}>
        {COPY.remind}
      </Button>
    );
  }
  if (status === "date_mismatch") {
    return (
      <Button size="sm" onClick={props.onRedate}>
        {COPY.redate}
      </Button>
    );
  }
  return null;
}

/** AUD-21: the letter's structure and paper. */
export function RepLetter(props: RepLetterProps): JSX.Element {
  const { letter } = props;
  const [tab, setTab] = useState<string>("Letter");
  const [on, setOn] = useState<Record<string, boolean>>(
    Object.fromEntries(SPECIFIC.map((s) => [s.key, s.on])),
  );
  const locked = ["sent", "signed", "date_mismatch"].includes(letter.status);
  const plan = PLAN_PARAGRAPHS.filter((p) => on[p.key] === true);
  const draft = letter.watermark === "draft";
  return (
    <div data-screen="AUD-21" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
        <div className="flex flex-1 justify-center">
          <Segmented
            size="small"
            label="Letter views"
            options={COPY.tabs}
            active={tab}
            onChange={setTab}
          />
        </div>
      </div>
      {tab === "Letter" && (
        <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
          <section
            aria-label="Structure"
            className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
          >
            <h2 className="flex h-[32px] items-center px-[12px] text-[12.5px] font-medium text-ink-2">
              {COPY.sheet}
            </h2>
            <StatusBand status={letter.status} />
            <h3 className="flex h-[31px] items-center gap-2 bg-band-hd px-[12px] text-dense font-medium">
              {COPY.general}
              <Icon name="lock" size={12} />
              <span className="text-[11.5px] font-normal text-ink-3">{COPY.always}</span>
            </h3>
            <ul>
              {GENERAL.map((label) => (
                <li
                  key={label}
                  className="flex h-[34px] items-center gap-2 px-[12px] text-[12.5px]"
                >
                  <Toggle checked disabled label={label} />
                  <span>{label}</span>
                </li>
              ))}
            </ul>
            <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
              {COPY.specific}
            </h3>
            <ul>
              {SPECIFIC.map((s) => (
                <li
                  key={s.key}
                  data-specific={s.key}
                  className="flex min-h-[34px] items-center gap-2 px-[12px] text-[12.5px]"
                >
                  <Toggle
                    checked={on[s.key] === true}
                    disabled={locked}
                    label={s.label}
                    onChange={(next: boolean) => {
                      setOn({ ...on, [s.key]: next });
                    }}
                  />
                  <span className="flex-1">{s.label}</span>
                  <button
                    type="button"
                    className="text-[11.5px] text-ink-3 underline-offset-2 hover:underline"
                    onClick={() => props.onReason?.(s.reason)}
                  >
                    {s.reason}
                  </button>
                </li>
              ))}
            </ul>
            <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
              {COPY.attachments}
            </h3>
            <p className="flex h-[34px] items-center gap-2 px-[12px] text-[12.5px]">
              Summary of uncorrected misstatements
              <StatusPill tone="success">Attached</StatusPill>
              <span className="text-[11.5px] text-ink-3">
                2 items · 34,150 rollover / 22,250 iron curtain
              </span>
            </p>
            <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-dense font-medium">
              {COPY.signerDating}
            </h3>
            <dl className="grid grid-cols-[120px_1fr] gap-y-1 px-[12px] py-[6px] text-[12.5px]">
              <dt className="text-ink-3">Signer</dt>
              <dd>Dana Kowalski · HR Director and Plan Administrator</dd>
              <dt className="text-ink-3">Identity</dt>
              <dd>Email code + knowledge-based verification</dd>
              <dt className="text-ink-3">Date the letter</dt>
              <dd>As of the report date → October 9, 2026</dd>
            </dl>
            <p className="px-[12px] pb-[12px] text-[11.5px] text-ink-3">{COPY.helper}</p>
          </section>
          <section
            aria-label="Paper"
            className="flex min-w-0 flex-1 flex-col rounded-pane bg-shell"
          >
            <header className="relative flex h-[46px] items-center justify-center">
              <h2 className="text-[14.5px] font-medium">{COPY.paperTitle}</h2>
              <div className="absolute right-[10px] flex gap-2">
                {!locked && (
                  <Button size="sm" variant="secondary">
                    {COPY.edit}
                  </Button>
                )}
                <Button size="sm" variant="ghost">
                  {COPY.preview}
                </Button>
                <Primary status={letter.status} props={props} />
              </div>
            </header>
            <div
              // A scrolling region is reachable by keyboard (axe scrollable-region-focusable).
              tabIndex={0}
              role="region"
              aria-label="Paper"
              className="min-h-0 flex-1 overflow-y-auto p-[14px]"
            >
              {letter.status === "drafting" ? (
                <div
                  data-drafting="true"
                  className="mx-auto w-[600px] rounded-pane bg-card p-[24px] shadow-e2"
                >
                  <p className="pb-[10px] text-[12px] text-ink-3">{COPY.drafting}</p>
                  {[0, 1, 2, 3].map((n) => (
                    <Skeleton key={n} className="mb-[8px] h-[12px] w-full" />
                  ))}
                </div>
              ) : (
                <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[24px] pb-[24px] pt-[20px] text-[12px] leading-[1.55] shadow-e2">
                  {draft && (
                    <span
                      aria-hidden="true"
                      data-watermark="draft"
                      className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06]"
                    >
                      {COPY.watermark}
                    </span>
                  )}
                  <p className="text-[13.5px] font-medium">{PAPER.letterhead}</p>
                  <p className="text-[11.5px] text-ink-3">{PAPER.care}</p>
                  <hr className="my-[8px] border-hair" />
                  <p>{PAPER.date}</p>
                  <p className="pb-[8px]">{PAPER.addressee}</p>
                  <p>{PAPER.intro}</p>
                  <h4 className="pt-[10px] text-[13.5px] font-medium">Financial statements</h4>
                  <ol className="list-decimal pl-[18px]">
                    {PAPER.financial.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ol>
                  <p className="text-[12.5px] text-ink-3">{PAPER.more}</p>
                  <h4 className="pt-[10px] text-[13.5px] font-medium">Plan-specific matters</h4>
                  <ol start={12} className="list-decimal pl-[18px]">
                    {plan.map((p) => (
                      <li
                        key={p.key}
                        data-plan-paragraph={p.key}
                        className="transition-all duration-[220ms] motion-reduce:transition-none"
                      >
                        {p.text}
                      </li>
                    ))}
                  </ol>
                  <div className="pt-[18px]">
                    <hr className="w-[200px] border-ink-4" />
                    <p className="text-[12px] font-medium">{PAPER.signer}</p>
                    <p className="text-[11.5px] text-ink-3">{PAPER.title}</p>
                    <p>Date: {PAPER.date}</p>
                  </div>
                  <p className="mt-[14px] rounded-tile bg-nested px-[10px] py-[6px] text-[11.5px]">
                    {PAPER.attachment}
                  </p>
                </article>
              )}
            </div>
          </section>
        </div>
      )}
      {tab === "Signers" && (
        <section aria-label="Signers" className="p-[12px] text-dense">
          <p>
            Dana Kowalski · order 1 · {letter.envelope_id === null ? "not sent" : "envelope sent"}
          </p>
        </section>
      )}
      {tab === "History" && (
        <section aria-label="History" className="p-[12px] text-dense">
          <ul>
            <li>v1 · agent draft · Oct 2</li>
            <li>v2 · HL edits · Oct 5</li>
            <li>v3 · MO approved · Oct 5</li>
          </ul>
        </section>
      )}
    </div>
  );
}
