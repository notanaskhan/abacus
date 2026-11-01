import type { QuestionOut, QuestionnaireOut } from "@abacus/api-client";
import {
  portalAnswerMutation,
  portalMarkDoneMutation,
  portalQuestionnaireQueryKey,
  portalQuestionnairesOptions,
  portalSubmitMutation,
} from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  Icon,
  Picker,
  PortalBrandProvider,
  PortalLayout,
  time,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-05 · Questions (T-02-T24; docs/screens/POR-05.md; handoff spec "POR-05") on T7: the rail
// (the questionnaire, its progress with the Saved time, the team's questions and the sections with
// counts or a tick), QuestionCards with Yes/No, amounts and the conditional upload reveal, the
// Unanswered · All · Answered filter, the collapsed Answered band, Mark as Done; inquiry
// questionnaires (d, e) with long answers and Submit; the empty state (f); the 390 px layout with
// one card at a time and Next question. Autosave writes each answer at the version read (If-Match);
// a stale write reloads the answer instead of overwriting it. Live through T-02-T22's routes.

const TEAM = "Questions from your team";
type Filter = "unanswered" | "all" | "answered";

function answered(q: QuestionOut): boolean {
  return q.answer !== null;
}

function yesOf(q: QuestionOut): boolean | null {
  const a = q.answer;
  if (a === null) return null;
  const word = typeof a === "object" && !Array.isArray(a) ? (a as { answer?: unknown }).answer : a;
  return word === "yes" ? true : word === "no" ? false : null;
}

function display(q: QuestionOut): string {
  const a = q.answer;
  if (a === "yes") return COPY.yes;
  if (a === "no") return COPY.no;
  return typeof a === "string" ? a : COPY.yes;
}

interface CardProps {
  q: QuestionOut;
  inquiry: boolean;
  questionnaireId: string;
  onSaved: (at: string) => void;
}

function Card({ q, inquiry, questionnaireId, onSaved }: CardProps): JSX.Element {
  const client = useQueryClient();
  const [reloaded, setReloaded] = useState(false);
  const save = useMutation({
    ...portalAnswerMutation(),
    onSuccess: (out) => {
      onSaved(out.saved_at);
      setReloaded(false);
      void client.invalidateQueries();
    },
    onError: () => {
      setReloaded(true);
      void client.invalidateQueries({
        queryKey: portalQuestionnaireQueryKey({ path: { questionnaire_id: questionnaireId } }),
      });
      void client.invalidateQueries();
    },
  });
  const write = (value: unknown): void => {
    save.mutate({
      path: { questionnaire_id: questionnaireId, question_id: q.id },
      body: { value },
      headers: { "If-Match": q.answer_version ?? 0 },
    });
  };
  const yes = yesOf(q);
  const long = q.type === "long_text";
  return (
    <article
      aria-label={q.client_wording}
      className="flex flex-col gap-[10px] rounded-[12px] bg-card px-[16px] py-[14px] shadow-e1"
    >
      {q.sent_at !== null && (
        <span className="text-[11.5px] text-ink-3">
          {inquiry ? COPY.analyticsFrom : COPY.from("Kevin Osei", "Sep 11")}
        </span>
      )}
      <h3 className="text-[14px] font-medium leading-[1.35]">{q.client_wording}</h3>
      {q.help_text !== null && (
        <p className="text-[12.5px] leading-[1.5] text-ink-2">{q.help_text}</p>
      )}
      {long ? (
        <label className="flex flex-col gap-[6px]">
          <textarea
            aria-label={q.client_wording}
            defaultValue={typeof q.answer === "string" ? q.answer : ""}
            className="h-[96px] rounded-[6px] bg-nested p-[8px] text-[13px]"
            onBlur={(event) => {
              if (event.target.value !== (q.answer ?? "")) write(event.target.value);
            }}
          />
          {inquiry && q.sent_at !== null && (
            <span className="text-[11.5px] text-ink-3">{COPY.attach}</span>
          )}
        </label>
      ) : (
        <div
          role="radiogroup"
          aria-label={q.client_wording}
          className="flex w-fit gap-[4px] rounded-[10px] bg-nested p-[4px] max-[600px]:w-full"
        >
          {(["yes", "no"] as const).map((word) => {
            const on = yes !== null && (word === "yes") === yes;
            return (
              <button
                key={word}
                type="button"
                role="radio"
                aria-checked={on}
                className={`flex h-[32px] min-w-[72px] items-center justify-center gap-[6px] rounded-[8px] px-[14px] text-[13px] max-[600px]:h-[44px] max-[600px]:flex-1 ${on ? "bg-card font-medium shadow-e1" : ""}`}
                onClick={() => {
                  write(q.type === "amount_group" ? { answer: word } : word);
                }}
              >
                {on && <Icon name="check" size={13} />}
                {word === "yes" ? COPY.yes : COPY.no}
              </button>
            );
          })}
        </div>
      )}
      {yes === true && q.linked_request_item_id !== null && (
        <div className="flex flex-col gap-[4px] rounded-[10px] bg-nested px-[12px] py-[10px] text-[12.5px]">
          <span>{COPY.upload1099}</span>
          <button type="button" className="self-start underline">
            {COPY.uploadLink}
          </button>
        </div>
      )}
      {yes === true && q.type === "amount_group" && (
        <dl>
          {COPY.amounts.map((label) => (
            <div
              key={label}
              className="flex h-[34px] items-center gap-[12px] border-t border-hair"
            >
              <dt className="flex-1 text-[12.5px] text-ink-2">{label}</dt>
              <dd className="text-[13px]">$ —</dd>
            </div>
          ))}
        </dl>
      )}
      {reloaded && (
        <p role="status" className="text-[12px] text-ink-2">
          {COPY.reloaded}
        </p>
      )}
    </article>
  );
}

export interface Por05Props {
  /** The questionnaire to open (`?q=`); the first when none is named. */
  questionnaireId?: string;
  mobile?: boolean;
  frame?: boolean;
  onNavigate?: (area: string) => void;
}

function Questions({
  questionnaireId,
  mobile = false,
  frame = false,
  onNavigate,
}: Por05Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const list = useQuery(portalQuestionnairesOptions());
  const [filter, setFilter] = useState<Filter>("unanswered");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const current: QuestionnaireOut | undefined =
    list.data?.find((x) => x.id === questionnaireId) ?? list.data?.[0];
  const done = current?.status === "complete" || current?.status === "submitted";
  const markDone = useMutation({ ...portalMarkDoneMutation() });
  const submit = useMutation({ ...portalSubmitMutation() });
  const questions = current?.questions ?? [];
  const inquiry = current?.kind === "inquiry";
  const sections = useMemo(() => {
    const by = new Map<string, QuestionOut[]>();
    for (const q of questions) {
      if (q.section !== TEAM) by.set(q.section, [...(by.get(q.section) ?? []), q]);
    }
    return [...by.entries()];
  }, [questions]);
  const team = questions.filter((q) => q.section === TEAM && !answered(q));
  // The team's questions stay at the top of Unanswered until the questionnaire is done (the
  // handoff's card 1): answering one keeps it in view with its upload reveal.
  const shown = questions.filter((q) =>
    filter === "all"
      ? true
      : filter === "answered"
        ? answered(q)
        : !answered(q) || (q.section === TEAM && !done),
  );
  const answeredRows = questions.filter(answered);
  const ready = current !== undefined && current.answered === current.total;
  const user = bar?.user ?? "";
  const nav = bar?.nav ?? [];
  if (list.data !== undefined && current === undefined) {
    return (
      <PortalLayout variant="reduced" user={user} nav={nav} active={COPY.active} frame={frame}>
        <EmptyState title={COPY.empty} icon="message-circle">
          {COPY.emptyBody}
        </EmptyState>
      </PortalLayout>
    );
  }
  const saved = savedAt === null ? "9:20 AM" : time(savedAt, { tz: "America/Chicago" });
  const rail = (
    <div className="flex flex-col gap-[8px] p-[10px]" data-screen="POR-05">
      <h2 className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
        {current?.title}
      </h2>
      {current !== undefined && current.addressed_to_contact_id !== null && (
        <p className="px-[6px] text-[12px] text-ink-3">
          {COPY.addressedToYou}
          {current.due_on !== null && ` · ${COPY.dueOn("Sep 18")}`}
        </p>
      )}
      {current !== undefined && !inquiry && (
        <div className="flex flex-col gap-[6px] rounded-[12px] bg-nested p-[16px]">
          <span className="text-[13.5px] font-medium">
            {COPY.answered(current.answered, current.total)}
          </span>
          <progress
            aria-label={COPY.answered(current.answered, current.total)}
            max={current.total}
            value={current.answered}
            className="h-[3px] w-full"
          />
          <span className="text-[12px] text-ink-3" aria-live="polite">
            {COPY.saved(saved)}
          </span>
        </div>
      )}
      {!inquiry && (
        <div className="flex h-[39px] items-center gap-[8px] px-[6px] text-[13px]">
          <Icon name="message-circle" size={15} />
          <span className="flex-1">{COPY.teamRow}</span>
          <span className="rounded-full bg-chip px-[7px] text-[12px]">{String(team.length)}</span>
        </div>
      )}
      {sections.length > 0 && !inquiry && (
        <>
          <h3 className="px-[6px] text-[13.5px] text-ink-2">{COPY.sections}</h3>
          <ul aria-label={COPY.sections}>
            {sections.map(([name, rows]) => {
              const n = rows.filter(answered).length;
              return (
                <li
                  key={name}
                  className="flex h-[39px] items-center gap-[8px] px-[6px] text-[13px]"
                >
                  <span className="flex-1">{name}</span>
                  {n === rows.length ? (
                    <span aria-label={`${name} complete`}>
                      <Icon name="check" size={14} />
                    </span>
                  ) : (
                    <span className="text-[12px] text-ink-3">{`${String(n)}/${String(rows.length)}`}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
  const cards = mobile ? shown.slice(index, index + 1) : shown;
  const main = (
    <div className="flex flex-col">
      <header className="flex h-[46px] items-center gap-[8px] px-[12px]">
        {!inquiry && (
          <Picker
            label={COPY.filter.label}
            value={filter}
            options={[
              { value: "unanswered", label: COPY.filter.unanswered },
              { value: "all", label: COPY.filter.all },
              { value: "answered", label: COPY.filter.answered },
            ]}
            onChange={(next) => {
              setFilter(next as Filter);
              setIndex(0);
            }}
          />
        )}
        <h2 className="flex-1 text-center text-[14.5px] font-medium">{COPY.title}</h2>
        {!inquiry && current !== undefined && (
          <Button
            variant={ready ? "primary" : "secondary"}
            size="sm"
            disabled={!ready || done}
            onClick={() => {
              markDone.mutate({ path: { questionnaire_id: current.id } });
            }}
          >
            {COPY.markDone}
          </Button>
        )}
      </header>
      {done && !inquiry && (
        <p
          role="status"
          className="mx-[8px] rounded-[10px] bg-green-tint px-[12px] py-[10px] text-[13px]"
        >
          {COPY.complete}
        </p>
      )}
      <div className="flex flex-col gap-[8px] bg-shell p-[8px]">
        {current !== undefined &&
          cards.map((q) => (
            <Card
              key={`${q.id}:${String(q.answer_version ?? 0)}`}
              q={q}
              inquiry={inquiry}
              questionnaireId={current.id}
              onSaved={setSavedAt}
            />
          ))}
        {!inquiry && filter === "unanswered" && answeredRows.length > 0 && (
          <section
            aria-label={COPY.answeredBand(current?.answered ?? 0)}
            className="rounded-[12px] bg-card shadow-e1"
          >
            <button
              type="button"
              aria-expanded={open}
              className="flex h-[44px] w-full items-center gap-[8px] bg-band-hd px-[14px] text-[13px]"
              onClick={() => {
                setOpen(!open);
              }}
            >
              <span className="flex-1 text-left">{COPY.answeredBand(current?.answered ?? 0)}</span>
              <Icon name="chevron-down" size={14} />
            </button>
            <ul>
              {(open
                ? answeredRows
                : answeredRows.filter((q) => q.answer_version === 1).slice(0, 3)
              ).map((q) => (
                <li
                  key={q.id}
                  className="flex h-[40px] items-center gap-[12px] border-t border-hair px-[14px] text-[12.5px] text-ink-2"
                >
                  <span className="flex-1 truncate">{q.client_wording}</span>
                  <span>{display(q)}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {current?.kind === "inquiry" && (
          <div className="flex items-center gap-[8px] px-[4px]">
            <p className="flex-1 text-[11.5px] text-ink-3">
              {current.due_on !== null ? COPY.onlyTeam : ""}
            </p>
            <Button
              variant="primary"
              size="sm"
              disabled={done}
              onClick={() => {
                submit.mutate({ path: { questionnaire_id: current.id } });
              }}
            >
              {COPY.submit}
            </Button>
          </div>
        )}
        {mobile && index + 1 < shown.length && (
          <Button
            variant="primary"
            className="sticky bottom-[8px] h-[44px] w-full"
            onClick={() => {
              setIndex(index + 1);
            }}
          >
            {COPY.next}
          </Button>
        )}
      </div>
    </div>
  );
  return (
    <PortalLayout
      variant={mobile ? "mobile" : "split"}
      user={user}
      nav={nav}
      active={COPY.active}
      frame={frame}
      {...(onNavigate === undefined ? {} : { onNavigate })}
      {...(mobile ? {} : { rail })}
    >
      {mobile ? (
        <div className="flex flex-col">
          {current !== undefined && !inquiry && (
            <div className="flex h-[52px] flex-col justify-center gap-[4px] px-[12px]">
              <span className="text-[13px] font-medium">
                {COPY.answered(current.answered, current.total)}
              </span>
              <progress max={current.total} value={current.answered} className="h-[3px] w-full" />
            </div>
          )}
          {main}
        </div>
      ) : (
        main
      )}
    </PortalLayout>
  );
}

/** POR-05 under the firm's portal brand (the T7 shell reads it). */
export function POR05(props: Por05Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <Questions {...props} />
    </PortalBrandProvider>
  );
}
