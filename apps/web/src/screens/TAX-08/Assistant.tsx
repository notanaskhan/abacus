// TAX-08 · Return › Assistant panel (T-04-T34; handoff TAX-08) in fixture mode: an O2 drawer docked
// at 420 over TAX-05 with no scrim, so the tree and viewer stay live underneath. The thread holds
// the person's bubble, the agent's block (through AgentText), the inline K-1 card with its
// treatment chips (hovering a row lights its box in the viewer underneath, purple only through the
// match tokens), and the E7 ApprovalCard: Approve is a person's HumanAction, Edit… makes the after
// values editable, Reject… asks a reason. Approving collapses the card to the 9:31 AM checkpoint
// line with Undo for 10 seconds (DEC-24); the host passes Issues 4 → 3 from the server. No
// control on an agent-owned element reads approve, send or sign.
import {
  AgentText,
  ApprovalCard,
  Button,
  Pill,
  Skeleton,
  Spinner,
  type Actor,
  type DiffRow,
} from "@abacus/ui";
import { type JSX, useEffect, useState } from "react";
import {
  CHIPS,
  COPY,
  DIFF,
  FOLLOW_UP_TABLE,
  FOLLOW_UPS,
  type Frame,
  IDLE_PROMPTS,
  K1_ROWS,
  LIT_ROW,
  VIEWER,
} from "./copy";

export const UNDO_MS = 10_000;

export interface AssistantProps {
  frame: Frame;
  /** The person viewing (Approve renders only for a person). */
  actor?: Actor;
  /** Approve adjustments: the same `proposal.approve` API as SHL-10 (inline approve). */
  onApprove?: (edits: Readonly<Record<string, string>>) => void;
  /** Reject… with its reason. */
  onReject?: (reason: string) => void;
  /** Undo within 10 s of an approval (DEC-24). */
  onUndo?: () => void;
  /** A suggested prompt or the composer's text. */
  onAsk?: (text: string) => void;
  /** The source row: SHL-08 with K-1 page 2 and box 18A lit. */
  onOpenSource?: () => void;
  /** Hovering a K-1 card row: light its box in the viewer underneath (null on leave). */
  onLightRegion?: (region: string | null) => void;
  onHistory?: () => void;
  onNewThread?: () => void;
  onClose?: () => void;
}

const PERSON: Actor = { kind: "human", name: VIEWER };

function Header({
  onClose,
  onHistory,
  onNewThread,
}: Pick<AssistantProps, "onClose" | "onHistory" | "onNewThread">): JSX.Element {
  return (
    <header className="flex h-[46px] items-center justify-between bg-card px-[10px]">
      <button
        type="button"
        aria-label={COPY.close}
        onClick={onClose}
        className="flex size-[30px] items-center justify-center rounded-full bg-chip"
      >
        ✕
      </button>
      <h2 className="flex items-center gap-[6px] text-[14.5px] font-medium">
        <span aria-hidden data-live className="size-[8px] rounded-full bg-green" />
        {COPY.title}
      </h2>
      <div className="flex gap-[6px]">
        <Button variant="secondary" aria-label={COPY.history} onClick={onHistory}>
          {COPY.history}
        </Button>
        <Button variant="secondary" aria-label={COPY.newThread} onClick={onNewThread}>
          {COPY.newThread}
        </Button>
      </div>
    </header>
  );
}

function K1Card({
  lit,
  onLightRegion,
}: {
  lit: boolean;
  onLightRegion?: AssistantProps["onLightRegion"];
}): JSX.Element {
  return (
    <div data-k1-card className="overflow-hidden rounded-[10px] shadow-hair">
      <div className="flex h-[34px] items-center justify-between bg-band-hd px-[12px] text-[13px] font-medium">
        <span>{COPY.k1Head}</span>
        <Pill variant="amber">{COPY.draftPill}</Pill>
      </div>
      <ul aria-label={COPY.k1Head}>
        {K1_ROWS.map((row) => (
          <li
            key={row.key}
            data-k1-row={row.key}
            data-region={row.region}
            data-lit={lit && row.key === LIT_ROW ? "true" : "false"}
            onMouseEnter={() => onLightRegion?.(row.region)}
            onMouseLeave={() => onLightRegion?.(null)}
            className={
              lit && row.key === LIT_ROW
                ? "flex h-[32px] items-center justify-between bg-match-bg px-[12px] ring-1 ring-match-line"
                : "flex h-[32px] items-center justify-between px-[12px]"
            }
          >
            <span className="text-ink-2">{row.label}</span>
            <span className="font-medium">{row.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Chips(): JSX.Element {
  return (
    <ul aria-label="Treatments" className="flex flex-wrap gap-[6px]">
      {CHIPS.map((chip) => (
        <li
          key={chip}
          data-chip
          className="flex h-[24px] items-center rounded-full bg-chip px-[10px] text-[12px] font-medium text-ink-2 shadow-hair"
        >
          {chip}
        </li>
      ))}
    </ul>
  );
}

function UserBubble({ text }: { text: string }): JSX.Element {
  return (
    <div className="flex justify-end">
      <p
        data-bubble="person"
        className="max-w-[80%] rounded-[14px] bg-ink px-[14px] py-[10px] text-[13px] leading-[1.45] text-card"
      >
        {text}
      </p>
    </div>
  );
}

function AgentBlock({ children }: { children: JSX.Element | JSX.Element[] }): JSX.Element {
  return (
    <div
      data-block="agent"
      className="flex flex-col gap-[10px] rounded-[14px] bg-card px-[14px] py-[13px] shadow-e2"
    >
      {children}
    </div>
  );
}

function Proposal({
  frame,
  actor,
  onApprove,
  onReject,
  onOpenSource,
}: Pick<
  AssistantProps,
  "frame" | "actor" | "onApprove" | "onReject" | "onOpenSource"
>): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const rows: DiffRow[] = DIFF.map((d) => ({
    key: d.key,
    label: d.label,
    before: d.before,
    after: edits[d.key] ?? d.after,
    cites: 2,
  }));
  return (
    <ApprovalCard
      title={COPY.cardTitle}
      actor={actor ?? PERSON}
      reasoning={
        <div
          className="flex flex-col gap-[4px]"
          data-focus={frame === "a2" ? "change" : undefined}
        >
          <span className="text-[13.5px] font-medium text-ink">{COPY.reasoningHead}</span>
          <AgentText text={COPY.reasoning} />
        </div>
      }
      rows={rows}
      evidence={[
        {
          key: "k1",
          label: COPY.source,
          meta: COPY.sourceMeta,
          ...(onOpenSource === undefined ? {} : { onOpen: onOpenSource }),
        },
      ]}
      policyNote={COPY.policy}
      approveObject={COPY.approveObject}
      rejectLabel={COPY.reject}
      onReject={() => {
        setRejecting(true);
      }}
      onApprove={() => onApprove?.(edits)}
      {...(editing
        ? {
            renderAfter: (row: DiffRow) => (
              <input
                aria-label={row.label}
                value={row.after ?? ""}
                onChange={(e) => {
                  setEdits((prev) => ({ ...prev, [row.key]: e.target.value }));
                }}
                className="w-[96px] rounded-[6px] bg-card px-[6px] text-right shadow-hair"
              />
            ),
          }
        : {})}
      actions={
        <Button
          variant="tonal"
          opensDialog
          onClick={() => {
            setEditing(true);
          }}
        >
          {COPY.edit}
        </Button>
      }
      afterRows={
        rejecting ? (
          <form
            className="flex gap-[8px] px-[12px] py-[8px]"
            onSubmit={(e) => {
              e.preventDefault();
              if (reason.trim()) onReject?.(reason.trim());
            }}
          >
            <input
              aria-label={COPY.rejectReason}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
              className="flex-1 rounded-[6px] bg-card px-[8px] shadow-hair"
            />
            <Button variant="secondary" type="submit" disabled={!reason.trim()}>
              {COPY.reject.replace("…", "")}
            </Button>
          </form>
        ) : undefined
      }
    />
  );
}

function Applied({ onUndo }: Pick<AssistantProps, "onUndo">): JSX.Element {
  const [undoable, setUndoable] = useState(true);
  useEffect(() => {
    const timer = setTimeout(() => {
      setUndoable(false);
    }, UNDO_MS);
    return () => {
      clearTimeout(timer);
    };
  }, []);
  return (
    <div data-applied className="flex items-center justify-between text-[12.5px] text-green-ink">
      <span>{COPY.applied}</span>
      {undoable && (
        <Button variant="ghost" onClick={onUndo}>
          {COPY.undo}
        </Button>
      )}
      <span role="status" className="sr-only">
        {COPY.toast}
      </span>
    </div>
  );
}

function FollowUpTable(): JSX.Element {
  return (
    <table aria-label="2024 and 2025" className="w-full text-[12.5px]">
      <thead>
        <tr className="text-ink-3">
          <th className="text-left font-normal" />
          <th className="text-right font-normal">2024</th>
          <th className="text-right font-normal">2025</th>
        </tr>
      </thead>
      <tbody>
        {FOLLOW_UP_TABLE.map((r) => (
          <tr key={r.label} className="h-[28px]">
            <td className="text-ink-2">{r.label}</td>
            <td className="text-right">{r.y2024}</td>
            <td className="text-right font-medium">{r.y2025}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Suggestions({
  prompts,
  onAsk,
  cards = false,
}: {
  prompts: readonly string[];
  onAsk?: AssistantProps["onAsk"];
  cards?: boolean;
}): JSX.Element {
  return (
    <div className={cards ? "flex flex-col gap-[8px]" : "flex flex-wrap gap-[6px]"}>
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          data-suggestion
          onClick={() => onAsk?.(p)}
          className={
            cards
              ? "rounded-[12px] bg-card px-[12px] py-[10px] text-left text-[12.5px] shadow-e1"
              : "h-[28px] rounded-full bg-card px-[10px] text-[12.5px] shadow-e1"
          }
        >
          {p}
        </button>
      ))}
    </div>
  );
}

function Composer({ onAsk }: Pick<AssistantProps, "onAsk">): JSX.Element {
  const [text, setText] = useState("");
  return (
    <form
      className="mx-[10px] mb-[10px] flex h-[50px] items-center gap-[8px] rounded-[12px] bg-chip px-[10px] shadow-hair"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) onAsk?.(text.trim());
        setText("");
      }}
    >
      <input
        aria-label={COPY.composer}
        placeholder={COPY.composer}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
        }}
        className="flex-1 bg-transparent text-[13.5px] placeholder:text-ink-3"
      />
      <button
        type="submit"
        aria-label={COPY.send}
        className="flex size-[32px] items-center justify-center rounded-full bg-card shadow-e1"
      >
        ↑
      </button>
    </form>
  );
}

function Thread(props: AssistantProps): JSX.Element {
  const { frame } = props;
  if (frame === "b") {
    return (
      <Suggestions prompts={IDLE_PROMPTS} cards {...(props.onAsk ? { onAsk: props.onAsk } : {})} />
    );
  }
  if (frame === "c") {
    return (
      <>
        <UserBubble text={COPY.question} />
        <AgentBlock>
          <div data-narration className="flex items-center gap-[8px] text-[13px] text-ink-2">
            <Spinner label={COPY.thinking} />
            <AgentText inline text={COPY.thinking} />
          </div>
          <Skeleton />
        </AgentBlock>
      </>
    );
  }
  const lit = frame === "a" || frame === "a2";
  return (
    <>
      <UserBubble text={COPY.question} />
      <AgentBlock>
        <AgentText text={COPY.answer} />
        <K1Card
          lit={lit}
          {...(props.onLightRegion ? { onLightRegion: props.onLightRegion } : {})}
        />
        <Chips />
        <AgentText text={COPY.closing} />
      </AgentBlock>
      {(frame === "a" || frame === "a2") && <Proposal {...props} />}
      {frame === "d" && <Applied {...(props.onUndo ? { onUndo: props.onUndo } : {})} />}
      {frame === "e" && (
        <p data-rejected className="text-[12.5px] text-red-ink">
          {COPY.rejected}
        </p>
      )}
      {frame === "f" && (
        <>
          <UserBubble text={COPY.followUpQuestion} />
          <AgentBlock>
            <AgentText text={COPY.followUpAnswer} />
            <FollowUpTable />
          </AgentBlock>
        </>
      )}
      {frame === "a" && (
        <Suggestions prompts={FOLLOW_UPS} {...(props.onAsk ? { onAsk: props.onAsk } : {})} />
      )}
    </>
  );
}

export function Assistant(props: AssistantProps): JSX.Element {
  const { frame } = props;
  return (
    <aside
      data-screen="TAX-08"
      data-frame={frame}
      aria-label={COPY.title}
      className="flex h-full w-[420px] flex-col overflow-hidden rounded-[14px] bg-surface shadow-e3"
    >
      <Header
        {...(props.onClose ? { onClose: props.onClose } : {})}
        {...(props.onHistory ? { onHistory: props.onHistory } : {})}
        {...(props.onNewThread ? { onNewThread: props.onNewThread } : {})}
      />
      {frame === "notAllowed" ? (
        <p role="alert" className="p-[16px] text-[13px] text-ink-2">
          {COPY.notAllowed}
        </p>
      ) : frame === "loading" ? (
        <div
          aria-busy="true"
          aria-label={COPY.loading}
          className="flex flex-col gap-[10px] p-[12px]"
        >
          <Skeleton />
          <Skeleton />
        </div>
      ) : (
        <>
          <div className="m-[10px] flex h-[32px] items-center rounded-[10px] bg-card px-[10px] text-[11.5px] text-ink-2 shadow-e1">
            {COPY.context}
          </div>
          <div data-thread className="flex flex-1 flex-col gap-[10px] overflow-y-auto p-[12px]">
            <Thread {...props} />
          </div>
          <Composer {...(props.onAsk ? { onAsk: props.onAsk } : {})} />
        </>
      )}
    </aside>
  );
}
