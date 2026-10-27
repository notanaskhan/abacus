import { type JSX, type ReactNode, useId } from "react";
import { HumanAction } from "../attribution/human-action";
import { cn } from "../cn";
import { Button, IconButton } from "../components/button";
import { Pill } from "../components/pill";
import { StatusDisc } from "../components/status";
import { Icon } from "../icons/icon";
import { status } from "../status";
import type {
  AuthorizingVM,
  EnvelopeVM,
  EvidenceItem,
  SignerChipVM,
  SignerVM,
  SigningDocumentVM,
  SigningStepVM,
} from "./types";

// The T16 signing kit's L2 parts (F-06-T04; T16 and TPL-16 handoff; F-06.md §5.2, §5.5). Words come
// from the C2 registry (`envelope`, `envelope_signer`, `signing_step`) or from props; nothing here
// counts signers, unmasks a TIN or names the product. No part carries an agent element (INV-1):
// the one sign control is a HumanAction.

// ---- Envelope header (46) ----------------------------------------------------------------------

export interface EnvelopeHeaderProps {
  envelope: Pick<EnvelopeVM, "title" | "status" | "signedCount" | "signerCount">;
  backLabel: string;
  onBack?: () => void;
  /** Decline is offered while the viewer can still sign. */
  canDecline: boolean;
  onOpenDecline?: () => void;
  onDownload?: () => void;
}

/** The envelope's pill: "1 of 2 signed" from the server's counts, "Completed" and so on. */
export function envelopePill(
  envelope: Pick<EnvelopeVM, "status" | "signedCount" | "signerCount">,
): JSX.Element {
  const s = status("envelope", envelope.status, {
    vars: { signed: envelope.signedCount, total: envelope.signerCount },
  });
  return (
    <Pill variant={s.variant ?? "neutral"} size="state" check={s.check} data-envelope-pill="">
      {s.label}
    </Pill>
  );
}

export function EnvelopeHeader({
  envelope,
  backLabel,
  onBack,
  canDecline,
  onOpenDecline,
  onDownload,
}: EnvelopeHeaderProps): JSX.Element {
  return (
    <div
      data-signing="envelope-header"
      className="relative flex h-[46px] flex-none items-center gap-2 px-[12px]"
    >
      <Button variant="secondary" size="sm" icon="chevron-left" onClick={onBack}>
        {backLabel}
      </Button>
      <div className="pointer-events-none absolute inset-x-0 flex items-center justify-center gap-2">
        <h1 className="truncate text-pane font-medium">{envelope.title}</h1>
        {envelopePill(envelope)}
      </div>
      <div className="ml-auto flex items-center gap-2">
        {canDecline && (
          <Button
            variant="ghost"
            size="sm"
            opensDialog
            className="text-red-ink"
            onClick={onOpenDecline}
          >
            Decline…
          </Button>
        )}
        <IconButton icon="download" label="Download" onClick={onDownload} />
      </div>
    </div>
  );
}

// ---- Signer chips (shared with TPL-01b and SIG-01) ------------------------------------------------

export interface SignerChipsProps {
  chips: readonly SignerChipVM[];
  /** A chip opens SIG-01 (firm side); without it the chips are text. */
  onOpen?: () => void;
  className?: string;
}

function chipText(chip: SignerChipVM): string {
  if (chip.status === "signed") {
    return `✓ ${chip.name}${chip.date === undefined ? "" : ` · ${chip.date}`}`;
  }
  return `○ ${chip.name}`;
}

/** One chip per signer: "✓ Dev · Sep 9" green-tint once signed, "○ Mira" neutral until then. */
export function SignerChips({ chips, onOpen, className }: SignerChipsProps): JSX.Element {
  const list = (
    <span data-signer-chips="" className={cn("flex flex-wrap items-center gap-1", className)}>
      {chips.map((chip) => (
        <Pill
          key={chip.signerId}
          size="sm"
          variant={chip.status === "signed" ? "green-tint" : "neutral"}
          data-signer={chip.signerId}
        >
          {chipText(chip)}
        </Pill>
      ))}
    </span>
  );
  if (onOpen === undefined) return list;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="rounded-pill focus-visible:outline-[1.5px] focus-visible:outline-espresso"
    >
      {list}
    </button>
  );
}

// ---- Documents pane (240) ------------------------------------------------------------------------

export interface SigningDocumentListProps {
  documents: readonly SigningDocumentVM[];
  selected: string;
  onSelect: (documentId: string) => void;
  signers: readonly SignerVM[];
}

export function SigningDocumentList({
  documents,
  selected,
  onSelect,
  signers,
}: SigningDocumentListProps): JSX.Element {
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      data-signing="documents"
      className="flex w-[240px] flex-none flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <h2 id={heading} className="flex h-[46px] flex-none items-center px-[12px] text-section">
        {`Documents (${String(documents.length)})`}
      </h2>
      <ul className="flex flex-col">
        {documents.map((doc) => (
          <li key={doc.id}>
            <button
              type="button"
              aria-current={doc.id === selected ? "true" : undefined}
              onClick={() => {
                onSelect(doc.id);
              }}
              data-document={doc.id}
              className={cn(
                "flex min-h-[64px] w-full items-start gap-2 border-t-[0.5px] border-hair px-[12px] py-[10px] text-left",
                "hover:bg-tonal-hover aria-[current=true]:bg-sel-bg",
              )}
            >
              <Icon name="file-text" size={15} className="mt-[1px] flex-none text-ink-3" />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="text-dense font-medium">{doc.name}</span>
                <SignerChips chips={doc.signerChips} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-auto flex flex-col border-t-[0.5px] border-hair">
        <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-section">Signers</h3>
        <ul className="flex flex-col">
          {signers.map((s) => (
            <li key={s.id} data-signer-row={s.id} className="flex flex-col px-[12px] py-[8px]">
              <span className="text-dense font-medium">
                {s.isViewer ? `${s.name} (you)` : s.name}
              </span>
              <span className="text-meta text-ink-3">{s.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ---- Steps pane (300) ----------------------------------------------------------------------------

const STEP_DISC = { done: "done", current: "half", todo: "todo" } as const;

export interface SigningStepsProps {
  steps: readonly SigningStepVM[];
  /** The consent and the call to action under the steps. */
  children?: ReactNode;
}

/** The ordered steps Verify identity · Review · Sign · Done, the current one marked for assistive
 * technology (`aria-current="step"`). */
export function SigningSteps({ steps, children }: SigningStepsProps): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <ol aria-label="Signing steps" className="flex flex-col">
        {steps.map((step) => (
          <li
            key={step.key}
            data-step={step.key}
            aria-current={step.state === "current" ? "step" : undefined}
            className="flex min-h-[52px] items-start gap-[10px] py-[6px]"
          >
            <StatusDisc state={STEP_DISC[step.state]} size={17} className="mt-[1px]" />
            <span className="flex flex-col">
              <span
                className={cn("text-dense", step.state === "current" ? "font-medium" : undefined)}
              >
                {status("signing_step", step.key).label}
              </span>
              {step.sub !== "" && <span className="text-meta text-ink-3">{step.sub}</span>}
            </span>
          </li>
        ))}
      </ol>
      {children}
    </div>
  );
}

/** "What you're authorizing": the firm's text, never model text. */
export function AuthorizingCard({ authorizing }: { authorizing: AuthorizingVM }): JSX.Element {
  return (
    <section
      aria-label={authorizing.title}
      className="flex flex-col gap-1 rounded-nested bg-shell p-[12px] shadow-[inset_0_0_0_0.5px_var(--color-hair)]"
    >
      <h3 className="text-dense font-medium">{authorizing.title}</h3>
      <p className="text-para">{authorizing.body}</p>
    </section>
  );
}

export interface SignCallToActionProps {
  viewer: SignerVM;
  note: string;
  onClick?: () => void;
  disabled?: boolean;
}

/** The sign call to action, "Adopt signature & sign…": a HumanAction for the viewer, so it can
 * never render for an agent. */
export function SignCallToAction({
  viewer,
  note,
  onClick,
  disabled = false,
}: SignCallToActionProps): JSX.Element {
  return (
    <div className="flex flex-col gap-2">
      <HumanAction
        verb="Adopt"
        object="signature & sign"
        opensDialog
        actor={{ kind: "human", name: viewer.name }}
        variant="primary"
        size="xl"
        className="w-full"
        disabled={disabled}
        onClick={onClick}
      />
      <p className="text-meta text-ink-3">{note}</p>
    </div>
  );
}

// ---- Completion ----------------------------------------------------------------------------------

/** The evidence record as label and value rows (TPL-16d: six items). */
export function EvidenceList({ items }: { items: readonly EvidenceItem[] }): JSX.Element {
  return (
    <dl data-signing="evidence" className="flex flex-col">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex min-h-[30px] items-baseline gap-3 border-t-[0.5px] border-hair py-[6px]"
        >
          <dt className="w-[86px] flex-none text-meta text-ink-3">{item.label}</dt>
          <dd className="min-w-0 text-cell">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export interface CompletionCardProps {
  title: string;
  evidence: readonly EvidenceItem[];
  note?: string;
}

/** The steps pane once everyone has signed: the olive tile, the thanks, the evidence record. */
export function CompletionCard({ title, evidence, note }: CompletionCardProps): JSX.Element {
  return (
    <section data-signing="completion" aria-label={title} className="flex flex-col gap-3">
      <span
        aria-hidden="true"
        className="inline-flex size-[34px] items-center justify-center rounded-tile bg-green text-on-dark"
      >
        <Icon name="check" size={18} />
      </span>
      <h2 className="text-title font-medium">{title}</h2>
      <EvidenceList items={evidence} />
      {note !== undefined && <p className="text-meta text-ink-3">{note}</p>}
    </section>
  );
}
