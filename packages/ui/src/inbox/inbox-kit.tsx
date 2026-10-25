import { Check, X } from "lucide-react";
import type { JSX, ReactNode } from "react";
import { AgentText } from "../agent-text";
import { cn } from "../cn";
import { Button, IconButton } from "../components/button";
import { type MenuItem, Menu } from "../components/popover";
import { Icon } from "../icons";

// C-15 / C-18 File kit, inbox visuals (F-05-T56; File Kit `Mail`, `InboxList`, `Attachments`): the
// rows of the firm inbox rail and the reading pane's message. Rows are min 52, padding 9 10, gap 11,
// radius 8, separated by a hairline inset (never borders), with a leading 16px status slot in one
// of four states, exactly:
//
//   new       16px ring, 1.5px ink-4                       "Not filed"
//   wait      16px solid amber dot                          "Waiting to be filed"
//   filed     15px olive disc with a white check            "Filed"
//   ignored   15px ink-4 disc with a white x; the row's text goes ink-3 at 400   "Ignored"
//
// No avatars, no coloured initials, no bold for unread: the subject is 13.5/500 on every row. The
// client chip in the reading pane names the matched client, or reads "Match client…" in amber ink
// when the sender matches none. The agent's filing note is attributed and offers only Review; it
// never carries File, Ignore or Send (INV-1).

export type InboxState = "new" | "wait" | "filed" | "ignored";

export const INBOX_STATE_WORD: Readonly<Record<InboxState, string>> = {
  new: "Not filed",
  wait: "Waiting to be filed",
  filed: "Filed",
  ignored: "Ignored",
};

/** The leading status slot, one of the four states exactly. */
export function InboxDot({
  state,
  className,
}: {
  state: InboxState;
  className?: string;
}): JSX.Element {
  const label = INBOX_STATE_WORD[state];
  const base = "inline-flex flex-none items-center justify-center rounded-pill";
  switch (state) {
    case "new":
      return (
        <span
          role="img"
          aria-label={label}
          data-dot="new"
          className={cn(base, "size-[16px] inset-ring-[1.5px] inset-ring-ink-4", className)}
        />
      );
    case "wait":
      return (
        <span
          role="img"
          aria-label={label}
          data-dot="wait"
          className={cn(base, "size-[16px] bg-amber", className)}
        />
      );
    case "filed":
      return (
        <span
          role="img"
          aria-label={label}
          data-dot="filed"
          className={cn(base, "size-[15px] bg-green text-on-dark", className)}
        >
          <Check aria-hidden="true" size={10} strokeWidth={2.2} />
        </span>
      );
    case "ignored":
      return (
        <span
          role="img"
          aria-label={label}
          data-dot="ignored"
          className={cn(base, "size-[15px] bg-ink-4 text-on-dark", className)}
        >
          <X aria-hidden="true" size={10} strokeWidth={2.2} />
        </span>
      );
  }
}

// ---- The rail -------------------------------------------------------------------------------------

export interface InboxMessage {
  id: string;
  subject: string;
  /** The sender line: "Claire Feld", "Ben Ashby · Copperleaf". */
  from: string;
  /** "9:12 AM", "Yesterday", "Sep 11". */
  time: string;
  state: InboxState;
  /** The row's second line after the sender: the message's opening words. */
  preview: string;
  /** Where a filed message went: "Northwind 401(k) PY2025 › Investments › Trust statements". */
  filedTo?: string;
  /** Thread replies, newest first. */
  replies?: readonly InboxMessage[];
}

export interface InboxRowProps {
  message: InboxMessage;
  selected?: boolean;
  onSelect?: (message: InboxMessage) => void;
  /** A thread parent: its chevron, open or shut. */
  thread?: { open: boolean; onToggle: () => void };
  /** A thread child: indented 34. */
  child?: boolean;
}

/** One rail row (C-18 InboxRow). */
export function InboxRow({
  message,
  selected = false,
  onSelect,
  thread,
  child = false,
}: InboxRowProps): JSX.Element {
  const ignored = message.state === "ignored";
  const second =
    message.state === "filed" && message.filedTo !== undefined ? (
      <>
        Filed to <span className="text-ink">{message.filedTo}</span>
      </>
    ) : (
      `${message.from} · ${message.preview}`
    );
  return (
    <li className="flex hairline-b last:shadow-none">
      <button
        type="button"
        data-inbox-row={message.id}
        data-state={message.state}
        {...(selected ? { "aria-current": "true" as const } : {})}
        {...(thread === undefined ? {} : { "aria-expanded": thread.open })}
        onClick={() => {
          onSelect?.(message);
          thread?.onToggle();
        }}
        className={cn(
          "flex min-h-[52px] w-full items-start gap-[11px] rounded-tile py-[9px] pr-[10px] text-left",
          "hover:bg-nested focus-visible:outline-offset-[-2px]",
          child ? "pl-[34px]" : "pl-[10px]",
          selected && "bg-sel-bg hover:bg-sel-bg",
          ignored && "text-ink-3",
        )}
      >
        <InboxDot state={message.state} className="mt-[2px]" />
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="flex items-baseline gap-[8px]">
            <span
              className={cn(
                "min-w-0 flex-1 truncate text-section",
                ignored ? "font-normal text-ink-3" : "font-medium text-ink",
              )}
            >
              {message.subject}
            </span>
            <span className="flex-none text-cell text-ink-3">{message.time}</span>
            {thread !== undefined && (
              <Icon
                name={thread.open ? "chevron-down" : "chevron-right"}
                size={12}
                className="flex-none text-ink-3"
              />
            )}
          </span>
          <span className="truncate text-cell text-ink-3">{second}</span>
        </span>
      </button>
    </li>
  );
}

export interface InboxListProps {
  messages: readonly InboxMessage[];
  selected?: string | null;
  onSelect?: (message: InboxMessage) => void;
  /** Threads shown open. */
  open?: readonly string[];
  onToggle?: (id: string) => void;
  /** What shows when the filters leave nothing. */
  empty?: ReactNode;
}

/** The rail's list (C-18 InboxList): rows, their thread children, padding 0 8 8. */
export function InboxList({
  messages,
  selected,
  onSelect,
  open = [],
  onToggle,
  empty,
}: InboxListProps): JSX.Element {
  if (messages.length === 0) return <>{empty}</>;
  return (
    <ul aria-label="Messages" data-inbox-list="" className="flex flex-col px-[8px] pb-[8px]">
      {messages.flatMap((m) => {
        const kids = m.replies ?? [];
        const isOpen = open.includes(m.id);
        return [
          <InboxRow
            key={m.id}
            message={m}
            selected={selected === m.id}
            {...(onSelect === undefined ? {} : { onSelect })}
            {...(kids.length > 0
              ? { thread: { open: isOpen, onToggle: () => onToggle?.(m.id) } }
              : {})}
          />,
          ...(isOpen
            ? kids.map((k) => (
                <InboxRow
                  key={k.id}
                  message={k}
                  child
                  selected={selected === k.id}
                  {...(onSelect === undefined ? {} : { onSelect })}
                />
              ))
            : []),
        ];
      })}
    </ul>
  );
}

// ---- The reading pane ------------------------------------------------------------------------------

/** The reading pane's client chip: the matched client, or "Match client…" in amber ink. */
export function ClientMatchChip({
  client,
  clients,
  onMatch,
}: {
  client: string | null;
  clients: readonly string[];
  onMatch?: (client: string) => void;
}): JSX.Element {
  return (
    <Menu
      label="Client"
      align="start"
      width={260}
      trigger={
        <button
          type="button"
          data-client-chip={client === null ? "unmatched" : "matched"}
          className={cn(
            "inline-flex h-[29px] items-center gap-[7px] rounded-pill bg-card pr-[10px] pl-[10px] text-body shadow-e1 hover:bg-nav-fill",
            client === null ? "text-amber-ink" : "text-ink",
          )}
        >
          <Icon name="circle-user-round" size={14} />
          {client ?? "Match client…"}
          <Icon name="chevron-down" size={12} className="text-ink-3" />
        </button>
      }
      sections={[
        clients.map((c) => ({ label: c, checked: c === client, onSelect: () => onMatch?.(c) })),
      ]}
    />
  );
}

export interface InboxAttachment {
  name: string;
  /** "1.2 MB PDF". */
  meta: string;
  /** The server's page render: a same-origin URL (in fixtures, a PNG data URL). */
  src: string;
  state?: Extract<InboxState, "wait" | "filed">;
}

/** An attachment (C-18 AttachmentThumb): a 126 × 150 page render, its state disc over the top
 * right corner, then the name and the size. */
export function AttachmentThumb({ attachment }: { attachment: InboxAttachment }): JSX.Element {
  return (
    <li data-attachment={attachment.name} className="flex w-[126px] flex-col gap-[6px]">
      <span className="relative block h-[150px] w-[126px]">
        <img
          src={attachment.src}
          alt=""
          className="size-full rounded-sheet bg-card object-cover object-top shadow-e1 ring-[0.5px] ring-stroke"
        />
        {attachment.state !== undefined && (
          <InboxDot
            state={attachment.state}
            className={cn(
              "absolute -top-[5px] -right-[5px]",
              attachment.state === "wait" && "size-[10px]",
            )}
          />
        )}
      </span>
      <span className="line-clamp-2 text-dense font-medium">{attachment.name}</span>
      <span className="text-meta text-ink-3">{attachment.meta}</span>
    </li>
  );
}

export interface MessageViewProps {
  subject: string;
  /** "Sep 14, 2026, 9:12 AM". */
  date: string;
  /** "From Claire Feld <claire.feld@…>". */
  address: string;
  body: string;
  signature?: string;
  attachments?: readonly InboxAttachment[];
  onDownloadAll?: () => void;
  /** An older message in the thread: recessed on the nested fill under a hairline. */
  recessed?: boolean;
}

/** One message in the reading pane (C-18 MessageView): subject, date and address lines, the body
 * at 13.5/1.6 to 640 wide, the signature, and the attachments. Client words are plain text. */
export function MessageView({
  subject,
  date,
  address,
  body,
  signature,
  attachments = [],
  onDownloadAll,
  recessed = false,
}: MessageViewProps): JSX.Element {
  return (
    <article
      data-message=""
      aria-label={subject}
      className={cn(
        "flex flex-col px-[18px] pt-[16px] pb-[20px]",
        recessed && "bg-nested hairline-t",
      )}
    >
      <h3 className="text-tab font-medium">{subject}</h3>
      <p className="mt-[6px] text-dense leading-[1.5] text-ink-3">{date}</p>
      <p className="text-dense leading-[1.5] text-ink-3">{address}</p>
      <p className="mt-[16px] max-w-[640px] text-section leading-[1.6] font-normal whitespace-pre-line">
        {body}
      </p>
      {signature !== undefined && <p className="mt-[14px] text-body text-ink-2">{signature}</p>}
      {attachments.length > 0 && (
        <section aria-label="Attachments" className="mt-[24px] flex flex-col gap-[12px]">
          <header className="flex items-center gap-[8px]">
            <Icon name="paperclip" size={14} className="text-ink-3" />
            <h4 className="flex-1 text-section">Attachments</h4>
            <Button
              variant="ghost"
              size="sm"
              icon="download"
              {...(onDownloadAll === undefined ? {} : { onClick: onDownloadAll })}
            >
              Download All
            </Button>
          </header>
          <ul className="flex flex-wrap gap-[16px]">
            {attachments.map((a) => (
              <AttachmentThumb key={a.name} attachment={a} />
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}

/** The agent's filing note above a message: attributed, with Review and nothing else (INV-1). */
export function AgentFilingNote({
  text,
  onReview,
}: {
  /** "Accrued Agent filed 2 of 3 attachments to 2025 Binder · Income". */
  text: string;
  /** Opens what was filed; omit when everything is already reviewed. */
  onReview?: () => void;
}): JSX.Element {
  return (
    <div
      data-agent-note=""
      className="mx-[16px] mt-[16px] flex min-h-[44px] items-center gap-[10px] rounded-nested bg-card px-[14px] shadow-e1"
    >
      <Icon name="sparkles" size={14} className="flex-none text-ink-3" />
      <AgentText inline text={text} className="min-w-0 flex-1 truncate text-body text-ink-2" />
      {onReview !== undefined && (
        <button type="button" onClick={onReview} className="flex-none text-body font-medium">
          Review
        </button>
      )}
    </div>
  );
}

export interface ReadingHeaderProps {
  client: string | null;
  clients: readonly string[];
  onMatch?: (client: string) => void;
  subject: string;
  state: InboxState;
  /** File… (new or waiting) or Move… (filed): the destinations; Ignore is the last section. */
  fileTo?: readonly string[];
  onFile?: (to: string) => void;
  onIgnore?: () => void;
  onReply?: () => void;
  onList?: () => void;
}

/** The reading pane's 44 header: list toggle, client chip, subject, File… or Move…, Reply. */
export function ReadingHeader({
  client,
  clients,
  onMatch,
  subject,
  state,
  fileTo = [],
  onFile,
  onIgnore,
  onReply,
  onList,
}: ReadingHeaderProps): JSX.Element {
  const sections: MenuItem[][] = [
    fileTo.map((to) => ({ label: to, onSelect: () => onFile?.(to) })),
    ...(state === "filed" ? [] : [[{ label: "Ignore", onSelect: () => onIgnore?.() }]]),
  ];
  const canFile = state !== "ignored" && fileTo.length > 0;
  return (
    <div data-reading="header" className="flex h-[44px] w-full items-center gap-[8px]">
      <IconButton
        icon="menu"
        label="Show the list"
        variant="white"
        {...(onList === undefined ? {} : { onClick: onList })}
      />
      <ClientMatchChip
        client={client}
        clients={clients}
        {...(onMatch === undefined ? {} : { onMatch })}
      />
      <span className="min-w-0 flex-1 truncate text-right text-section font-normal text-ink-2">
        {subject}
      </span>
      {canFile && (
        <Menu
          label={state === "filed" ? "Move to" : "File to"}
          width={300}
          trigger={
            <Button variant="secondary" size="md">
              {state === "filed" ? "Move…" : "File…"}
            </Button>
          }
          sections={sections}
        />
      )}
      <Button
        variant="primary"
        size="md"
        icon="reply"
        {...(onReply === undefined ? {} : { onClick: onReply })}
      >
        Reply
      </Button>
    </div>
  );
}
