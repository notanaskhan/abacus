import type {
  EditorQuestionOut,
  PreviewQuestionOut,
  QuestionnaireEditorOut,
} from "@abacus/api-client";
import { questionnaireEditorOptions, questionnairePreviewOptions } from "@abacus/api-client/query";
import {
  Button,
  type ClientQuestion,
  ClientQuestionPreview,
  EmptyState,
  Icon,
  Pill,
  Segmented,
  Toggle,
  ViewStateBody,
  type ViewState,
  cn,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// BND-03 · Questionnaire editor, read states a and e and the client preview dock (T-03-T09; T-03 §3
// F2; the handoff spec): the T2 frame (rail 330 · canvas 696 · dock 330) over
// `GET /v1/questionnaires/{id}/editor` (T-03-T05). The rail's KVs, section counts and Logic band are
// the server's counts; the canvas draws one QuestionCard per question (the selected section's
// expanded with its Required toggle, client wording, answer and follow-ups, the effect banner and
// helpers); an empty section shows its EmptyState. The dock renders `…/client-preview` (the portal
// DTO) through the client question renderer in `@abacus/ui`: no tag, banner, helper or toggle
// reaches it. Editing (b, c, d) is T-03-T10: the toggles and "+ Question" are read-only here.

export type BinderTab = "requests" | "questions" | "activity";

export interface EditorProps {
  questionnaireId: string;
  section?: string | null;
  onSection?: (key: string) => void;
  /** Requests and Activity return to the binder (BND-02). */
  onTab?: (tab: BinderTab, binderId: string) => void;
}

const PANE = "flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e2";
const HEAD =
  "flex h-[46px] shrink-0 items-center gap-[8px] px-[14px] text-[14.5px] font-medium hairline-b";
const BAND =
  "px-[14px] pt-[10px] pb-[4px] text-micro font-medium uppercase tracking-[.07em] text-ink-3";

function answerText(q: EditorQuestionOut, fmtDate: (iso: string) => string): string {
  const a = q.answer;
  if (a === null || a === undefined) return COPY.canvas.unanswered;
  const v = a.value;
  const text =
    typeof v === "string"
      ? v
      : typeof v === "boolean"
        ? v
          ? "Yes"
          : "No"
        : typeof v === "number"
          ? String(v)
          : Object.entries((v ?? {}) as Record<string, unknown>)
              .map(([k, x]) => `${k} ${String(x)}`)
              .join(" · ");
  return `${text} · ${fmtDate(a.answered_on)}`;
}

function Rail({
  data,
  selected,
  onSection,
}: {
  data: QuestionnaireEditorOut;
  selected: string;
  onSection: (key: string) => void;
}): JSX.Element {
  const fmt = useFormat();
  const c = data.counts;
  return (
    <aside data-bnd03="rail" className={cn(PANE, "w-[330px] shrink-0")}>
      <header className={HEAD}>
        <span className="flex-1">{COPY.rail.title}</span>
      </header>
      <dl className="flex flex-col px-[14px] py-[6px] text-dense">
        {data.template !== null && data.template !== undefined && (
          <div className="flex h-[34px] items-center justify-between hairline-b">
            <dt className="text-ink-3">{COPY.rail.template}</dt>
            <dd>{COPY.rail.templateValue(data.template.name, data.template.version)}</dd>
          </div>
        )}
        <div className="flex h-[34px] items-center justify-between" data-bnd03="answered">
          <dt className="text-ink-3">{COPY.rail.answered}</dt>
          <dd className="truncate">
            {COPY.rail.answeredValue(
              c.answered,
              c.questions,
              c.last_answer_by ?? null,
              c.last_answer_on === null || c.last_answer_on === undefined
                ? null
                : fmt.date(c.last_answer_on),
            )}
          </dd>
        </div>
      </dl>
      <p className={BAND}>{COPY.rail.sections}</p>
      <ul className="flex flex-col">
        {data.sections.map((s) => (
          <li key={s.key}>
            <button
              type="button"
              data-section={s.key}
              aria-current={s.key === selected ? "true" : undefined}
              className={cn(
                "flex h-[39px] w-full items-center justify-between px-[14px] text-left text-[13.5px]",
                s.key === selected ? "bg-sel-bg font-medium" : "hover:bg-tonal-hover",
              )}
              onClick={() => {
                onSection(s.key);
              }}
            >
              <span className="truncate">{s.title}</span>
              <Pill variant="neutral" size="count">
                {s.question_count}
              </Pill>
            </button>
          </li>
        ))}
      </ul>
      <p className={BAND}>{COPY.rail.logic}</p>
      <ul className="flex flex-col pb-[10px] text-[13.5px]">
        <li data-logic="follow-ups" className="flex h-[39px] items-center px-[14px]">
          {COPY.rail.followUps(c.conditional_follow_ups)}
        </li>
        <li
          data-logic="review-points"
          className="flex h-[39px] items-center justify-between px-[14px]"
        >
          {COPY.rail.reviewPoints(c.review_points_raised)}
          {c.review_points_raised > 0 && (
            <Pill variant="amber" size="count">
              {c.review_points_raised}
            </Pill>
          )}
        </li>
      </ul>
    </aside>
  );
}

function FollowUp({ q }: { q: EditorQuestionOut }): JSX.Element {
  const fmt = useFormat();
  const created = (q.effects ?? []).find((e) => e.kind === "request_item_created");
  return (
    <div
      data-follow-up={q.key}
      className="flex flex-col gap-[4px] bg-nested py-[6px] pr-[12px] pl-[24px]"
    >
      <div className="flex h-[30px] items-center gap-[8px] text-dense">
        <Icon name="corner-down-right" size={12} className="text-ink-3" />
        <span className="min-w-0 flex-1 truncate">{COPY.canvas.ifYes(q.client_wording)}</span>
        <Pill variant="tag" size="sm">
          {COPY.type[q.type] ?? q.type}
        </Pill>
        <Toggle checked={q.required} disabled label={COPY.canvas.required} size="small" />
      </div>
      <p className={cn("text-dense", q.triggered === false || !q.answered ? "text-ink-4" : "")}>
        {q.triggered === false ? COPY.canvas.notTriggered : answerText(q, (d) => fmt.date(d))}
      </p>
      {created !== undefined && !q.required && (
        <p data-helper="make-required" className="text-[11.5px] text-amber-ink">
          {COPY.canvas.makeRequired(created.title)}
        </p>
      )}
      {q.internal_helper !== null && q.internal_helper !== undefined && (
        <p data-helper="internal" className="text-[11.5px] text-ink-3">
          {q.internal_helper}
        </p>
      )}
    </div>
  );
}

function QuestionCard({
  q,
  followUps,
  expanded,
}: {
  q: EditorQuestionOut;
  followUps: readonly EditorQuestionOut[];
  expanded: boolean;
}): JSX.Element {
  const fmt = useFormat();
  const review = (q.effects ?? []).find((e) => e.kind === "review_point_raised");
  return (
    <article
      data-question={q.key}
      data-expanded={expanded ? "true" : "false"}
      className="flex flex-col overflow-hidden rounded-[10px] bg-card shadow-e1"
    >
      <header className="flex h-[38px] items-center gap-[8px] px-[12px]">
        <Icon name="grip-vertical" size={14} className="text-ink-4" />
        <span className="text-[12px] text-ink-3">{q.key.toUpperCase()}</span>
        <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium">
          {q.client_wording}
        </span>
        <Pill variant="tag" size="sm" data-type={q.type}>
          {COPY.type[q.type] ?? q.type}
        </Pill>
      </header>
      {expanded && (
        <dl className="flex flex-col px-[12px] text-dense">
          <div className="flex h-[34px] items-center justify-between hairline-t">
            <dt className="text-ink-3">{COPY.canvas.required}</dt>
            <dd>
              <Toggle checked={q.required} disabled label={COPY.canvas.required} />
            </dd>
          </div>
          <div className="flex min-h-[34px] items-center justify-between gap-[10px] hairline-t">
            <dt className="text-ink-3">{COPY.canvas.wording}</dt>
            <dd className="truncate text-[12.5px] text-ink-2">{q.client_wording}</dd>
          </div>
        </dl>
      )}
      <p
        data-answer
        className={cn(
          "flex h-[34px] items-center px-[12px] text-dense hairline-t",
          !q.answered && "text-ink-4",
        )}
      >
        {answerText(q, (d) => fmt.date(d))}
      </p>
      {review !== undefined && (
        <p
          data-banner="review-point"
          className="mx-[12px] mb-[8px] flex h-[32px] items-center gap-[6px] rounded-nested bg-amber-tint px-[8px] text-[12.5px] text-amber-ink"
        >
          <Icon name="triangle-alert" size={14} />
          {COPY.canvas.reviewPoint(review.title)}
        </p>
      )}
      {q.internal_helper !== null && q.internal_helper !== undefined && (
        <p data-helper="internal" className="px-[12px] pb-[8px] text-[11.5px] text-ink-3">
          {q.internal_helper}
        </p>
      )}
      {(expanded ? followUps : []).map((f) => (
        <FollowUp key={f.key} q={f} />
      ))}
    </article>
  );
}

function toClient(p: PreviewQuestionOut): ClientQuestion {
  return {
    key: p.key,
    wording: p.client_wording,
    type: p.type,
    required: p.required,
    answer: p.answer,
    ...(p.choices === undefined ? {} : { choices: p.choices }),
    ...(p.amount_parts === undefined ? {} : { amountParts: p.amount_parts }),
  };
}

function Dock({
  questionnaireId,
  keys,
  enabled,
}: {
  questionnaireId: string;
  keys: ReadonlySet<string>;
  enabled: boolean;
}): JSX.Element {
  const [size, setSize] = useState<"desktop" | "phone">("phone");
  const preview = useQuery({
    ...questionnairePreviewOptions({ path: { questionnaire_id: questionnaireId } }),
    enabled,
  });
  const items = (preview.data?.questions ?? []).filter((q) => q.visible);
  const top = items.filter((q) => (q.parent_key ?? null) === null && keys.has(q.key));
  return (
    <aside data-bnd03="dock" className={cn(PANE, "w-[330px] shrink-0")}>
      <header className={cn(HEAD, "justify-center")}>{COPY.dock.title}</header>
      <div className="flex justify-center py-[8px]">
        <Segmented
          size="small"
          label={COPY.dock.label}
          options={[COPY.dock.desktop, COPY.dock.phone]}
          active={size === "phone" ? COPY.dock.phone : COPY.dock.desktop}
          onChange={(label) => {
            setSize(label === COPY.dock.phone ? "phone" : "desktop");
          }}
        />
      </div>
      <div
        data-preview-size={size}
        className="flex min-h-0 flex-1 flex-col items-center gap-[10px] overflow-y-auto bg-shell p-[12px]"
      >
        {preview.data !== undefined && (
          <p className="flex w-full items-center gap-[6px] text-dense font-medium">
            <span aria-hidden className="size-[20px] rounded-[6px] bg-espresso" />
            {preview.data.firm_name}
          </p>
        )}
        {top.map((q) => (
          <ClientQuestionPreview
            key={q.key}
            question={toClient(q)}
            followUps={items.filter((f) => f.parent_key === q.key).map(toClient)}
            className={size === "phone" ? "w-[260px]" : "w-[300px]"}
          />
        ))}
      </div>
    </aside>
  );
}

export function QuestionnaireEditor({
  questionnaireId,
  section,
  onSection,
  onTab,
}: EditorProps): JSX.Element {
  const on = useFlag("questionnaires.editor") === true;
  const editor = useQuery({
    ...questionnaireEditorOptions({ path: { questionnaire_id: questionnaireId } }),
    enabled: on,
  });
  const data = editor.data;
  const [own, setOwn] = useState<string | null>(section ?? null);
  const selected = section ?? own ?? data?.sections[0]?.key ?? "";
  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "questionnaires.editor" };
  else if (editor.isError) {
    const status = (editor.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void editor.refetch() };
  } else if (data === undefined) state = { kind: "loading" };

  const questions = data?.questions ?? [];
  const top = questions.filter((q) => (q.parent_key ?? null) === null);
  const inSection = top.filter((q) => q.section_key === selected);
  return (
    <div data-screen="BND-03" className="flex min-h-0 flex-1 flex-col">
      <ViewStateBody state={state} empty={{ title: COPY.states.notFound }} noun="questionnaire">
        {() =>
          data === undefined ? null : (
            <>
              <div className="flex h-[42px] shrink-0 items-center justify-center text-[15px] font-medium">
                {data.title}
              </div>
              <div className="flex h-[50px] shrink-0 items-center justify-center">
                <Segmented
                  label={COPY.tabsLabel}
                  options={[
                    COPY.tabs.requests,
                    { label: COPY.tabs.questions, count: data.counts.questions },
                    COPY.tabs.activity,
                  ]}
                  active={COPY.tabs.questions}
                  onChange={(label) => {
                    const binder = data.binder_id ?? null;
                    if (binder === null) return;
                    if (label === COPY.tabs.requests) onTab?.("requests", binder);
                    if (label === COPY.tabs.activity) onTab?.("activity", binder);
                  }}
                />
              </div>
              <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pt-[10px] pb-[12px]">
                <Rail
                  data={data}
                  selected={selected}
                  onSection={(key) => {
                    setOwn(key);
                    onSection?.(key);
                  }}
                />
                <section data-bnd03="canvas" className={cn(PANE, "w-[696px] shrink-0")}>
                  <header className={HEAD}>
                    <span className="flex-1">{COPY.canvas.title}</span>
                    <Button variant="ghost" size="sm" disabled>
                      {COPY.canvas.reorder}
                    </Button>
                    <Button variant="secondary" size="sm" disabled>
                      {COPY.canvas.preview}
                    </Button>
                    <Button variant="primary" size="sm" disabled>
                      {COPY.canvas.add}
                    </Button>
                  </header>
                  <div className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto bg-shell p-[10px]">
                    {inSection.length === 0 ? (
                      <EmptyState icon="list" title={COPY.canvas.empty}>
                        <Button variant="secondary" size="sm" disabled>
                          {COPY.canvas.add}
                        </Button>
                      </EmptyState>
                    ) : (
                      top.map((q) => (
                        <QuestionCard
                          key={q.key}
                          q={q}
                          followUps={questions.filter((f) => f.parent_key === q.key)}
                          expanded={q.section_key === selected}
                        />
                      ))
                    )}
                  </div>
                </section>
                <Dock
                  questionnaireId={questionnaireId}
                  keys={new Set(inSection.map((q) => q.key))}
                  enabled={on}
                />
              </div>
            </>
          )
        }
      </ViewStateBody>
    </div>
  );
}
