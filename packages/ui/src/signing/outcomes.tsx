import { type JSX, type ReactNode, useState } from "react";
import { HumanAction } from "../attribution/human-action";
import { cn } from "../cn";
import { Button } from "../components/button";
import { ValueRow } from "../components/inputs";
import { RadioGroup } from "../components/toggles";
import { Icon } from "../icons/icon";
import { Dialog } from "../overlays/dialog";
import type { SigningSession, SigningStepVM, StepKey } from "./types";

// The T16 kit's identity, exception and phone parts (F-06-T05, F-06-T06; F-06.md §3 Stories 1.1,
// 1.4 to 1.6; DF-11, DF-12). Provider mode only: identity and the signature run in the provider's
// view, which `ProviderSigningFrame` hosts; there is no native identity part (no KBA card, no
// email-code card, no adopt dialog: Story 1.7). Copy comes from props (the screen's copy module);
// nothing here names the product or the provider.

// ---- ProviderSigningFrame (DF-12) --------------------------------------------------------------

/** The sandbox the provider's embedded view runs in (N-02's CSP `frame-src` names the host): its
 * own scripts and forms in its own origin, popups for its help links; no top navigation, so it can
 * never move the portal away. */
export const PROVIDER_SANDBOX = "allow-scripts allow-same-origin allow-forms allow-popups";

/** Only an https session URL is hosted; anything else draws nothing (the server's URL, but a
 * fixture or a broken mapping must never become an iframe of an arbitrary scheme). */
export function sessionUrlAllowed(url: string): boolean {
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

export interface ProviderSigningFrameProps {
  session: SigningSession;
  /** The frame's accessible title ("Verify your identity and sign: Form 8879"). */
  title: string;
  /** Redirect presentation: the call to action that leaves for the provider. */
  continueLabel: string;
  onContinue?: () => void;
  /** Shown when the URL can't be hosted. */
  unavailable: string;
}

/** The page well's provider view (TPL-16a/c in production). An iframe presentation is titled and
 * sandboxed; a redirect presentation is one call to action. What the provider sends back is never
 * read here: completion is the server's signer status, refetched by the container. */
export function ProviderSigningFrame({
  session,
  title,
  continueLabel,
  onContinue,
  unavailable,
}: ProviderSigningFrameProps): JSX.Element {
  if (!sessionUrlAllowed(session.url)) {
    return (
      <div data-signing="provider-unavailable" className="p-[16px] text-body text-ink-2">
        {unavailable}
      </div>
    );
  }
  if (session.presentation === "redirect") {
    return (
      <div data-signing="provider-redirect" className="flex justify-center p-[16px]">
        <Button
          variant="primary"
          size="lg"
          {...(onContinue === undefined ? {} : { onClick: onContinue })}
        >
          {continueLabel}
        </Button>
      </div>
    );
  }
  return (
    <iframe
      data-signing="provider-frame"
      title={title}
      src={session.url}
      sandbox={PROVIDER_SANDBOX}
      referrerPolicy="no-referrer"
      allow="camera"
      className="h-full min-h-[560px] w-[680px] max-w-full rounded-page border-0 bg-card shadow-page"
    />
  );
}

// ---- Pending confirmation (Story 1.1) ----------------------------------------------------------

export interface PendingConfirmationProps {
  title: string;
  body: string;
}

/** After the provider returns, until the server says the signer signed: never "Completed". */
export function PendingConfirmation({ title, body }: PendingConfirmationProps): JSX.Element {
  return (
    <div
      data-signing="pending-confirmation"
      role="status"
      className="flex flex-col gap-[6px] rounded-nested bg-card p-[14px] shadow-e1"
    >
      <span className="text-body font-medium text-ink">{title}</span>
      <span className="text-meta text-ink-2">{body}</span>
    </div>
  );
}

// ---- VerificationFailedCard (DF-11, TPL-16e) ---------------------------------------------------

export interface VerificationFailedCardProps {
  title: string;
  /** DF-11: the paper-form text naming the firm's contact. */
  body: string;
}

/** Three failed attempts close remote signing for the form (DF-11): no retry, no countdown, no
 * other method; the firm sends a paper form. The card has no control at all. */
export function VerificationFailedCard({ title, body }: VerificationFailedCardProps): JSX.Element {
  return (
    <div
      data-signing="verification-failed"
      role="alert"
      className="flex w-[480px] max-w-full gap-[12px] rounded-dialog bg-card p-[18px] shadow-e2"
    >
      <span className="flex size-[34px] flex-none items-center justify-center rounded-tile bg-red-tint text-red-ink">
        <Icon name="shield-alert" size={17} aria-hidden="true" />
      </span>
      <span className="flex flex-col gap-[4px]">
        <span className="text-title text-ink">{title}</span>
        <span className="text-body text-ink-2">{body}</span>
      </span>
    </div>
  );
}

// ---- DeclineDialog (TPL-16f) -------------------------------------------------------------------

export interface DeclineChoice {
  reason: string;
  note: string;
}

export interface DeclineCopy {
  title: string;
  reasons: readonly string[];
  /** The reasons group's accessible name. */
  reasonsLabel: string;
  noteLabel: string;
  confirm: string;
  /** The trigger in the envelope header ("Decline…"). */
  trigger: string;
}

export interface DeclineDialogProps {
  copy: DeclineCopy;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called once per confirmation with the chosen reason and the note. */
  onDecline: (choice: DeclineChoice) => void;
  trigger?: ReactNode;
  /** Hold the dialog open in place for a specimen. */
  forceState?: "open";
}

/** "Decline to sign?": four reasons and a note; Decline (destructive) waits for a reason. Focus
 * returns to the trigger on close (the Dialog's). */
export function DeclineDialog({
  copy,
  open,
  onOpenChange,
  onDecline,
  trigger,
  forceState,
}: DeclineDialogProps): JSX.Element {
  const [reason, setReason] = useState<string | undefined>(undefined);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setReason(undefined);
          setNote("");
          setSent(false);
        }
        onOpenChange(next);
      }}
      title={copy.title}
      size="sm"
      dirty={reason !== undefined || note !== ""}
      {...(trigger === undefined ? {} : { trigger })}
      {...(forceState === undefined ? {} : { forceState })}
      action={
        <Button
          variant="destructive"
          size="sm"
          disabled={reason === undefined || sent}
          data-signing="decline-confirm"
          onClick={() => {
            if (reason === undefined || sent) return;
            setSent(true);
            onDecline({ reason, note });
          }}
        >
          {copy.confirm}
        </Button>
      }
    >
      <div className="flex flex-col gap-[10px] rounded-nested bg-card p-[12px] shadow-e1">
        <RadioGroup
          label={copy.reasonsLabel}
          options={copy.reasons.map((r) => ({ value: r, label: r }))}
          {...(reason === undefined ? {} : { value: reason })}
          onChange={setReason}
        />
      </div>
      <div className="mt-[10px] overflow-hidden rounded-nested bg-card shadow-e1">
        <ValueRow
          kind="paragraph"
          label={copy.noteLabel}
          value={note}
          onChange={setNote}
          rows={3}
        />
      </div>
    </Dialog>
  );
}

// ---- Phone parts (TPL-16g, TPL-19 frame 9) ----------------------------------------------------

export interface StepChipsProps {
  steps: readonly SigningStepVM[];
  /** Each step's name ("Verify", "Review", "Sign", "Done"). */
  names: Readonly<Record<StepKey, string>>;
}

/** The 390 step row: "Verify ✓ · Review ✓ · Sign · Done". The current step is 500. */
export function StepChips({ steps, names }: StepChipsProps): JSX.Element {
  return (
    <ol
      data-signing="step-chips"
      aria-label="Steps"
      className="flex min-h-[44px] flex-wrap items-center gap-x-[6px] text-meta text-ink-2"
    >
      {steps.map((step, i) => (
        <li
          key={step.key}
          aria-current={step.state === "current" ? "step" : undefined}
          className={cn(
            "inline-flex items-center",
            step.state === "current" && "font-medium text-ink",
          )}
        >
          {names[step.key]}
          {step.state === "done" ? " ✓" : ""}
          {i < steps.length - 1 && (
            <span aria-hidden="true" className="ml-[6px] text-ink-4">
              ·
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

/** The sticky sign bar's heights: TPL-16g and POR-06 64, TPL-19 frame 9 72 (F-06 §11.2 Q4). */
export type MobileSignBarHeight = 64 | 72;

export interface MobileSignBarProps {
  /** The viewer: the sign control is theirs (a HumanAction), never an agent's. */
  viewer: string;
  onClick?: () => void;
  disabled?: boolean;
  height?: MobileSignBarHeight;
}

/** The phone's sticky bottom bar: one 48 primary, full width, "Adopt signature & sign…". */
export function MobileSignBar({
  viewer,
  onClick,
  disabled = false,
  height = 64,
}: MobileSignBarProps): JSX.Element {
  return (
    <div
      data-signing="mobile-sign-bar"
      data-height={height}
      style={{ height }}
      className="flex items-center"
    >
      <HumanAction
        verb="Adopt"
        object="signature & sign"
        opensDialog
        actor={{ kind: "human", name: viewer }}
        variant="primary"
        size="xl"
        className="h-[48px] w-full"
        disabled={disabled}
        {...(onClick === undefined ? {} : { onClick })}
      />
    </div>
  );
}
