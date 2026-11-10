// ReviewNoteThread v1 (A-06-T24; AUD-17; P-04-T48's grammar): a review note's messages and its reply
// composer, on the well. A message from the agent's work reads "<person> via Agent" with the atom
// glyph, and its body goes through the caller's AgentText when it is agent-written. Data-free: the
// screen passes the server's events.

import { type JSX, type ReactNode, useState } from "react";
import { Button } from "../components/button";
import { cn } from "../cn";

export interface ReviewNoteMessage {
  id: string;
  who: ReactNode;
  at: string;
  body: ReactNode;
  /** The mini diff row ("EBP-04 v2 → v3"). */
  diff?: ReactNode;
}

export interface ReviewNoteThreadProps {
  messages: readonly ReviewNoteMessage[];
  /** The amber line when the note changed a paper after a sign-off. */
  notice?: ReactNode;
  replyLabel: string;
  sendLabel: string;
  /** None: the composer is hidden (a read-only viewer). */
  onReply?: (text: string) => void;
  busy?: boolean;
  className?: string;
}

export function ReviewNoteThread({
  messages,
  notice,
  replyLabel,
  sendLabel,
  onReply,
  busy = false,
  className,
}: ReviewNoteThreadProps): JSX.Element {
  const [draft, setDraft] = useState("");
  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)} data-kit="review-note-thread">
      <ol className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-y-auto bg-shell p-[12px]">
        {messages.map((m) => (
          <li key={m.id} className="rounded-[10px] bg-card px-[12px] py-[10px] shadow-e1">
            <div className="flex items-baseline gap-[6px]">
              <span className="text-[12.5px] font-medium">{m.who}</span>
              <span className="text-[11.5px] text-ink-3">{m.at}</span>
            </div>
            <div className="text-[12.5px] leading-[1.55]">{m.body}</div>
            {m.diff != null && <div className="mt-[4px] text-[11.5px] text-ink-3">{m.diff}</div>}
          </li>
        ))}
      </ol>
      {notice != null && (
        <div className="flex min-h-[32px] items-center bg-amber-tint px-[12px] text-[12.5px] text-amber-ink">
          {notice}
        </div>
      )}
      {onReply !== undefined && (
        <form
          className="flex h-[44px] items-center gap-[6px] bg-composer px-[10px]"
          onSubmit={(event) => {
            event.preventDefault();
            if (draft.trim() === "") return;
            onReply(draft.trim());
            setDraft("");
          }}
        >
          <input
            aria-label={replyLabel}
            placeholder={replyLabel}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
            className="min-w-0 flex-1 bg-transparent text-[13px] outline-none"
          />
          <Button size="xs" variant="primary" type="submit" disabled={busy || draft.trim() === ""}>
            {sendLabel}
          </Button>
        </form>
      )}
    </div>
  );
}
