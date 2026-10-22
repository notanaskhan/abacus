import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { StatusDisc } from "../components/status";
import { FrameClose, FrameDescription, FrameMode, FrameTitle, HiddenDescription } from "./frame";
import { Layer } from "./layer";

// Wizard (O6, plan 04 section 5.3; ENG-03 for the geometry): the full sheet's frame (inset 14, top
// 60, radius 14, the .30 scrim, a 46-high white header with the title centred and the close on the
// right) around a 220-wide step list and a body, over a 56-high sticky footer: Back on the left;
// Save draft and Next on the right, and on the last step Create. The wizard draws the frame only.
// The steps, their order and the body of each are data the screen passes (the type catalogue and
// the gate cards are TPL-18's, F-05-T38); a screen's gate block goes in `aside`.

export type WizardStepState = "done" | "current" | "todo";

export interface WizardStep {
  id: string;
  label: string;
  /** done: an olive check; current: a half disc and a selected row; todo: a ring. */
  state: WizardStepState;
}

export interface WizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Next to the title in ink-3: "Draft · saved 9:39 AM". */
  subtitle?: string;
  description?: string;
  steps: readonly WizardStep[];
  /** A press on a done step goes back to it. Without it the list is not interactive. */
  onStepChange?: (id: string) => void;
  /** Under the list: a screen's gate block. */
  aside?: ReactNode;
  /** The current step's body. */
  children: ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  /** Next stays disabled until the step can be left. */
  nextDisabled?: boolean;
  onSaveDraft?: () => void;
  /** The last step's primary: "Create". */
  createLabel?: string;
  onCreate?: () => void;
  createDisabled?: boolean;
  /** Replaces the right of the footer, for a last step with two creates. */
  actions?: ReactNode;
  /** Unsaved changes: closing asks "Discard changes?" first. */
  dirty?: boolean;
  /** Hold the wizard open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

const BOX = "flex flex-col overflow-hidden rounded-dialog bg-shell shadow-sheet";
const PLACE = "fixed inset-x-[14px] top-[60px] bottom-[14px]";

function Frame({
  title,
  subtitle,
  description,
  steps,
  onStepChange,
  aside,
  children,
  onBack,
  onNext,
  nextDisabled,
  onSaveDraft,
  createLabel = "Create",
  onCreate,
  createDisabled,
  actions,
  onClose,
}: Omit<WizardProps, "open" | "onOpenChange" | "dirty" | "forceState"> & {
  onClose?: () => void;
}): JSX.Element {
  const at = steps.findIndex((s) => s.state === "current");
  const last = at === steps.length - 1;
  return (
    <>
      <header className="relative flex h-[46px] shrink-0 items-center justify-center gap-[8px] border-b-[0.5px] border-hair bg-card px-[56px]">
        <FrameTitle className="min-w-0 truncate text-title font-medium tracking-[-0.012em]">
          {title}
        </FrameTitle>
        {subtitle !== undefined && (
          <span className="shrink-0 text-body text-ink-3">{subtitle}</span>
        )}
        <FrameClose
          className="absolute top-[8px] right-[9px]"
          {...(onClose === undefined ? {} : { onClose })}
        />
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-[220px_minmax(0,1fr)]">
        <nav
          aria-label="Steps"
          className="flex min-h-0 flex-col gap-[1px] overflow-y-auto border-r-[0.5px] border-hair bg-card pt-[6px]"
        >
          <ol className="flex flex-col">
            {steps.map((step, i) => {
              const row = (
                <>
                  <StatusDisc
                    state={
                      step.state === "done" ? "done" : step.state === "current" ? "half" : "todo"
                    }
                    size={15}
                  />
                  <span className="min-w-0 flex-1 truncate">{step.label}</span>
                </>
              );
              const cls = cn(
                "flex h-[38px] w-full items-center gap-[10px] px-[14px] text-left text-body",
                step.state === "current" && "bg-sel-bg font-medium",
              );
              return (
                <li key={step.id}>
                  {onStepChange !== undefined && step.state === "done" ? (
                    <button
                      type="button"
                      className={cn(cls, "hover:bg-nav-fill")}
                      onClick={() => {
                        onStepChange(step.id);
                      }}
                    >
                      <span className="sr-only">{`Step ${String(i + 1)}: `}</span>
                      {row}
                    </button>
                  ) : (
                    <div
                      className={cls}
                      {...(step.state === "current" ? { "aria-current": "step" as const } : {})}
                    >
                      <span className="sr-only">{`Step ${String(i + 1)}: `}</span>
                      {row}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
          {aside !== undefined && (
            <div className="px-[14px] pt-[14px] pb-[12px] text-dense text-ink-3">{aside}</div>
          )}
        </nav>
        <div className="min-h-0 overflow-y-auto p-[12px]">
          {description === undefined ? (
            <HiddenDescription text={title} />
          ) : (
            <FrameDescription className="sr-only">{description}</FrameDescription>
          )}
          {children}
        </div>
      </div>
      <footer className="flex h-[56px] shrink-0 items-center justify-between border-t-[0.5px] border-hair bg-card px-[14px]">
        <Button variant="secondary" size="lg" disabled={at <= 0} onClick={onBack}>
          Back
        </Button>
        <div className="flex items-center gap-[8px]">
          {actions ?? (
            <>
              {onSaveDraft !== undefined && (
                <Button variant="ghost" size="lg" onClick={onSaveDraft}>
                  Save draft
                </Button>
              )}
              {last ? (
                <span data-overlay-action="" className="contents">
                  <Button size="lg" disabled={createDisabled === true} onClick={onCreate}>
                    {createLabel}
                  </Button>
                </span>
              ) : (
                <span data-overlay-action="" className="contents">
                  <Button size="lg" disabled={nextDisabled === true} onClick={onNext}>
                    Next
                  </Button>
                </span>
              )}
            </>
          )}
        </div>
      </footer>
    </>
  );
}

export function Wizard({
  open,
  onOpenChange,
  dirty,
  forceState,
  ...frame
}: WizardProps): JSX.Element {
  if (forceState === "open") {
    return (
      <div role="group" aria-label={frame.title} className={cn(BOX, "relative h-full")}>
        <FrameMode live={false}>
          <Frame {...frame} onClose={() => undefined} />
        </FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind="wizard"
      open={open}
      onOpenChange={onOpenChange}
      dirty={dirty ?? false}
      title={frame.title}
      scrim="sheet"
      className={cn(BOX, PLACE)}
      motion="data-[state=open]:motion-rise data-[state=closed]:motion-fade-out"
      initialFocus="close"
    >
      <Frame {...frame} />
    </Layer>
  );
}
