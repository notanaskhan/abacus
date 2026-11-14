// ChatThread (F-07-T03; handoff T4 THREAD; SPEC-652 AC-4). The renderer registry is keyed by C6
// v2's eight `SessionItemOut` kinds; `plan`, `question` and the slot kinds `approval`,
// `decision_ref` and `run_card` render the consumer's slot (P-04's ApprovalCard and DecisionCard,
// W-02's plan card, P-09's RunCard, F-07-T06's QuestionCard). With no slot, or a kind the registry
// does not know, a neutral row renders and the raw payload never does. Every agent string goes
// through AgentText or AgentBlocks (ADR-065, P-24); a line arriving now reveals 20 ms a word on the
// client (no token streaming, P-46), and under reduced motion or `still` (`?static=1`) the whole
// verified text shows at once. A locked thread renders no item and no composer (INV-3). The kit
// renders no Approve, Reject, Decide, Sign off, Release or Send control (INV-1).
import { type JSX, type ReactNode, useEffect, useRef, useState } from "react";
import { AgentText } from "../../agent-text";
import { Button } from "../../components/button";
import { Spinner } from "../../components/motion";
import { Icon } from "../../icons";
import { useWordReveal } from "../../motion";
import { type AgentBlocksPayload, AgentBlocks, type BlockFact } from "../blocks";

export type ThreadItemKind =
  | "user_message"
  | "agent_blocks"
  | "plan"
  | "question"
  | "answer"
  | "tool_card"
  | "artifact"
  | "notice";
export type SlotKind = "plan" | "question" | "approval" | "decision_ref" | "run_card";

/** A C6 v2 session item as the thread reads it (structurally `SessionItemOut`). */
export interface ThreadItem {
  id: string;
  seq: number;
  kind: string;
  payload: Readonly<Record<string, unknown>>;
  run_id?: string | null;
  step_id?: string | null;
  actor_kind: "human" | "agent" | "system";
  actor_name?: string | null;
}

export type ArtifactIntent = "open" | "download" | "save";

export interface ChatThreadProps {
  items: readonly ThreadItem[];
  locked?: boolean;
  slots?: Partial<Record<SlotKind, (item: ThreadItem) => ReactNode>>;
  /** Figures code registered for the run, by fact id (AgentBlocks' `{fact}` tokens). */
  facts?: Readonly<Record<string, BlockFact>>;
  /** Items appended after the first render reveal word by word; `still` shows them at once. */
  still?: boolean;
  /** The question card's place above the composer (F-07-T06's QuestionCard, through a slot). */
  above?: ReactNode;
  composerPlaceholder?: string;
  /** F-07-T07: what a session with no items shows in the thread (EmptySession, T4a). */
  empty?: ReactNode;
  /** F-07-T07: text placed in the composer (a suggested prompt), never sent by itself. A new
   * `nonce` replaces what is there and focuses the composer. */
  draft?: { text: string; nonce: number } | null;
  onRetryStep?: (stepId: string) => void;
  onOpenRun?: (runId: string) => void;
  onArtifact?: (artifactId: string, intent: ArtifactIntent) => void;
  onSend?: (body: string) => void;
  /** W-02-T17: Edit and resend on the person's own bubble (the consumer drafts it again and
   * sends it as a new turn naming the edited item). */
  onEditResend?: (seq: number, text: string) => void;
}

const NEUTRAL = "This item can’t be shown here.";

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function NeutralRow(): JSX.Element {
  return (
    <div data-row="neutral" className="text-[12.5px] text-ink-3">
      {NEUTRAL}
    </div>
  );
}

function MeBubble({
  text,
  onEdit,
}: {
  text: string;
  /** W-02-T17 (WB-01): the bubble's "···" menu: Copy, and Edit and resend (the person's own). */
  onEdit?: (() => void) | undefined;
}): JSX.Element {
  const [menu, setMenu] = useState(false);
  return (
    <div className="group flex items-center justify-end gap-[4px]">
      {onEdit !== undefined ? (
        <span className="relative">
          <button
            type="button"
            aria-label="Message actions"
            aria-expanded={menu}
            onClick={() => {
              setMenu(!menu);
            }}
            className="flex size-[22px] items-center justify-center rounded-pill text-ink-3 opacity-0 group-hover:opacity-100 focus:opacity-100"
          >
            <Icon name="ellipsis" size={13} />
          </button>
          {menu ? (
            <span role="menu" className="absolute right-0 z-10 mt-[4px] flex w-[240px] flex-col rounded-[10px] bg-card py-[4px] shadow-e2">
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenu(false);
                  void navigator.clipboard?.writeText(text).catch(() => undefined);
                }}
                className="px-[10px] py-[6px] text-left text-[13px] text-ink hover:bg-nested"
              >
                Copy
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenu(false);
                  onEdit();
                }}
                className="px-[10px] py-[6px] text-left text-[13px] text-ink hover:bg-nested"
              >
                Edit and resend
              </button>
            </span>
          ) : null}
        </span>
      ) : null}
      <p
        data-bubble="me"
        className="max-w-[56%] rounded-[14px] bg-espresso px-[14px] py-[10px] text-[13.5px] leading-[1.45] text-on-dark"
      >
        {text}
      </p>
    </div>
  );
}

function blocksOf(payload: Readonly<Record<string, unknown>>): AgentBlocksPayload | null {
  const b = payload.blocks;
  if (typeof b !== "object" || b === null) return null;
  const parts = (b as { parts?: unknown }).parts;
  return Array.isArray(parts) ? (b as AgentBlocksPayload) : null;
}

/** A paragraph-only, text-only answer: drawn as a line bubble and revealed word by word. */
function lineText(blocks: AgentBlocksPayload): string | null {
  if (blocks.parts.length !== 1) return null;
  const only = blocks.parts[0] as { kind: string; segments?: { kind: string; text?: string }[] };
  if (only.kind !== "p" || !only.segments?.every((s) => s.kind === "text")) return null;
  return only.segments.map((s) => s.text ?? "").join("");
}

function LineBubble({ text, still }: { text: string; still: boolean }): JSX.Element {
  const shown = useWordReveal(text, { still });
  return (
    <div
      data-bubble="line"
      aria-busy={!shown.done}
      className="max-w-[74%] self-start rounded-[14px] bg-card px-[14px] py-[10px] text-[13.5px] leading-[1.45] shadow-e1"
    >
      <AgentText text={shown.text} inline />
    </div>
  );
}

function BlockCard({
  blocks,
  facts,
  badge,
}: {
  blocks: AgentBlocksPayload;
  facts: Readonly<Record<string, BlockFact>>;
  badge: string | null;
}): JSX.Element {
  return (
    <div
      data-bubble="block"
      className="relative rounded-[14px] bg-card px-[16px] pt-[13px] pb-[14px] text-[13.5px] leading-[1.45] shadow-e2"
    >
      {badge ? (
        <span
          data-badge
          className="absolute top-[10px] right-[12px] rounded-[6px] bg-green-tint px-[6px] text-[11.5px] text-green-ink"
        >
          ✓ {badge}
        </span>
      ) : null}
      <AgentBlocks blocks={blocks} facts={facts} />
    </div>
  );
}

function ToolCardRow({
  item,
  onRetryStep,
  onOpenRun,
  still,
}: {
  item: ThreadItem;
  onRetryStep?: ((stepId: string) => void) | undefined;
  onOpenRun?: ((runId: string) => void) | undefined;
  still: boolean;
}): JSX.Element {
  const state = str(item.payload.state);
  const label = str(item.payload.label);
  if (state === "failed") {
    const error = (item.payload.error ?? {}) as { title?: unknown; body?: unknown };
    return (
      <div
        role="alert"
        data-row="error"
        className="flex items-start gap-[10px] rounded-[12px] bg-red-tint px-[14px] py-[10px] text-[13px]"
      >
        <Icon name="x" size={14} className="mt-[2px] text-red-ink" />
        <span className="flex flex-1 flex-col">
          <span className="font-medium text-red-ink">
            {str(error.title) || `Stopped at ${label}`}
          </span>
          {str(error.body) ? <span className="text-ink-2">{str(error.body)}</span> : null}
        </span>
        <Button
          variant="secondary"
          onClick={() => {
            onRetryStep?.(item.step_id ?? item.id);
          }}
        >
          Retry
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            if (item.run_id) onOpenRun?.(item.run_id);
          }}
        >
          View run
        </Button>
      </div>
    );
  }
  const counters = Array.isArray(item.payload.counters)
    ? (item.payload.counters as { label?: unknown; state?: unknown; value?: unknown }[])
    : [];
  return (
    <div data-row="tool" data-state={state} className="flex flex-col gap-[4px] text-[12.5px]">
      <span className="flex items-center gap-[6px]">
        {state === "running" ? (
          <Spinner label="Running" size={10} showLabel={false} still={still} />
        ) : state === "succeeded" ? (
          <Icon name="check" size={13} className="text-green" />
        ) : null}
        <span>{label}</span>
      </span>
      {counters.length > 0 ? (
        <span data-counters className="flex gap-[14px] pl-[19px] text-ink-2">
          {counters.map((c) => (
            <span
              key={str(c.label)}
              data-counter={str(c.label)}
              className="flex items-center gap-[4px]"
            >
              {str(c.label)}
              {str(c.state) === "succeeded" ? (
                <Icon name="check" size={12} className="text-green" />
              ) : (
                <Spinner label="Running" size={10} showLabel={false} still={still} />
              )}
              <span className="tabular-nums">{str(c.value)}</span>
            </span>
          ))}
        </span>
      ) : null}
    </div>
  );
}

function FileArtifactRow({
  item,
  onArtifact,
}: {
  item: ThreadItem;
  onArtifact?: ((id: string, intent: ArtifactIntent) => void) | undefined;
}): JSX.Element {
  const id = str(item.payload.artifact_id);
  return (
    <div
      data-row="artifact"
      className="flex items-center gap-[10px] rounded-[12px] bg-card px-[14px] py-[10px] shadow-e1"
    >
      <Icon name="file-spreadsheet" size={14} />
      <span className="flex flex-1 flex-col">
        <span className="text-[13px] font-medium">{str(item.payload.name)}</span>
        <span className="text-[11.5px] text-ink-3">{str(item.payload.meta)}</span>
      </span>
      <Button variant="secondary" onClick={() => onArtifact?.(id, "open")}>
        Open
      </Button>
      <Button variant="secondary" onClick={() => onArtifact?.(id, "download")}>
        Download
      </Button>
      <Button variant="secondary" onClick={() => onArtifact?.(id, "save")}>
        Save to Files
      </Button>
    </div>
  );
}

function NoticeRow({ item }: { item: ThreadItem }): JSX.Element {
  // The server's fixed words (a code's copy), never model text.
  return (
    <div data-row="notice" className="text-[12.5px] text-ink-2">
      {str(item.payload.text) || NEUTRAL}
    </div>
  );
}

function Composer({
  placeholder,
  disabled,
  draft,
  onSend,
}: {
  placeholder: string;
  disabled: boolean;
  draft?: { text: string; nonce: number } | null | undefined;
  onSend?: ((body: string) => void) | undefined;
}): JSX.Element {
  const [body, setBody] = useState("");
  const field = useRef<HTMLTextAreaElement | null>(null);
  // A suggested prompt fills the composer; only the person's Enter or the send button sends it.
  useEffect(() => {
    if (draft == null) return;
    setBody(draft.text);
    field.current?.focus();
  }, [draft?.nonce]);
  const send = (): void => {
    const text = body.trim();
    if (!text) return;
    onSend?.(text);
    setBody("");
  };
  return (
    <div
      data-kit="Composer"
      className="mx-[16px] mb-[12px] flex min-h-[50px] items-center gap-[8px] rounded-[12px] bg-nested px-[12px]"
    >
      <Icon name="paperclip" size={14} className="text-ink-3" />
      <textarea
        ref={field}
        aria-label="Message"
        placeholder={placeholder}
        rows={1}
        value={body}
        disabled={disabled}
        onChange={(e) => {
          setBody(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        className="max-h-[160px] flex-1 resize-none bg-transparent py-[14px] text-[13.5px] outline-none"
      />
      <button
        type="button"
        aria-label="Send message"
        disabled={disabled || body.trim().length === 0}
        onClick={send}
        data-ready={body.trim().length > 0}
        className={`flex size-[32px] items-center justify-center rounded-pill shadow-e1 ${
          body.trim().length > 0 ? "bg-espresso text-on-dark" : "bg-card"
        }`}
      >
        <Icon name="arrow-right" size={14} />
      </button>
    </div>
  );
}

function render(
  item: ThreadItem,
  props: ChatThreadProps,
  revealed: ReadonlySet<string>,
): ReactNode {
  const slot = props.slots?.[item.kind as SlotKind];
  const still = props.still === true || !revealed.has(item.id);
  switch (item.kind as ThreadItemKind) {
    case "user_message":
      return (
        <MeBubble
          text={str(item.payload.body)}
          onEdit={
            props.onEditResend === undefined
              ? undefined
              : () => props.onEditResend?.(item.seq, str(item.payload.body))
          }
        />
      );
    case "answer":
      return <MeBubble text={str(item.payload.title) || str(item.payload.body)} />;
    case "agent_blocks": {
      const blocks = blocksOf(item.payload);
      if (blocks === null) return <NeutralRow />;
      const line = lineText(blocks);
      if (line !== null && !item.payload.badge) return <LineBubble text={line} still={still} />;
      return (
        <BlockCard
          blocks={blocks}
          facts={props.facts ?? {}}
          badge={str(item.payload.badge) || null}
        />
      );
    }
    case "tool_card":
      return (
        <ToolCardRow
          item={item}
          onRetryStep={props.onRetryStep}
          onOpenRun={props.onOpenRun}
          still={props.still === true}
        />
      );
    case "artifact":
      return <FileArtifactRow item={item} onArtifact={props.onArtifact} />;
    case "notice":
      return <NoticeRow item={item} />;
    case "plan":
    case "question":
      return slot ? slot(item) : <NeutralRow />;
    default:
      return slot ? slot(item) : <NeutralRow />;
  }
}

export function ChatThread(props: ChatThreadProps): JSX.Element {
  const { items, locked = false, above, composerPlaceholder = "Message", onSend } = props;
  const scroller = useRef<HTMLDivElement | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [unseen, setUnseen] = useState(false);
  const seen = useRef<Set<string> | null>(null);
  // Items present on the first render are history (shown whole); later ones reveal.
  if (seen.current === null) seen.current = new Set(items.map((i) => i.id));
  const revealed = new Set(items.filter((i) => !seen.current?.has(i.id)).map((i) => i.id));
  const last = items.at(-1)?.id;

  useEffect(() => {
    const el = scroller.current;
    if (el === null) return;
    if (atBottom) el.scrollTop = el.scrollHeight;
    else setUnseen(true);
    // biome-ignore lint/correctness/useExhaustiveDependencies: only a new last item moves the view
  }, [last]);

  if (locked) {
    return <div data-kit="ChatThread" data-locked="true" className="flex-1 bg-shell" />;
  }
  return (
    <div data-kit="ChatThread" className="relative flex min-h-0 flex-1 flex-col bg-shell">
      <div
        ref={scroller}
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        onScroll={(e) => {
          const el = e.currentTarget;
          const bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          setAtBottom(bottom);
          if (bottom) setUnseen(false);
        }}
        className="flex min-h-0 flex-1 flex-col gap-[11px] overflow-y-auto px-[16px] pt-[16px]"
      >
        {items.length === 0 && props.empty ? props.empty : null}
        {items.map((item) => (
          <div key={item.id} data-item={item.kind} data-seq={item.seq} className="flex flex-col">
            {render(item, props, revealed)}
          </div>
        ))}
      </div>
      {unseen && !atBottom ? (
        <button
          type="button"
          aria-label="Jump to latest"
          data-jump
          onClick={() => {
            const el = scroller.current;
            if (el !== null) el.scrollTop = el.scrollHeight;
            setAtBottom(true);
            setUnseen(false);
            const items = el?.querySelectorAll<HTMLElement>("[data-item]");
            items?.[items.length - 1]?.focus();
          }}
          className="mx-auto mb-[12px] flex size-[30px] items-center justify-center rounded-pill bg-card shadow-e1"
        >
          <Icon name="arrow-down" size={14} />
        </button>
      ) : null}
      {above ? <div className="mx-[16px] mb-[9px]">{above}</div> : null}
      <Composer
        placeholder={composerPlaceholder}
        disabled={false}
        draft={props.draft}
        onSend={onSend}
      />
    </div>
  );
}
