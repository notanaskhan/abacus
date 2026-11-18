// POR-11 · Close requests and transaction questions (C-01-T41, DEC-5638; handoff POR-11 a, b, c;
// SPEC-655 AC-47, AC-52). Filled into C-01-T57's pre-window seams: `/documents?period=YYYY-MM`
// with `closes.portal_requests` on opens the close's binder (the binder list names each close
// binder's `close_id` and `period`) with the transaction questions first, then the close's
// requests in the C-16 Request kit (POR-03 on that binder). The client sees only questions
// addressed to a contact they hold, in the firm's wording with a code-built context line.
import type { PortalQuestionOut } from "@abacus/api-client";
import {
  portalCloseQuestionsOptions,
  portalCloseQuestionsQueryKey,
} from "@abacus/api-client/query";
import { Button, DEFAULT_TZ, Skeleton, StatusDisc, date, time } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, Suspense, lazy, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useBinders } from "../../domain/portal";
import { COPY as C } from "./copy";
import { QuestionSheet } from "./QuestionSheet";

// Lazy, so the request kit stays in POR-03's own chunk (the route budgets, F-05-T17).
const POR03 = lazy(async () => ({ default: (await import("../POR-03")).POR03 }));

export interface POR11Props {
  /** `YYYY-MM` from `/documents?period=`. */
  period: string;
  mobile?: boolean;
  /** Open this question's sheet on arrival (POR-11 b; POR-04 `?question=`). */
  questionId?: string;
  onNavigate?: (area: string) => void;
  /** The documents area the slot falls back to (rendered only where POR-11 is not built in). */
  children?: ReactNode;
}

function receipt(at: string, now: Date): string {
  return `${date(at, { tz: DEFAULT_TZ, now })}, ${time(at, { tz: DEFAULT_TZ })}`;
}

export function QuestionsCard({
  closeId,
  mobile = false,
  questionId,
}: {
  closeId: string;
  mobile?: boolean;
  questionId?: string | undefined;
}): JSX.Element | null {
  const qc = useQueryClient();
  const now = useNow();
  const path = { close_id: closeId };
  const q = useQuery(portalCloseQuestionsOptions({ path }));
  const [open, setOpen] = useState<string | undefined>(questionId);
  if (q.data === undefined) return null;
  const items = q.data.items.filter((x) => x.status !== "withdrawn");
  if (items.length === 0) return null;
  const openOnes = items.filter((x) => x.status === "open");
  // Answered rows sit at the bottom of the card (POR-11 c).
  const ordered = [...openOnes, ...items.filter((x) => x.status === "answered")];
  const sheet = items.find((x) => x.question_id === open && x.status === "open");
  const answered = (row: PortalQuestionOut): void => {
    qc.setQueryData(portalCloseQuestionsQueryKey({ path }), {
      items: q.data.items.map((x) => (x.question_id === row.question_id ? row : x)),
    });
    setOpen(undefined);
  };
  return (
    <section
      data-por11="questions"
      aria-label={C.questions(openOnes.length)}
      className="rounded-card bg-card shadow-e1"
    >
      <header className="flex h-[44px] items-center px-[14px] text-[13.5px] font-medium">
        {C.questions(openOnes.length)}
      </header>
      <ul>
        {ordered.map((x) => {
          const done = x.status === "answered";
          return (
            <li
              key={x.question_id}
              data-question={x.question_id}
              data-status={x.status}
              className="flex min-h-[56px] items-center gap-[10px] border-t border-hair px-[14px] py-[10px]"
            >
              <StatusDisc size={13} state={done ? "done" : "todo"} />
              <div className="min-w-0 flex-1">
                <p className={done ? "text-[13.5px] text-ink-2" : "text-[13.5px] font-medium"}>
                  {x.client_wording}
                </p>
                {done && x.answered_at ? (
                  <p className="text-[12.5px] font-medium text-green-ink">
                    {C.answered(receipt(x.answered_at, now))}
                  </p>
                ) : (
                  <p className="text-[12.5px] text-ink-2">{x.context_line}</p>
                )}
              </div>
              {done ? null : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setOpen(x.question_id);
                  }}
                >
                  {mobile ? C.answerMobile : C.answer}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
      {sheet ? (
        <QuestionSheet
          question={sheet}
          onAnswered={answered}
          onClose={() => {
            setOpen(undefined);
          }}
        />
      ) : null}
    </section>
  );
}

export function POR11({
  period,
  mobile = false,
  questionId,
  onNavigate,
}: POR11Props): JSX.Element {
  const binders = useBinders(null);
  if (binders.data === undefined)
    return <Skeleton aria-label={C.loading} className="h-[604px] w-full" />;
  const binder = binders.data.items.find((b) => b.period === period);
  return (
    <div data-screen="POR-11" className="flex min-h-0 flex-1 flex-col gap-[8px]">
      {binder?.close_id ? (
        <div className="px-[12px] pt-[8px]">
          <QuestionsCard closeId={binder.close_id} mobile={mobile} questionId={questionId} />
        </div>
      ) : null}
      <Suspense fallback={<Skeleton aria-label={C.loading} className="h-[604px] w-full" />}>
        <POR03
          {...(binder ? { binderId: binder.id } : {})}
          mobile={mobile}
          {...(onNavigate ? { onNavigate } : {})}
        />
      </Suspense>
    </div>
  );
}
