// ChatHeader (F-07-T02; handoff T4 CHAT header; SPEC-652 AC-3). 46 high: the Paperclip ⌄ context
// chip at the left; centred, the 8 px olive LiveDot, the title (14.5/500) and the owner (14.5/400
// ink-2, from `formatActor`); at the right Bug, Pencil and Trash2 icon buttons and "Create Agent…".
// Each control emits an intent; nothing here fetches. A locked session disables every action.
import type { JSX } from "react";
import { type Actor, formatActor } from "../../attribution/actor";
import { Button, IconButton } from "../../components/button";
import { LiveDot } from "../../components/motion";
import { Icon } from "../../icons";

export interface ChatHeaderProps {
  title: string;
  owner: Actor;
  live: boolean;
  /** How many context references the session holds (the chip's accessible name). */
  contextCount?: number;
  locked?: boolean;
  still?: boolean;
  onContext?: () => void;
  onOpenTrace?: () => void;
  onRename?: () => void;
  onDelete?: () => void;
  onCreateAgent?: () => void;
}

export function ChatHeader({
  title,
  owner,
  live,
  contextCount = 0,
  locked = false,
  still = false,
  onContext,
  onOpenTrace,
  onRename,
  onDelete,
  onCreateAgent,
}: ChatHeaderProps): JSX.Element {
  return (
    <header
      data-kit="ChatHeader"
      style={{ height: 46 }}
      className="flex shrink-0 items-center gap-[8px] px-[12px]"
    >
      <button
        type="button"
        aria-label={`Context: ${String(contextCount)} item${contextCount === 1 ? "" : "s"}`}
        disabled={locked}
        onClick={onContext}
        className="flex h-[28px] items-center gap-[2px] rounded-[7px] bg-card px-[8px] shadow-e1"
      >
        <Icon name="paperclip" size={14} />
        <Icon name="chevron-down" size={12} />
      </button>
      <span className="flex min-w-0 flex-1 items-center justify-center gap-[8px]">
        {live ? <LiveDot still={still} /> : null}
        <span className="truncate text-[14.5px] font-medium">{title}</span>
        <span data-owner className="truncate text-[14.5px] text-ink-2">
          {formatActor(owner)}
        </span>
      </span>
      <IconButton icon="bug" label="Open run trace" disabled={locked} onClick={onOpenTrace} />
      <IconButton icon="pencil" label="Rename session" disabled={locked} onClick={onRename} />
      <IconButton icon="trash-2" label="Delete session" disabled={locked} onClick={onDelete} />
      <Button variant="secondary" disabled={locked} onClick={onCreateAgent}>
        <Icon name="sparkles" size={14} />
        Create Agent…
      </Button>
    </header>
  );
}
