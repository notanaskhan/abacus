// Empty session and context (F-07-T07; handoff T4a, TPL-04b; SPEC-652 AC-4 consumers).
// `EmptySession` fills the thread of a new session: the sparkles tile, "New session", the line
// "Ask about any client, engagement or return. The agent works read-only until you approve a
// change.", and a 2 × 2 grid of suggested prompts. Picking one hands its text to the composer
// (ChatThread's `draft`); nothing is sent until the person sends it (INV-1). `ContextChips` is the
// row above the composer: "+ Client record", "+ Documents", "+ Workpapers", each opening the
// Paperclip context picker on its kind, and attached items as chips with a remove button.
// Data comes through props; nothing here fetches. Prompts are the host's (L3), never kit samples.
import type { JSX } from "react";
import { Icon } from "../../icons";

export interface SuggestedPrompt {
  id: string;
  /** The card's title, and the text the composer receives unless `text` says otherwise. */
  title: string;
  detail?: string | null;
  text?: string;
}

export interface EmptySessionProps {
  prompts: readonly SuggestedPrompt[];
  onPick: (text: string, prompt: SuggestedPrompt) => void;
  title?: string;
  body?: string;
}

export const EMPTY_SESSION_COPY = {
  title: "New session",
  body: "Ask about any client, engagement or return. The agent works read-only until you approve a change.",
} as const;

/** T4a geometry (product px): a 32 tile, cards 286 wide and at least 80 tall in a 2 × 2 grid. */
export const EMPTY_SESSION_GEOMETRY = { tile: 32, card: { width: 286, minHeight: 80 }, gap: 6 };

export function EmptySession({
  prompts,
  onPick,
  title = EMPTY_SESSION_COPY.title,
  body = EMPTY_SESSION_COPY.body,
}: EmptySessionProps): JSX.Element {
  return (
    <div
      data-kit="EmptySession"
      className="flex flex-1 flex-col items-center justify-center gap-[6px] px-[16px] pb-[24px]"
    >
      <span
        aria-hidden="true"
        className="mb-[8px] flex size-[32px] items-center justify-center rounded-[8px] bg-nested text-ink-2"
      >
        <Icon name="sparkles" size={14} />
      </span>
      <h2 className="text-[14.5px] font-medium">{title}</h2>
      <p className="max-w-[310px] text-center text-[12.5px] leading-[1.45] text-ink-2">{body}</p>
      {prompts.length > 0 ? (
        <ul
          aria-label="Suggested prompts"
          className="mt-[18px] grid w-full max-w-[578px] grid-cols-2 gap-[6px]"
        >
          {prompts.slice(0, 4).map((prompt) => (
            <li key={prompt.id} className="flex">
              <button
                type="button"
                data-prompt={prompt.id}
                onClick={() => {
                  onPick(prompt.text ?? prompt.title, prompt);
                }}
                className="flex min-h-[80px] flex-1 flex-col items-start gap-[3px] rounded-[10px] bg-card px-[13px] py-[12px] text-left shadow-e1 hover:shadow-e3"
              >
                <span className="text-[13px] font-medium leading-[1.35]">{prompt.title}</span>
                {prompt.detail ? (
                  <span className="text-[12px] leading-[1.35] text-ink-2">{prompt.detail}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export type ContextKind = "client_record" | "documents" | "workpapers";

export const CONTEXT_KINDS: readonly { kind: ContextKind; label: string }[] = [
  { kind: "client_record", label: "Client record" },
  { kind: "documents", label: "Documents" },
  { kind: "workpapers", label: "Workpapers" },
];

/** A record the session holds as context: identifiers and the label L3 gives it. */
export interface ContextItem {
  id: string;
  kind: ContextKind;
  label: string;
  /** "Brooklyn, NY · Household", "PDF · 2 pages": L3's words. */
  detail?: string | null;
}

export interface ContextChipsProps {
  attached: readonly ContextItem[];
  onAdd: (kind: ContextKind) => void;
  onRemove?: (item: ContextItem) => void;
  locked?: boolean;
}

export function ContextChips({
  attached,
  onAdd,
  onRemove,
  locked = false,
}: ContextChipsProps): JSX.Element {
  return (
    <div
      data-kit="ContextChips"
      aria-label="Context"
      role="group"
      className="flex flex-wrap items-center gap-[6px]"
    >
      {attached.map((item) => (
        <span
          key={item.id}
          data-context={item.id}
          className="flex h-[26px] items-center gap-[5px] rounded-pill bg-card pr-[4px] pl-[10px] text-[12.5px] shadow-e1"
        >
          <Icon name="paperclip" size={12} className="text-ink-3" />
          <span className="max-w-[220px] truncate">{item.label}</span>
          {onRemove ? (
            <button
              type="button"
              aria-label={`Remove ${item.label}`}
              disabled={locked}
              onClick={() => {
                onRemove(item);
              }}
              className="flex size-[18px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
            >
              <Icon name="x" size={12} />
            </button>
          ) : null}
        </span>
      ))}
      {CONTEXT_KINDS.map(({ kind, label }) => (
        <button
          key={kind}
          type="button"
          data-add-context={kind}
          disabled={locked}
          onClick={() => {
            onAdd(kind);
          }}
          className="flex h-[26px] items-center gap-[5px] rounded-pill bg-card px-[10px] text-[12.5px] shadow-e1"
        >
          <Icon name="plus" size={12} className="text-ink-2" />
          {label}
        </button>
      ))}
    </div>
  );
}
