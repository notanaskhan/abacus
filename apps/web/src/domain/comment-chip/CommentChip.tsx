// C-29's row chip (P-05-T10; SHL-18a): a 20h chip at a row's end that opens the thread in an O1
// popover 420 anchored to it. Mounted by host screens behind `collaboration.v2` (AUD-09 rows).
// Its own public root, apart from `domain/collaboration`: a host route (AUD-09, inside the AUD-02
// chunk) carries the chip only, and the thread loads when the chip first opens (bundle budget).
import { Icon, Popover } from "@abacus/ui";
import { type JSX, lazy, Suspense, useState } from "react";
import { useSession } from "../../app-core/session";
import type { CommentAnchor } from "../collaboration/CommentThread";

const LiveCommentThread = lazy(async () => ({
  default: (await import("../collaboration/CommentThread")).LiveCommentThread,
}));

export interface CommentChipProps {
  anchor: CommentAnchor;
  anchorLabel: string;
  engagementId: string;
  engagementLabel: string;
  context?: { title: string; kind?: string };
  count?: number;
}

export function CommentChip({
  anchor,
  anchorLabel,
  engagementId,
  engagementLabel,
  context,
  count,
}: CommentChipProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const session = useSession();
  return (
    <Popover
      width={420}
      open={open}
      onOpenChange={setOpen}
      label={`Comments on ${anchorLabel}`}
      trigger={
        <button
          type="button"
          aria-label={`Comments on ${anchorLabel}`}
          data-c29="chip"
          className={`flex h-[20px] items-center gap-[3px] rounded-[6px] px-[5px] text-[11px] text-ink-2 ${open ? "bg-chip" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            setOpen((v) => !v);
          }}
        >
          <Icon name="message-square" size={12} />
          {count !== undefined && count > 0 ? count : null}
        </button>
      }
    >
      <Suspense fallback={null}>
        <LiveCommentThread
          variant="popover"
          anchor={anchor}
          anchorLabel={anchorLabel}
          engagementId={engagementId}
          engagementLabel={engagementLabel}
          viewerId={session.user?.id ?? ""}
          {...(context ? { context } : {})}
          onClose={() => {
            setOpen(false);
          }}
        />
      </Suspense>
    </Popover>
  );
}
