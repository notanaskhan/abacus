import type { HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";
import {
  FrameClose,
  FrameDescription,
  FrameMode,
  FrameTitle,
  HiddenDescription,
  type Loose,
} from "./frame";
import { Layer } from "./layer";

// SheetModal (O3, C-13 Edit Agent sheet, C-22): a focused task over the page. 500 wide, from 52
// below the top to the window's bottom, rounded 16 16 0 0, on the shell ground with the modal
// shadow, over the .28 scrim. The header is 56 high and white: the close on the left, a centred
// 15/500 title, and the one primary action ("Save") on the right, disabled until there is
// something to save. It rises 24px in 260ms and leaves in 200ms.
//
// FullSheet (O4, C-22): inset 14, top 60, radius 14, a 46-high header with the title centred and
// the close on the right, and a body of white cards in three columns, over the .30 scrim.

const SHEET_BOX =
  "fixed inset-x-0 top-[52px] bottom-0 mx-auto flex w-[500px] max-w-[calc(100vw-32px)] flex-col overflow-hidden rounded-t-window bg-shell shadow-modal";

export interface SheetModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** For assistive technology when there is no visible description. */
  description?: string;
  trigger?: ReactNode;
  /** The one primary action, in the header's right. Disable it until the form can be saved. */
  action?: ReactNode;
  /** Beside the action: a status pill, record stepping. */
  meta?: ReactNode;
  /** A pinned footer. The kit has none; kept for callers that already pin their action here. */
  footer?: ReactNode;
  /** Unsaved changes: closing asks "Discard changes?" first. */
  dirty?: boolean;
  children: ReactNode;
  /** Hold the sheet open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

function SheetFrame({
  title,
  description,
  action,
  meta,
  footer,
  children,
  onClose,
}: Loose<Pick<SheetModalProps, "description" | "action" | "meta" | "footer">> & {
  title: string;
  children: ReactNode;
  onClose?: () => void;
}): JSX.Element {
  return (
    <>
      <header className="relative flex h-[56px] shrink-0 items-center justify-center border-b-[0.5px] border-hair bg-card px-[110px]">
        <FrameClose
          className="absolute top-[13px] left-[14px]"
          {...(onClose === undefined ? {} : { onClose })}
        />
        <FrameTitle className="min-w-0 truncate text-title font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        <div className="absolute top-[13px] right-[14px] flex items-center gap-[8px]">
          {meta}
          {action !== undefined && (
            <span data-overlay-action="" className="contents">
              {action}
            </span>
          )}
        </div>
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-[12px] overflow-y-auto p-[12px]">
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

export function SheetModal({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  action,
  meta,
  footer,
  dirty,
  children,
  forceState,
}: SheetModalProps): JSX.Element {
  const frame = { title, description, action, meta, footer };
  if (forceState === "open") {
    return (
      <div
        role="group"
        aria-label={title}
        className={cn(SHEET_BOX, "relative inset-x-auto top-auto bottom-auto h-full")}
      >
        <FrameMode live={false}>
          <SheetFrame {...frame} onClose={() => undefined}>
            {children}
          </SheetFrame>
        </FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind="sheet"
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty ?? false}
      title={title}
      scrim="agent"
      className={SHEET_BOX}
      motion="data-[state=open]:motion-sheet-in data-[state=closed]:motion-sheet-out"
      initialFocus="field"
      trigger={trigger}
    >
      <SheetFrame {...frame}>{children}</SheetFrame>
    </Layer>
  );
}

/** The earlier name of SheetModal, kept so every caller is unchanged. */
export const Sheet = SheetModal;

// ---- FullSheet ---------------------------------------------------------------------------------

const FULL_BOX = "flex flex-col overflow-hidden rounded-dialog bg-shell shadow-sheet";
const FULL_PLACE = "fixed inset-x-[14px] top-[60px] bottom-[14px]";

export interface FullSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  trigger?: ReactNode;
  dirty?: boolean;
  /** The body. For three columns of cards, use `SheetColumns`. */
  children: ReactNode;
  /** Hold the sheet open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

function FullFrame({
  title,
  description,
  children,
  onClose,
}: Loose<Pick<FullSheetProps, "description">> & {
  title: string;
  children: ReactNode;
  onClose?: () => void;
}): JSX.Element {
  return (
    <>
      <header className="relative flex h-[46px] shrink-0 items-center justify-center border-b-[0.5px] border-hair bg-card px-[56px]">
        <FrameTitle className="min-w-0 truncate text-title font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        <FrameClose
          className="absolute top-[8px] right-[9px]"
          {...(onClose === undefined ? {} : { onClose })}
        />
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">
        {description === undefined ? (
          <HiddenDescription text={title} />
        ) : (
          <FrameDescription className="sr-only">{description}</FrameDescription>
        )}
        {children}
      </div>
    </>
  );
}

export function FullSheet({
  open,
  onOpenChange,
  title,
  description,
  trigger,
  dirty,
  children,
  forceState,
}: FullSheetProps): JSX.Element {
  if (forceState === "open") {
    return (
      <div role="group" aria-label={title} className={cn(FULL_BOX, "relative h-full")}>
        <FrameMode live={false}>
          <FullFrame title={title} description={description} onClose={() => undefined}>
            {children}
          </FullFrame>
        </FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind="full-sheet"
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty ?? false}
      title={title}
      scrim="sheet"
      className={cn(FULL_BOX, FULL_PLACE)}
      motion="data-[state=open]:motion-rise data-[state=closed]:motion-fade-out"
      initialFocus="close"
      trigger={trigger}
    >
      <FullFrame title={title} description={description}>
        {children}
      </FullFrame>
    </Layer>
  );
}

/** The full sheet's body: three equal columns of cards, gap 10, padding 12. */
export function SheetColumns({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn(
        "grid min-h-0 flex-1 grid-cols-3 gap-[10px] overflow-auto p-[12px]",
        className,
      )}
      {...props}
    />
  );
}

/** One column: a white radius-12 card with a 40-high header and 36-high rows. */
export function SheetColumn({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section
      aria-label={title}
      className="min-w-0 self-start overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <h3 className="flex h-[40px] items-center border-b-[0.5px] border-hair px-[14px] text-section">
        {title}
      </h3>
      {children}
    </section>
  );
}

/** A row of a column: the key in ink-2, the value at 500, right-aligned. */
export function SheetRow({ label, value }: { label: string; value: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[36px] items-center justify-between gap-[12px] border-b-[0.5px] border-hair px-[14px] text-dense last:border-b-0">
      <span className="text-ink-2">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
