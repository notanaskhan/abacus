// RequestSheet (R-01 §5.2, L3; docs/screens/POR-04.md): one request in full, in the O3 sheet over
// the portal page that opened it, or the whole width at 390. One composition, three typed slots:
//
//   request   what we need, why, where to upload it, the shared thread, "doesn't apply" (R-01)
//   question  a firm question with context, one answer and an attachment (C-01 wires it)
//   decision  a firm decision with code-computed figures, three options (T-06 / T-09 wire it)
//
// Each variant has exactly one primary button. The firm's words (title, guidance, the thread) are
// shown as written, never model text (ADR P-25 off); the client never sees a firm status, the
// agent or a confidence. Send and Upload are the signed-in person's own (INV-1).

import type { CommentOut, PortalFileOut, PortalRequestOut } from "@abacus/api-client";
import {
  type Actor,
  Button,
  ConfirmDialog,
  HumanAction,
  Icon,
  RadioGroup,
  SheetModal,
  StatusDisc,
  UploadRow,
  bytes,
  cn,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, type ReactNode, useRef, useState } from "react";
import { DOCUMENT_WORDS, SHEET_WORDS } from "./messages";
import {
  type QuestionAnswer,
  type SheetDecision,
  type SheetQuestion,
  noteRecipient,
} from "./sheet";

/** The three Ignore reasons, as the kit and P-06's codes order them. */
const REASONS = ["Not applicable this year", "Already sent another way", "I don’t have this"];

export interface RequestSlot {
  variant: "request";
  request: PortalRequestOut;
  thread: readonly CommentOut[];
  /** A file in flight from this browser, 0–100 (POR-04 g). */
  uploading?: { name: string; sizeBytes: number; percent: number };
  /** "This doesn't apply to me…" pressed (POR-04 b). */
  ignoreOpen?: boolean;
  onUpload: (files: readonly File[]) => void;
  onIgnore: (reason: string, note: string) => void;
  onUndoIgnore: () => void;
  onWithdraw: (file: PortalFileOut) => void;
  onComment: (text: string) => void;
}

export interface QuestionSlot {
  variant: "question";
  question: SheetQuestion;
  onSend: (answer: QuestionAnswer) => void;
}

export interface DecisionSlot {
  variant: "decision";
  decision: SheetDecision;
  onSend: (option: string) => void;
}

export type SheetSlot = RequestSlot | QuestionSlot | DecisionSlot;

export interface RequestSheetProps {
  slot: SheetSlot;
  open: boolean;
  onClose: () => void;
  /** The signed-in person: Send is theirs (INV-1). */
  viewer: Actor;
  /** A server date ("2026-02-03") in the portal's words ("Feb 3"). */
  day: (iso: string) => string;
  /** The 390 layout: the sheet takes the whole width; "Take a photo" under the drop area. */
  mobile?: boolean;
  /** The file input's accepted types (the portal's upload policy). */
  accept: string;
  /** A specimen held open in place (the gallery): no layer, no scrim. */
  forceOpen?: boolean;
}

function Card({
  title,
  aside,
  children,
  label,
}: {
  title?: string;
  aside?: string;
  children: ReactNode;
  label?: string;
}): JSX.Element {
  return (
    <section
      aria-label={label ?? title}
      className="flex-none overflow-hidden rounded-nested bg-card shadow-e1"
    >
      {title !== undefined && (
        <div className="flex h-[33px] items-center gap-[8px] bg-band-hd px-[14px] hairline-b">
          <span className="text-section">{title}</span>
          {aside !== undefined && <span className="text-meta text-ink-3">{aside}</span>}
        </div>
      )}
      {children}
    </section>
  );
}

/** The status row under the title: what the client reads of the request now. */
function StatusLine({
  request,
  day,
}: {
  request: PortalRequestOut;
  day: (iso: string) => string;
}): JSX.Element {
  const first = (request.files ?? [])[0];
  if (request.client_status === "returned") {
    return (
      <span className="inline-flex h-[19px] items-center self-start rounded-pill bg-red-tint px-[8px] text-pill text-red-ink">
        {DOCUMENT_WORDS.returned.pill(request.returned?.reason ?? "other")}
      </span>
    );
  }
  if (request.client_status === "done" && first !== undefined) {
    const on = day(first.receipt.on);
    const words =
      first.receipt.kind === "emailed"
        ? DOCUMENT_WORDS.receipt.emailed(on)
        : DOCUMENT_WORDS.receipt.uploaded(on);
    return (
      <span className="flex items-center gap-[6px] text-dense font-medium text-green-ink">
        <StatusDisc state="done" size={15} />
        {`✓ ${words}`}
      </span>
    );
  }
  if (request.client_status === "ignored") return <></>;
  return (
    <span className="flex items-center gap-[6px] text-dense text-ink-2">
      <StatusDisc state="todo" size={15} />
      {SHEET_WORDS.toDo(day(request.requested_on))}
    </span>
  );
}

function FileRow({
  file,
  struck,
  onWithdraw,
}: {
  file: PortalFileOut;
  struck: boolean;
  onWithdraw: (() => void) | undefined;
}): JSX.Element {
  return (
    <div className="flex items-center gap-[10px] px-[14px] py-[8px] hairline-t">
      <Icon name="file" size={15} className="flex-none text-ink-3" />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span
          className={cn("truncate text-body font-medium", struck && "text-ink-3 line-through")}
        >
          {file.name}
        </span>
        {file.size_bytes != null && (
          <span className="text-meta text-ink-3">{bytes(file.size_bytes)}</span>
        )}
      </span>
      {onWithdraw !== undefined && (
        <Button variant="ghost" size="sm" onClick={onWithdraw}>
          {SHEET_WORDS.withdraw}
        </Button>
      )}
    </div>
  );
}

function RequestBody({
  slot,
  day,
  mobile,
  firm,
  choose,
}: {
  slot: RequestSlot;
  day: (iso: string) => string;
  mobile: boolean;
  firm: string;
  choose: () => void;
}): JSX.Element {
  const { request, thread } = slot;
  const allowed = new Set(request.allowed_actions ?? []);
  const [ignoring, setIgnoring] = useState(slot.ignoreOpen === true);
  const [reason, setReason] = useState<string | undefined>(undefined);
  const [note, setNote] = useState("");
  const [comment, setComment] = useState("");
  const [withdrawing, setWithdrawing] = useState<PortalFileOut | null>(null);
  const files = request.files ?? [];
  const returned = request.returned;
  const person = noteRecipient(thread) ?? firm;
  const preChecks = request.pre_checks ?? [];
  const send = (): void => {
    const text = comment.trim();
    if (text === "") return;
    slot.onComment(text);
    setComment("");
  };
  return (
    <>
      <Card label={request.title}>
        <div className="flex flex-col gap-[8px] p-[14px]">
          <span className="flex items-center gap-[6px] text-meta text-ink-3">
            <Icon name="heart" size={12} />
            {request.category.label}
          </span>
          <h2 className="text-title leading-[1.3] font-medium">{request.title}</h2>
          <StatusLine request={request} day={day} />
          {returned != null && (
            <blockquote className="rounded-nested bg-nested px-[12px] py-[10px] text-dense leading-[1.5] text-ink-2">
              {SHEET_WORDS.returnedNote(returned.note, returned.by_name, day(returned.on))}
            </blockquote>
          )}
          {request.client_status === "ignored" && (
            <span className="flex items-center gap-[8px] text-dense text-ink-3">
              {SHEET_WORDS.ignoredLine}
              {allowed.has("undo_ignore") && (
                <button
                  type="button"
                  className="font-medium text-espresso hover:underline"
                  onClick={slot.onUndoIgnore}
                >
                  {SHEET_WORDS.undo}
                </button>
              )}
            </span>
          )}
        </div>
        {files.map((f, n) => {
          const mine = f.withdrawable && allowed.has("withdraw");
          return (
            <FileRow
              key={f.id}
              file={f}
              struck={f.struck === true || (n === 0 && returned != null)}
              onWithdraw={
                mine
                  ? () => {
                      setWithdrawing(f);
                    }
                  : undefined
              }
            />
          );
        })}
        {request.client_status === "done" && files.length > 0 && (
          <p className="px-[14px] pt-[4px] pb-[12px] text-dense text-ink-3">
            {SHEET_WORDS.checkNext(firm)}
          </p>
        )}
        {request.guidance != null && request.guidance !== "" && (
          <>
            <div className="flex h-[30px] items-center bg-band-hd px-[14px] text-dense font-medium text-ink-2 hairline-t">
              {SHEET_WORDS.why}
            </div>
            <p className="px-[14px] py-[10px] text-dense leading-[1.55] text-ink-2">
              {request.guidance}
            </p>
          </>
        )}
      </Card>
      {allowed.has("upload") && (
        <Card label={SHEET_WORDS.dropTitle}>
          <div className="flex flex-col gap-[8px] p-[12px]">
            <button
              type="button"
              aria-label={`${SHEET_WORDS.dropTitle}. ${SHEET_WORDS.dropTypes}`}
              onClick={choose}
              className="flex h-[112px] flex-col items-center justify-center gap-[6px] rounded-nested bg-nested inset-ring-1 inset-ring-hair hover:inset-ring-stroke"
            >
              <span className="inline-flex size-[40px] items-center justify-center rounded-pill bg-card text-ink-2 shadow-e1">
                <Icon name="file" size={18} />
              </span>
              <span className="text-section">{SHEET_WORDS.dropTitle}</span>
              <span className="text-meta text-ink-2">{SHEET_WORDS.dropTypes}</span>
            </button>
            {mobile && (
              <Button variant="secondary" size="xl" onClick={choose}>
                {SHEET_WORDS.photo}
              </Button>
            )}
            {slot.uploading !== undefined && (
              <UploadRow
                upload={{
                  name: slot.uploading.name,
                  size: bytes(slot.uploading.sizeBytes),
                  p: slot.uploading.percent / 100,
                }}
              />
            )}
            {preChecks.length > 0 && (
              <ul aria-label="Pre-checks" className="flex flex-col gap-[4px]">
                {preChecks.map((code) => (
                  <li key={code} className="flex items-start gap-[6px] text-dense text-ink-2">
                    <Icon name="circle-alert" size={13} className="mt-px flex-none text-ink-3" />
                    {SHEET_WORDS.preCheck[code]}
                  </li>
                ))}
              </ul>
            )}
            {request.prior_year != null && (
              <p className="text-meta text-ink-3">
                {SHEET_WORDS.lastYear(
                  request.prior_year.file_name,
                  day(request.prior_year.sent_on),
                )}
              </p>
            )}
          </div>
        </Card>
      )}
      <Card title={SHEET_WORDS.comments} aside={SHEET_WORDS.visibility(firm)}>
        <ul className="flex flex-col">
          {thread.map((c) => (
            <li key={c.id} className="flex flex-col gap-[3px] px-[14px] py-[10px] hairline-b">
              <span className="flex items-center gap-[6px]">
                <Icon name="circle-user-round" size={14} className="text-ink-3" />
                <span className="text-dense font-medium">
                  {c.author_side === "firm" ? `${c.author_name} · ${firm}` : c.author_name}
                </span>
                <span className="text-meta text-ink-3">{day(c.created_at.slice(0, 10))}</span>
              </span>
              <span className="text-dense leading-[1.5]">{c.text ?? ""}</span>
            </li>
          ))}
        </ul>
        {allowed.has("comment") && (
          <div className="p-[10px]">
            <div className="flex h-[44px] items-center gap-[8px] rounded-[12px] bg-nested px-[12px] inset-ring-[0.5px] inset-ring-hair">
              <Icon name="paperclip" size={14} className="text-ink-3" />
              <input
                aria-label={SHEET_WORDS.composer}
                placeholder={SHEET_WORDS.composer}
                value={comment}
                onChange={(event) => {
                  setComment(event.target.value);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    send();
                  }
                }}
                className="min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-ink-3"
              />
              <button
                type="button"
                aria-label={SHEET_WORDS.send}
                disabled={comment.trim() === ""}
                onClick={send}
                className="inline-flex size-[32px] flex-none items-center justify-center rounded-pill bg-card shadow-e1 disabled:text-ink-4"
              >
                <Icon name="arrow-right" size={14} />
              </button>
            </div>
          </div>
        )}
      </Card>
      {allowed.has("ignore") && !ignoring && (
        <Button
          variant="secondary"
          size="xl"
          onClick={() => {
            setIgnoring(true);
          }}
        >
          {SHEET_WORDS.notApplicable}
        </Button>
      )}
      {allowed.has("ignore") && ignoring && (
        <Card label={SHEET_WORDS.ignoreTitle}>
          <fieldset className="flex flex-col gap-[10px] p-[14px]">
            <legend className="mb-[8px] text-section">{SHEET_WORDS.ignoreTitle}</legend>
            <RadioGroup
              label={SHEET_WORDS.ignoreTitle}
              options={REASONS.map((r) => ({ value: r, label: r }))}
              {...(reason === undefined ? {} : { value: reason })}
              onChange={setReason}
            />
            <label className="flex flex-col gap-[4px] text-meta text-ink-3">
              {SHEET_WORDS.ignoreNote(person)}
              <textarea
                rows={3}
                value={note}
                onChange={(event) => {
                  setNote(event.target.value);
                }}
                className="h-[64px] resize-none rounded-nested bg-nested px-[10px] py-[8px] text-body text-ink outline-none inset-ring-[0.5px] inset-ring-hair"
              />
            </label>
            <Button
              variant="secondary"
              size="lg"
              disabled={reason === undefined}
              onClick={() => {
                if (reason !== undefined) slot.onIgnore(reason, note);
                setIgnoring(false);
              }}
            >
              {SHEET_WORDS.ignoreSave}
            </Button>
          </fieldset>
        </Card>
      )}
      <ConfirmDialog
        open={withdrawing !== null}
        onOpenChange={(open) => {
          if (!open) setWithdrawing(null);
        }}
        title={SHEET_WORDS.withdraw}
        confirmLabel={SHEET_WORDS.withdraw}
        cancelLabel={SHEET_WORDS.cancel}
        onConfirm={() => {
          if (withdrawing !== null) slot.onWithdraw(withdrawing);
          setWithdrawing(null);
        }}
      >
        {SHEET_WORDS.withdrawConfirm(firm)}
      </ConfirmDialog>
    </>
  );
}

function QuestionBody({ slot, viewer }: { slot: QuestionSlot; viewer: Actor }): JSX.Element {
  const { question } = slot;
  const [option, setOption] = useState(question.selected);
  const [text, setText] = useState(question.text);
  return (
    <>
      <Card label={question.title}>
        <div className="flex flex-col gap-[8px] p-[14px]">
          <h2 className="text-title leading-[1.3] font-medium">{question.title}</h2>
        </div>
        <dl className="flex flex-col">
          {question.context.map((kv) => (
            <div
              key={kv.label}
              className="flex min-h-[34px] items-center justify-between gap-[12px] px-[14px] text-dense hairline-t"
            >
              <dt className="text-ink-2">{kv.label}</dt>
              <dd className="text-right font-medium">{kv.value}</dd>
            </div>
          ))}
        </dl>
        <p className="px-[14px] py-[10px] text-dense leading-[1.5] text-ink-2 hairline-t">
          {question.note}
        </p>
      </Card>
      <Card label={SHEET_WORDS.question.answerLabel}>
        <div className="flex flex-col gap-[10px] p-[14px]">
          <RadioGroup
            label={SHEET_WORDS.question.answerLabel}
            options={question.options.map((o) => ({ value: o.code, label: o.label }))}
            value={option}
            onChange={setOption}
          />
          <label className="flex flex-col gap-[4px] text-meta text-ink-3">
            {SHEET_WORDS.question.textLabel}
            <textarea
              rows={4}
              value={text}
              onChange={(event) => {
                setText(event.target.value);
              }}
              className="resize-none rounded-nested bg-nested px-[10px] py-[8px] text-body leading-[1.5] text-ink outline-none inset-ring-[0.5px] inset-ring-hair"
            />
          </label>
          {question.attachments.map((a) => (
            <span key={a.name} className="flex items-center gap-[8px] text-dense">
              <Icon name="paperclip" size={14} className="text-ink-3" />
              <span className="min-w-0 flex-1 truncate">{`${a.name} · ${bytes(a.sizeBytes)}`}</span>
              {a.done && <StatusDisc state="done" size={13} />}
            </span>
          ))}
          {question.answered === undefined ? (
            <HumanAction
              verb="Send"
              object="answer"
              actor={viewer}
              variant="primary"
              size="xl"
              onClick={() => {
                slot.onSend({ option, text });
              }}
            />
          ) : (
            <span className="flex items-center gap-[6px] text-dense font-medium text-green-ink">
              <StatusDisc state="done" size={13} />
              {`✓ ${SHEET_WORDS.question.answered(question.answered.at, question.answered.followUpBy)}`}
            </span>
          )}
        </div>
      </Card>
    </>
  );
}

function DecisionBody({ slot, viewer }: { slot: DecisionSlot; viewer: Actor }): JSX.Element {
  const { decision } = slot;
  const [option, setOption] = useState<string | undefined>(undefined);
  return (
    <>
      <Card label={decision.title}>
        <div className="flex flex-col gap-[8px] p-[14px]">
          <h2 className="text-title leading-[1.3] font-medium">{decision.title}</h2>
          <span className="inline-flex h-[19px] items-center self-start rounded-pill bg-amber-tint px-[8px] text-pill text-amber-ink">
            {decision.dueLabel}
          </span>
          <p className="text-dense leading-[1.55] text-ink-2">{decision.explanation}</p>
        </div>
      </Card>
      <Card label={SHEET_WORDS.decision.choiceLabel}>
        <div className="flex flex-col gap-[10px] p-[14px]">
          <RadioGroup
            label={SHEET_WORDS.decision.choiceLabel}
            options={decision.options.map((o) => ({ value: o.code, label: o.label }))}
            {...(option === undefined ? {} : { value: option })}
            onChange={setOption}
          />
          <HumanAction
            verb="Send"
            object="decision"
            actor={viewer}
            variant="primary"
            size="xl"
            disabled={option === undefined}
            onClick={() => {
              if (option !== undefined) slot.onSend(option);
            }}
          />
          <p className="text-meta text-ink-3">{decision.footnote}</p>
        </div>
      </Card>
    </>
  );
}

/** The sheet: the O3 frame (or the whole width at 390) around the slot's body. */
export function RequestSheet({
  slot,
  open,
  onClose,
  viewer,
  day,
  mobile = false,
  accept,
  forceOpen = false,
}: RequestSheetProps): JSX.Element {
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const input = useRef<HTMLInputElement>(null);
  const choose = (): void => {
    input.current?.click();
  };
  const request = slot.variant === "request" ? slot : null;
  const canUpload = request !== null && (request.request.allowed_actions ?? []).includes("upload");
  const title = SHEET_WORDS.header[slot.variant];
  const label =
    slot.variant === "request"
      ? slot.request.title
      : slot.variant === "question"
        ? slot.question.title
        : slot.decision.title;
  const body =
    slot.variant === "request" ? (
      <RequestBody slot={slot} day={day} mobile={mobile} firm={firm} choose={choose} />
    ) : slot.variant === "question" ? (
      <QuestionBody slot={slot} viewer={viewer} />
    ) : (
      <DecisionBody slot={slot} viewer={viewer} />
    );
  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={title}
      description={label}
      fullScreen={mobile}
      {...(forceOpen ? { forceState: "open" as const } : {})}
      {...(canUpload
        ? {
            action: mobile ? (
              <Button variant="link" size="md" onClick={choose}>
                {SHEET_WORDS.upload}
              </Button>
            ) : (
              <Button variant="primary" size="md" onClick={choose}>
                {SHEET_WORDS.upload}
              </Button>
            ),
          }
        : {})}
    >
      <div data-sheet={slot.variant} className="contents">
        {request !== null && (
          <input
            ref={input}
            type="file"
            hidden
            multiple
            accept={accept}
            {...(mobile ? { capture: "environment" as const } : {})}
            onChange={(event) => {
              const files = [...(event.target.files ?? [])];
              if (files.length > 0) request.onUpload(files);
              event.target.value = "";
            }}
          />
        )}
        {body}
      </div>
    </SheetModal>
  );
}
