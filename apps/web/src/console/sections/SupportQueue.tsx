// Support queue (G-04-T17; G-04 §5.1 `?ov=support-queue[:<conversationId>]`, O2 480; DEC-32,
// DEC-5701): the firms' support conversations, unanswered first, opened from the "Support queue"
// pill. A conversation shows on the C-10 ChatThread kit: the staff member's replies are their own
// bubbles, a firm user's messages are line bubbles with the author's name; text only, never agent
// output, so no AgentText applies.
import type { QueueConversationDetailOut, QueueConversationsOut } from "@abacus/api-client";
import {
  ChatThread,
  type ChatThreadProps,
  Drawer,
  EmptyState,
  Pill,
  type ThreadItem,
} from "@abacus/ui";
import type { JSX } from "react";
import { SECTIONS_COPY } from "./copy";

const C = SECTIONS_COPY.queue;

export interface SupportQueueProps {
  data: QueueConversationsOut;
  /** The open conversation, when one is selected. */
  detail?: QueueConversationDetailOut | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect?: (conversationId: string) => void;
  onReply?: (conversationId: string, body: string) => void;
}

function items(detail: QueueConversationDetailOut): ThreadItem[] {
  return detail.messages.map((m, seq) => ({
    id: m.id,
    seq,
    kind: m.author_kind === "staff" ? "user_message" : "firm_message",
    payload: { body: m.body, author: m.author_display_name },
    actor_kind: "human",
    actor_name: m.author_display_name,
  }));
}

function FirmBubble({ item }: { item: ThreadItem }): JSX.Element {
  return (
    <div className="flex max-w-[82%] flex-col gap-[2px]" data-row="firm_message">
      <span className="text-[11.5px] text-ink-3">{String(item.payload.author ?? "")}</span>
      <p className="rounded-[14px] bg-card px-[12px] py-[8px] text-[13px] text-ink hairline">
        {String(item.payload.body ?? "")}
      </p>
    </div>
  );
}

export function SupportQueue({
  data,
  detail = null,
  open,
  onOpenChange,
  onSelect,
  onReply,
}: SupportQueueProps): JSX.Element {
  const ordered = [...data.items].sort((a, b) => Number(b.unanswered) - Number(a.unanswered));
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={C.title} width={480}>
      <div className="flex h-full flex-col gap-[10px]" data-console-section="queue">
        {detail === null ? (
          ordered.length === 0 ? (
            <EmptyState title={C.empty} />
          ) : (
            <ul className="flex flex-col">
              {ordered.map((q) => (
                <li key={q.id} className="hairline-t first:border-t-0">
                  <button
                    type="button"
                    className="flex w-full items-center gap-[8px] px-[4px] py-[9px] text-left text-[13px]"
                    onClick={() => onSelect?.(q.id)}
                  >
                    <span className="flex-1">
                      <span className="text-ink">{q.firm_display_name}</span>
                      <span className="ml-[6px] text-ink-3">{q.owner_display_name}</span>
                    </span>
                    <Pill variant={q.unanswered ? "amber" : "neutral"} size="sm">
                      {q.unanswered ? C.unanswered : C.answered}
                    </Pill>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          <ChatThread
            items={items(detail)}
            still
            slots={
              {
                firm_message: (item: ThreadItem) => <FirmBubble item={item} />,
              } as unknown as NonNullable<ChatThreadProps["slots"]>
            }
            composerPlaceholder={C.reply}
            onSend={(body) => onReply?.(detail.conversation.id, body)}
          />
        )}
      </div>
    </Drawer>
  );
}
