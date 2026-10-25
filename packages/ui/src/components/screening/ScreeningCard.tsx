import type { JSX, ReactNode } from "react";
import { cn } from "../../cn";
import { Icon, type IconName } from "../../icons";
import { Button } from "../button";
import { Count, Ring } from "../pill";
import { Skeleton } from "../states";
import { StatusDisc } from "../status";

// C-34 ScreeningCard (P-06-T22; handoff SHL-20 spec "CARD (C-34)"; DEC-48). The evidence screening
// of an upload against its request, 420 wide: a 44 header with the screening time and the verdict,
// the request line, two named checks ("Does this answer the request?", "Is it inside the expected
// period?"), the flagged-file band with View and Return… per file, a footer of the person's
// controls and thumbs, and the provenance line. States: flagged, passed, not screened and running
// (a rerun in flight: a spinner in the header, skeleton bars for the answers, a disabled footer).
//
// L2: the kit draws what it is given and never fetches. A verdict is a word and a glyph, never a
// percentage (P-06 §7): the card has no place for a confidence. Screening never accepts, returns
// or sends anything by itself; the footer holds only controls a person presses, and a flag's
// reason (verified agent text) comes in as a node the host renders through AgentText.

export type ScreeningVerdict = "passed" | "flagged" | "not_screened";
export type ScreeningCheckVerdict = "pass" | "flag" | "not_run";

/** The C-34 labels (handoff SHL-20 spec, verbatim). */
export const SCREENING_LABELS = {
  title: "Evidence screening",
  verdict: { passed: "Passed", flagged: "Flagged", not_screened: "Not screened" },
  questions: {
    right_document: "Does this answer the request?",
    right_period: "Is it inside the expected period?",
  },
  flaggedFiles: "Flagged files",
  view: "View",
  return: "Return…",
  close: "Close",
  helpful: "Helpful",
  notHelpful: "Not helpful",
} as const satisfies {
  title: string;
  verdict: Record<ScreeningVerdict, string>;
  questions: Record<string, string>;
  flaggedFiles: string;
  view: string;
  return: string;
  close: string;
  helpful: string;
  notHelpful: string;
};

export interface ScreeningCheck {
  key: string;
  question: string;
  verdict: ScreeningCheckVerdict;
  /** The answer line; null draws none. */
  answer: ReactNode;
}

export interface ScreeningFlaggedFile {
  id: string;
  name: string;
  /** Why the file is flagged: verified text the host renders (AgentText). */
  reason?: ReactNode;
  onView?: () => void;
  onReturn?: () => void;
  /** View or Return… held off, with a hint (a planned target, a missing right). */
  viewDisabled?: boolean;
  returnDisabled?: boolean;
}

export interface ScreeningAction {
  label: string;
  onClick?: () => void;
  icon?: IconName;
  disabled?: boolean;
  /** Why it is disabled, or what it opens. */
  hint?: string;
  /** The label opens a dialog or sheet ("Link to request…"). */
  opensDialog?: boolean;
}

export interface ScreeningCardProps {
  verdict: ScreeningVerdict;
  /** "Sep 26, 10:12 AM": when the batch was screened (not the clock). */
  time?: string | null;
  /** "Screening 2 new files…": a rerun in flight. */
  running?: string | null;
  /** The aggregate is still loading: the running skeleton with no words yet. */
  loading?: boolean;
  /** "Support for 40 subsequent disbursements (SURL) · expected period Jun 1 – Sep 18, 2026" */
  request?: string | null;
  checks: readonly ScreeningCheck[];
  /** d: "40 of 40 payments supported" */
  summary?: string | null;
  /** e: the one line that stands in for the checks. */
  notScreened?: string | null;
  flagged?: readonly ScreeningFlaggedFile[];
  primary?: ScreeningAction;
  secondary?: ScreeningAction;
  /** The thumbs (and the "Why?" menu): the host's, since feedback is a write. */
  feedback?: ReactNode;
  /** "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never
   * followed", and after feedback " · Feedback sent · Wrong request match". */
  provenance?: string | null;
  onClose?: () => void;
  className?: string;
}

const VERDICT_INK: Record<ScreeningVerdict, string> = {
  passed: "text-green-ink",
  flagged: "text-amber-ink",
  not_screened: "text-ink-3",
};

function VerdictGlyph({ verdict }: { verdict: ScreeningVerdict }): JSX.Element {
  if (verdict === "passed") return <StatusDisc state="done" size={13} />;
  if (verdict === "flagged")
    return <Icon name="triangle-alert" size={13} className="shrink-0 text-amber" />;
  return <StatusDisc state="todo" size={13} />;
}

function CheckGlyph({ verdict }: { verdict: ScreeningCheckVerdict }): JSX.Element {
  if (verdict === "pass") return <StatusDisc state="done" size={15} />;
  if (verdict === "flag")
    return (
      <Icon name="triangle-alert" size={15} label="Flagged" className="shrink-0 text-amber" />
    );
  return <StatusDisc state="todo" size={15} />;
}

function ActionButton({
  action,
  variant,
  locked,
}: {
  action: ScreeningAction;
  variant: "primary" | "secondary";
  locked: boolean;
}): JSX.Element {
  return (
    <Button
      variant={variant}
      size="md"
      {...(action.icon === undefined ? {} : { icon: action.icon })}
      disabled={locked || action.disabled === true}
      {...(action.hint === undefined ? {} : { title: action.hint })}
      opensDialog={action.opensDialog === true}
      onClick={action.onClick}
    >
      {action.label}
    </Button>
  );
}

/** The C-34 ScreeningCard, 420 wide. */
export function ScreeningCard({
  verdict,
  time,
  running,
  loading = false,
  request,
  checks,
  summary,
  notScreened,
  flagged = [],
  primary,
  secondary,
  feedback,
  provenance,
  onClose,
  className,
}: ScreeningCardProps): JSX.Element {
  const busy = loading || (running != null && running !== "");
  return (
    <section
      data-screening-card={busy ? "running" : verdict}
      aria-label={SCREENING_LABELS.title}
      aria-busy={busy || undefined}
      className={cn(
        "flex w-[420px] flex-col overflow-hidden rounded-pane bg-card shadow-pop",
        className,
      )}
    >
      <header className="flex h-[44px] flex-none items-center gap-[8px] pr-[8px] pl-[14px] hairline-b">
        <Icon name="atom" size={13} className="shrink-0 text-ink-2" />
        <h3 className="text-section font-medium">{SCREENING_LABELS.title}</h3>
        {time != null && time !== "" && <span className="text-meta text-ink-3">{time}</span>}
        <span className="ml-auto flex items-center gap-[6px]" aria-live="polite">
          {busy ? (
            <>
              <Ring size={13} width={1.4} track="stroke-rule" className="text-ink-2" />
              {running != null && running !== "" && (
                <span className="text-meta text-ink-2">{running}</span>
              )}
            </>
          ) : (
            <>
              <VerdictGlyph verdict={verdict} />
              <span
                data-verdict={verdict}
                className={cn("text-meta font-medium", VERDICT_INK[verdict])}
              >
                {SCREENING_LABELS.verdict[verdict]}
              </span>
            </>
          )}
        </span>
        {onClose !== undefined && (
          <button
            type="button"
            aria-label={SCREENING_LABELS.close}
            onClick={onClose}
            className="ml-[4px] inline-flex size-[26px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
          >
            <Icon name="x" size={13} />
          </button>
        )}
      </header>
      {request != null && request !== "" && (
        <p className="px-[14px] pt-[8px] text-cell text-ink-3">{request}</p>
      )}
      {notScreened != null && notScreened !== "" ? (
        <p className="px-[14px] py-[10px] text-dense text-ink-2 hairline-b">{notScreened}</p>
      ) : (
        <ul className="flex flex-col">
          {checks.map((c) => (
            <li
              key={c.key}
              data-check={c.key}
              data-check-verdict={busy ? "running" : c.verdict}
              className="flex gap-[10px] px-[14px] py-[10px] hairline-b"
            >
              <span className="pt-[1px]">
                {busy ? <StatusDisc state="todo" size={15} /> : <CheckGlyph verdict={c.verdict} />}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-[4px]">
                <span className="text-dense font-medium text-ink">{c.question}</span>
                {busy ? (
                  <Skeleton
                    immediate
                    style={{ width: c.key === checks[0]?.key ? "62%" : "38%" }}
                    className="h-[9px]"
                  />
                ) : (
                  c.answer != null && (
                    <span className="text-dense leading-[1.5] text-ink-2">{c.answer}</span>
                  )
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {summary != null && summary !== "" && !busy && (
        <p
          data-screening-summary=""
          className="px-[14px] py-[8px] text-cell text-ink-2 hairline-b"
        >
          {summary}
        </p>
      )}
      {flagged.length > 0 && !busy && (
        <section aria-label={SCREENING_LABELS.flaggedFiles} className="flex flex-col">
          <h4 className="flex h-[31px] items-center gap-[6px] bg-band-hd px-[14px] text-body font-medium">
            {SCREENING_LABELS.flaggedFiles}
            <Count value={flagged.length} />
          </h4>
          <ul className="flex flex-col">
            {flagged.map((f) => (
              <li
                key={f.id}
                data-flagged-file={f.id}
                className="flex gap-[8px] py-[9px] pr-[12px] pl-[14px] hairline-t"
              >
                <Icon name="file-text" size={14} className="mt-[1px] shrink-0 text-ink-3" />
                <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <span className="text-dense font-medium [overflow-wrap:anywhere]">{f.name}</span>
                  {f.reason != null && (
                    <span className="text-cell leading-[1.45] text-ink-2">{f.reason}</span>
                  )}
                </span>
                <span className="flex shrink-0 items-start gap-[4px]">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={f.onView === undefined || f.viewDisabled === true}
                    onClick={f.onView}
                    aria-label={`${SCREENING_LABELS.view} ${f.name}`}
                  >
                    {SCREENING_LABELS.view}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="undo-2"
                    opensDialog
                    disabled={f.onReturn === undefined || f.returnDisabled === true}
                    onClick={f.onReturn}
                    aria-label={`${SCREENING_LABELS.return} ${f.name}`}
                  >
                    {SCREENING_LABELS.return}
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {(primary !== undefined || secondary !== undefined || feedback !== undefined) && (
        <footer className="flex items-center gap-[8px] px-[12px] py-[10px] hairline-t">
          {primary !== undefined && (
            <ActionButton action={primary} variant="primary" locked={busy} />
          )}
          {secondary !== undefined && (
            <ActionButton action={secondary} variant="secondary" locked={busy} />
          )}
          {feedback !== undefined && (
            <span className="ml-auto flex items-center gap-[2px]">{feedback}</span>
          )}
        </footer>
      )}
      {provenance != null && provenance !== "" && (
        <p data-provenance="" className="px-[14px] pb-[12px] text-meta text-ink-3">
          {provenance}
        </p>
      )}
    </section>
  );
}
