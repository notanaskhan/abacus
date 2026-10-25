// SHL-20 ScreeningCardHost (P-06-T22; docs/screens/SHL-20.md): the C-34 card on a request's
// screening aggregate, with everything it opens. BND-02 (row glyph and dock) hosts it here; AUD-03
// (A-01) and CLS-03 (C-01) host the same component.
//
// - "View" opens SHL-08 on the flagged file with the flag's verified region lit (`region_ref` is
//   its citation), through `openSourceViewer`.
// - "Return…" opens the ReturnDialog with the flag's reason ("Wrong document") preselected; the
//   request is returned only when the person confirms.
// - "Draft follow-up" asks the platform for the template-composed return draft and opens the O3
//   sheet; only the person's "Send to …" sends it.
// - "Rerun" screens the current files again; the card polls every 2 s while it runs.
// - The thumbs record feedback; a thumbs down needs a reason.
// Nothing here accepts, returns or sends by itself, and nothing shows a confidence (P-06 §7).
// A flag's reason is the agent's verified text, so it renders through AgentText.

import type { CitationV2Out, FollowUpOut, ScreeningCardOut } from "@abacus/api-client";
import {
  AgentText,
  DEFAULT_TZ,
  type ScreeningCheck,
  ScreeningCard,
  type ScreeningFlaggedFile,
  SCREENING_LABELS,
  toast,
} from "@abacus/ui";
import { type JSX, useEffect, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenSourceViewer } from "../../app-core/overlay-host";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { ReturnDialog, type ReturnTarget } from "../requests/ReturnDialog";
import { ScreeningReturnSheet } from "../requests/ScreeningReturnSheet";
import { checkAnswer, newFiles, periodText, provenanceLine, screenedAt } from "./compose";
import { SCREENING_COPY } from "./copy";
import { FeedbackMenu } from "./FeedbackMenu";
import {
  type ScreeningSubjectRef,
  useFlagCitations,
  useScreeningCard,
  useScreeningWrites,
} from "./queries";

const PENDING_CHECKS: readonly ScreeningCheck[] = [
  {
    key: "right_document",
    question: SCREENING_LABELS.questions.right_document,
    verdict: "not_run",
    answer: null,
  },
  {
    key: "right_period",
    question: SCREENING_LABELS.questions.right_period,
    verdict: "not_run",
    answer: null,
  },
];

export interface ScreeningCardHostProps {
  /** The request whose batch is screened. */
  subject: ScreeningSubjectRef;
  onClose?: () => void;
  /** Open "Why?" (f) or the follow-up draft (b) as an artboard opens. */
  open?: "feedback" | "follow-up";
  className?: string;
}

function feedbackLine(card: ScreeningCardOut): string {
  const given = card.my_feedback;
  if (given === null) return provenanceLine(card);
  const said =
    given.reason_code === null
      ? SCREENING_COPY.feedback.sentUp
      : SCREENING_COPY.feedback.sent(SCREENING_COPY.feedback.reasons[given.reason_code]);
  return `${provenanceLine(card)} · ${said}`;
}

export function ScreeningCardHost({
  subject,
  onClose,
  open,
  className,
}: ScreeningCardHostProps): JSX.Element | null {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const query = useScreeningCard(subject);
  const writes = useScreeningWrites(subject);
  const openViewer = useOpenSourceViewer();
  const card = query.data;
  const flags = card?.file_flags ?? [];
  const citations = useFlagCitations(
    flags.flatMap((f) => (f.region_ref === null ? [] : [f.region_ref])),
  );
  const [returning, setReturning] = useState<ReturnTarget | null>(null);
  const [draft, setDraft] = useState<FollowUpOut | null>(null);
  const [asked, setAsked] = useState(false);

  const draftFollowUp = async (): Promise<void> => {
    try {
      setDraft(await writes.draftReturn(flags.map((f) => f.evidence_version_id)));
    } catch {
      toast.show({ kind: "error", text: SCREENING_COPY.sheet.failed });
    }
  };
  const ready = card !== undefined && flags.length > 0;
  useEffect(() => {
    if (open !== "follow-up" || asked || !ready) return;
    setAsked(true);
    void draftFollowUp();
  }, [open, asked, ready]);

  // Off (`screening.card`), walled or refused: the card area shows nothing extra.
  if (query.isError) return null;
  if (card === undefined) {
    return (
      <ScreeningCard
        verdict="not_screened"
        loading
        checks={PENDING_CHECKS}
        {...(onClose === undefined ? {} : { onClose })}
        {...(className === undefined ? {} : { className })}
      />
    );
  }

  const allowed = new Set(card.allowed_actions);
  const view = (
    citation: CitationV2Out | undefined,
    versionId: string,
  ): (() => void) | undefined =>
    citation === undefined || citation.match_id === null
      ? undefined
      : () => {
          openViewer({
            evidenceVersionId: citation.source.evidence_version_id ?? versionId,
            matchId: citation.match_id,
            engagementId: subject.engagementId,
          });
        };
  const flagged: ScreeningFlaggedFile[] = flags.map((f) => {
    const citation = f.region_ref === null ? undefined : citations[f.region_ref];
    const quote = citation?.verified === true ? citation.quote : null;
    const onView = view(citation, f.evidence_version_id);
    return {
      id: f.evidence_version_id,
      name: f.file_name,
      ...(quote === null
        ? {}
        : { reason: <AgentText inline text={quote} className="text-cell" /> }),
      ...(onView === undefined ? {} : { onView }),
      onReturn: () => {
        setReturning({
          engagementId: subject.engagementId,
          versionId: f.evidence_version_id,
          fileName: f.file_name,
          reason: f.reason_code,
        });
      },
    };
  });
  const checks: ScreeningCheck[] = card.checks.map((c) => ({
    key: c.key,
    question: SCREENING_LABELS.questions[c.key],
    verdict: c.verdict,
    answer: checkAnswer(c, card),
  }));
  const screened = card.screening_result_id !== null;
  const rerun = async (): Promise<void> => {
    try {
      await writes.rerun();
    } catch (error) {
      const detail = (error as { detail?: unknown } | null)?.detail;
      toast.show({
        kind: "error",
        text:
          detail === "screening_running" ? SCREENING_COPY.rerunBusy : SCREENING_COPY.rerunFailed,
      });
    }
  };
  const resultId = card.screening_result_id;

  return (
    <>
      <ScreeningCard
        verdict={card.verdict}
        time={screenedAt(card.provenance.screened_at, tz, now)}
        running={card.running ? SCREENING_COPY.running(newFiles(card)) : null}
        request={SCREENING_COPY.request(
          card.request_title,
          periodText(card.period_start, card.period_end),
        )}
        checks={checks}
        summary={
          card.verdict === "passed"
            ? SCREENING_COPY.passedTotal(card.files_answering, card.files_total)
            : null
        }
        flagged={flagged}
        {...(card.verdict === "flagged" && flags.length > 0
          ? {
              primary: {
                label: SCREENING_COPY.footer.draftFollowUp,
                onClick: () => void draftFollowUp(),
              },
            }
          : {})}
        {...(allowed.has("screening.request") || card.running
          ? {
              secondary: {
                label: screened ? SCREENING_COPY.footer.rerun : SCREENING_COPY.footer.screenNow,
                icon: "rotate-ccw" as const,
                disabled: writes.rerunning,
                onClick: () => void rerun(),
              },
            }
          : {})}
        {...(resultId !== null && allowed.has("screening.feedback")
          ? {
              feedback: (
                <FeedbackMenu
                  given={card.my_feedback}
                  openOnMount={open === "feedback"}
                  disabled={card.running}
                  onSend={(body) => writes.feedback(resultId, body)}
                />
              ),
            }
          : {})}
        provenance={screened ? feedbackLine(card) : null}
        {...(onClose === undefined ? {} : { onClose })}
        {...(className === undefined ? {} : { className })}
      />
      <ReturnDialog
        target={returning}
        onClose={() => {
          setReturning(null);
        }}
      />
      <ScreeningReturnSheet
        draft={draft}
        returning={flags.map((f) => f.file_name)}
        sending={writes.sending}
        onEdit={(body) => writes.edit(draft?.id ?? "", body)}
        onSend={() => writes.send(draft?.id ?? "")}
        onUndo={() => writes.undo(draft?.id ?? "")}
        onClose={() => {
          setDraft(null);
        }}
      />
    </>
  );
}

/** SHL-20 e: a file filed from the Inbox before it was linked to a request has no batch to
 * screen. "Link to request…" opens INB-02 (planned, DV-8); "Screen now" waits for the link. */
export function UnlinkedScreeningCard({
  onClose,
  className,
}: {
  onClose?: () => void;
  className?: string;
}): JSX.Element {
  return (
    <ScreeningCard
      verdict="not_screened"
      checks={[]}
      notScreened={SCREENING_COPY.notScreened.body}
      secondary={{ label: SCREENING_COPY.footer.screenNow, disabled: true }}
      {...(PLANNED_VISIBLE
        ? {
            primary: {
              label: SCREENING_COPY.footer.link,
              opensDialog: true,
              disabled: true,
              hint: SCREENING_COPY.footer.linkHint,
            },
          }
        : {})}
      {...(onClose === undefined ? {} : { onClose })}
      {...(className === undefined ? {} : { className })}
    />
  );
}
