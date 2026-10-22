import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Button, IconButton } from "../components/button";
import { Menu, type MenuItem } from "../components/popover";
import {
  FrameClose,
  FrameDescription,
  FrameMode,
  FrameTitle,
  HiddenDescription,
  type Loose,
} from "./frame";
import { Layer } from "./layer";

// Drawer (O2, C-23): a record's context beside the list it came from. It floats 10px from the top,
// right and bottom edges at radius 14 on the shell ground with the modal shadow, never full height
// and never dark. 380 for activity, 440 by default, 560 for evidence. The header is 46 high and
// white: the close on the left, a centred title, and `Open` (peek and evidence) and `···` on the
// right.
//
// Modal (the default): the .22 scrim, a focus trap, focus on the close, role dialog. A peek
// (`peek`) is the non-modal record peek: no scrim, no trap, role complementary, and the page stays
// live behind it. Only one drawer is open at a time; opening another replaces it (the OverlayStack
// asks the first to close). It enters with a 24px slide in 260ms and leaves in 180ms.
// The drawer is for context, not primary work: a long form belongs in a Dialog or SheetModal.

export type DrawerSize = "sm" | "md" | "lg";

const WIDTH: Record<DrawerSize, string> = {
  sm: "w-[380px]",
  md: "w-[440px]",
  lg: "w-[560px]",
};

// The older widths, 420 and 480, stay for callers that name one.
const LEGACY_WIDTH = { 420: "w-[420px]", 480: "w-[480px]", 560: "w-[560px]" } as const;

const BOX =
  "flex max-w-[calc(100vw-20px)] flex-col overflow-hidden rounded-dialog bg-shell shadow-modal";
const PLACE = "fixed top-[10px] right-[10px] bottom-[10px]";

export interface DrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** For assistive technology when there is no visible description. */
  description?: string;
  size?: DrawerSize;
  /** Left for callers that name a width in px: 420, 480 or 560. `size` wins when both are given. */
  width?: 420 | 480 | 560;
  /** The non-modal record peek: no scrim, no trap, role complementary. */
  peek?: boolean;
  /** Draws `Open` in the header (peek and evidence): open the full record. */
  onOpen?: () => void;
  /** The `···` menu: groups of items. Without it the button is not drawn. */
  more?: MenuItem[][];
  /** Right of the title, before `Open` (a status pill, record stepping). */
  meta?: ReactNode;
  /** A pinned footer (the primary action). */
  footer?: ReactNode;
  /** Zero padding in the body, for content that sits in `DrawerCard`s (which carry their own
   * 10px margins). The default pads the body 12px. */
  bare?: boolean;
  /** Unsaved changes: closing asks "Discard changes?" first. */
  dirty?: boolean;
  children: ReactNode;
  /** Hold the drawer open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

function Frame({
  title,
  description,
  onOpen,
  more,
  meta,
  footer,
  bare,
  children,
  onClose,
}: Loose<Pick<DrawerProps, "description" | "onOpen" | "more" | "meta" | "footer" | "bare">> & {
  title: string;
  children: ReactNode;
  onClose?: () => void;
}): JSX.Element {
  return (
    <>
      <header className="relative flex h-[46px] shrink-0 items-center justify-center border-b-[0.5px] border-hair bg-card px-[110px]">
        <FrameClose
          className="absolute top-[8px] left-[8px]"
          {...(onClose === undefined ? {} : { onClose })}
        />
        <FrameTitle className="min-w-0 truncate text-pane font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        <div className="absolute top-[9px] right-[8px] flex items-center gap-[6px]">
          {meta}
          {onOpen !== undefined && (
            <Button size="sm" variant="secondary" onClick={onOpen}>
              Open
            </Button>
          )}
          {more !== undefined && (
            <Menu
              label="More actions"
              sections={more}
              trigger={<IconButton icon="ellipsis" label="More actions" variant="white" />}
            />
          )}
        </div>
      </header>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          bare !== true && "gap-[10px] p-[12px]",
        )}
      >
        {description === undefined ? (
          <HiddenDescription text={title} />
        ) : (
          <FrameDescription className="text-para text-ink-2">{description}</FrameDescription>
        )}
        {children}
      </div>
      {footer !== undefined && (
        <div className="flex shrink-0 items-center justify-end gap-2 border-t-[0.5px] border-hair bg-card px-[12px] py-[10px]">
          {footer}
        </div>
      )}
    </>
  );
}

/** A white radius-12 card with a 10px margin: the unit a drawer's body is made of. */
export function DrawerCard({ className, ...props }: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn("m-[10px] overflow-hidden rounded-pane bg-card shadow-e1", className)}
      {...props}
    />
  );
}

export function Drawer({
  open,
  onOpenChange,
  title,
  description,
  size = "md",
  width,
  peek = false,
  onOpen,
  more,
  meta,
  footer,
  bare,
  dirty,
  children,
  forceState,
}: DrawerProps): JSX.Element {
  const w = width !== undefined && size === "md" ? LEGACY_WIDTH[width] : WIDTH[size];
  const frame = { title, description, onOpen, more, meta, footer, bare };
  if (forceState === "open") {
    return (
      <div
        role={peek ? "complementary" : "group"}
        aria-label={title}
        className={cn(BOX, "relative h-full", w)}
      >
        <FrameMode live={false}>
          <Frame {...frame} onClose={() => undefined}>
            {children}
          </Frame>
        </FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind={peek ? "peek" : "drawer"}
      modal={!peek}
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty ?? false}
      title={title}
      scrim="dialog"
      className={cn(BOX, PLACE, w)}
      motion="data-[state=open]:motion-drawer-in data-[state=closed]:motion-drawer-out"
      initialFocus="close"
      role={peek ? "complementary" : "dialog"}
    >
      <Frame {...frame}>{children}</Frame>
    </Layer>
  );
}
