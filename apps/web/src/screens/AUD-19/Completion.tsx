import type {
  AuditCompletionItemOut,
  AuditCompletionOut,
  GoingConcernOut,
  LegalLetterOut,
  SubsequentEventsOut,
} from "@abacus/api-client";
import {
  auditCompletionOptions,
  auditGoingConcernOptions,
  legalLettersOptions,
  subsequentEventsOptions,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  type DiscState,
  type ViewState,
  Button,
  Icon,
  PaneAction,
  Pill,
  Segmented,
  StatusDisc,
  cn,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { COPY } from "./copy";

// AUD-19 · Completion (A-07-T25; A-07 F2; SPEC-644; the handoff spec) on T2: the Completion
// Checklist canvas in the cockpit, the Agent dock the cockpit's (runs #4231 and #4240 as SHL-13 tool
// cards). Counts, blockers and every item's status are the projector's (A-07-T22): the summary
// reads "12 of 17" with N/A excluded because the server excludes it. The agent marks nothing
// complete (INV-1); the going-concern card is the Engagement Partner's and reads only here.
// Item titles and evidence are the firm template's words (database content).

export const COMPLETION_CHECKLIST = "completion_checklist";
export type CompletionTab = keyof typeof COPY.tabs;
const TABS: readonly CompletionTab[] = [
  "checklist",
  "subsequent_events",
  "legal_letters",
  "going_concern",
];
const DISC: Record<AuditCompletionItemOut["status"], DiscState> = {
  done: "done",
  partial: "half",
  open: "todo",
  not_applicable: "off",
};

export interface CompletionOptions {
  active?: boolean;
  tab?: CompletionTab;
  onTab?: (tab: CompletionTab) => void;
  /** "Sign off…": SHL-12 (manager L3 on the checklist; partner L4 required). */
  onSignOff?: () => void;
  /** A blocker or checklist link chip: the screen that clears it (AUD-21, AUD-20, EBP-07 …). */
  onLink?: (target: string) => void;
  /** "Request a legal letter…": SHL-14's third-party request. */
  onRequestLegalLetter?: () => void;
}

function LinkChip({
  target,
  onLink,
}: {
  target: string;
  onLink?: (target: string) => void;
}): JSX.Element {
  return (
    <button
      type="button"
      data-link={target}
      className="rounded-full bg-nested px-[8px] text-[11px] leading-[20px] text-ink-2 inset-shadow-hair"
      onClick={() => {
        onLink?.(target);
      }}
    >
      {target}
    </button>
  );
}

function Blockers({
  view,
  date,
  onLink,
}: {
  view: AuditCompletionOut;
  date: (iso: string) => string;
  onLink?: (target: string) => void;
}): JSX.Element {
  if (view.blockers.length === 0) {
    return (
      <button
        type="button"
        data-aud19="clear"
        className="mx-[14px] flex h-[36px] items-center rounded-[10px] bg-green-tint px-[12px] text-left text-[12.5px] text-green-ink"
        onClick={() => {
          onLink?.("AUD-24");
        }}
      >
        {COPY.blockers.clear}
      </button>
    );
  }
  const byKey = new Map(view.items.map((i) => [i.item_key, i]));
  return (
    <section data-aud19="blockers" className="mx-[14px] rounded-[10px] bg-card shadow-e1">
      <h4 className="flex h-[36px] items-center gap-[6px] px-[12px] text-[13.5px] font-medium hairline-b">
        <Icon name="triangle-alert" size={14} className="text-amber" />
        {COPY.blockers.title}
      </h4>
      {view.blockers.map((key) => {
        const item = byKey.get(key);
        if (item === undefined) return null;
        return (
          <div
            key={key}
            data-blocker={key}
            className="flex h-[34px] items-center justify-between gap-[8px] px-[12px] text-[12.5px] hairline-b last:shadow-none"
          >
            <span className="flex min-w-0 items-center gap-[6px]">
              <span className="truncate">{item.blocker_text ?? item.title}</span>
              {item.gate_tag != null && (
                <Pill size="chip" variant="tag">
                  {item.gate_tag}
                </Pill>
              )}
            </span>
            {item.link_target != null ? (
              <LinkChip target={item.link_target} {...(onLink === undefined ? {} : { onLink })} />
            ) : item.due_on != null ? (
              <span className="text-[11.5px] text-ink-3">{date(item.due_on)}</span>
            ) : null}
          </div>
        );
      })}
    </section>
  );
}

function Checklist({
  view,
  date,
  onLink,
}: {
  view: AuditCompletionOut;
  date: (iso: string) => string;
  onLink?: (target: string) => void;
}): JSX.Element {
  const linkProps = onLink === undefined ? {} : { onLink };
  return (
    <>
      <div
        data-aud19="summary"
        className="flex items-center justify-between px-[14px] py-[10px] text-[12.5px]"
      >
        <span className="flex items-center gap-[6px]">
          <Pill size="chip" variant="green-tint">
            {COPY.summary.complete(view.complete)}
          </Pill>
          <Pill size="chip" variant="neutral">
            {COPY.summary.notApplicable(view.not_applicable)}
          </Pill>
          {view.open > 0 && (
            <Pill size="chip" variant="amber">
              {COPY.summary.open(view.open)}
            </Pill>
          )}
        </span>
        <span data-aud19="of" className="text-ink-3 tabular-nums">
          {COPY.summary.of(view.complete, view.total)}
        </span>
      </div>
      <Blockers view={view} date={date} {...linkProps} />
      <table data-aud19="checklist" className="mt-[10px] w-full bg-card">
        <tbody>
          {view.items.map((item) => {
            const na = item.status === "not_applicable";
            return (
              <tr
                key={item.item_key}
                data-item={item.item_key}
                data-status={item.status}
                className={cn("h-[36px] hairline-t", na && "text-ink-3")}
              >
                <td className="w-[28px] pl-[14px] text-[11.5px] text-ink-3 tabular-nums">
                  {item.position}
                </td>
                <td className="w-[24px]">
                  <StatusDisc state={DISC[item.status]} size={15} />
                </td>
                <td className="py-[4px] pr-[8px]">
                  <div className="text-[12.5px]">{item.title}</div>
                  {item.evidence_text != null && (
                    <div className="text-[11.5px] text-ink-3">{item.evidence_text}</div>
                  )}
                </td>
                <td className="pr-[14px] text-right">
                  {item.link_target != null && (
                    <LinkChip target={item.link_target} {...linkProps} />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

function SubsequentEvents({
  view,
  date,
}: {
  view: SubsequentEventsOut;
  date: (iso: string) => string;
}): JSX.Element {
  const c = COPY.subsequent.columns;
  return (
    <div className="flex flex-col gap-[10px] p-[14px]">
      <section data-aud19="procedures" className="rounded-[10px] bg-card shadow-e1">
        <h4 className="flex h-[36px] items-center px-[12px] text-[13.5px] font-medium hairline-b">
          {COPY.subsequent.procedures}
        </h4>
        {view.procedures.map((p) => (
          <div
            key={p.id}
            data-procedure={p.procedure_key}
            data-status={p.status}
            className="flex h-[34px] items-center gap-[8px] px-[12px] text-[12.5px] hairline-b"
          >
            <StatusDisc state={p.status === "performed" ? "done" : "todo"} size={15} />
            <span className="flex-1">{p.title}</span>
            {p.status === "open" && view.report_date != null && (
              <span className="text-[11.5px] text-ink-3">{date(view.report_date)}</span>
            )}
          </div>
        ))}
      </section>
      <section data-aud19="events" className="rounded-[10px] bg-card shadow-e1">
        <h4 className="flex h-[36px] items-center px-[12px] text-[13.5px] font-medium hairline-b">
          {COPY.subsequent.events}
        </h4>
        <table className="w-full">
          <thead>
            <tr className="h-[30px] text-[11.5px] text-ink-3">
              {[c.event, c.type, c.effect, c.disclosure].map((h) => (
                <th key={h} className="px-[12px] text-left font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.events.map((e) => (
              <tr
                key={e.id}
                data-event={e.id}
                data-recognition={e.recognition}
                className="text-[12px] hairline-t"
              >
                <td className="px-[12px] py-[6px]">{e.description}</td>
                <td className="px-[12px]">{COPY.subsequent.recognition[e.recognition]}</td>
                <td className="px-[12px]">{e.fs_effect ?? ""}</td>
                <td className="px-[12px] whitespace-nowrap">
                  {e.note_ref ?? ""} <span className="text-green">✓</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function LegalLetters({
  view,
  onRequest,
}: {
  view: LegalLetterOut;
  onRequest?: () => void;
}): JSX.Element {
  const canRequest = view.allowed_actions.includes("legal_letter.request");
  return (
    <section
      data-aud19="legal"
      data-status={view.status ?? undefined}
      className="m-[14px] flex flex-col items-center gap-[8px] rounded-[10px] bg-card px-[24px] py-[28px] text-center shadow-e1"
    >
      <span className="flex size-[34px] items-center justify-center rounded-[10px] bg-nested">
        <Icon name="file-text" size={17} className="text-ink-2" />
      </span>
      <h4 className="text-[13.5px] font-medium">
        {view.not_applicable ? COPY.legal.title : (view.status ?? "")}
      </h4>
      {view.basis != null && (
        <p className="max-w-[460px] text-[12.5px] text-ink-2">{view.basis}</p>
      )}
      <Button
        size="xs"
        variant="secondary"
        disabled={!canRequest}
        {...(onRequest === undefined ? {} : { onClick: onRequest })}
      >
        {COPY.legal.request}
      </Button>
    </section>
  );
}

function GoingConcern({
  view,
  date,
}: {
  view: GoingConcernOut;
  date: (iso: string) => string;
}): JSX.Element {
  const options = Object.keys(
    COPY.goingConcern.options,
  ) as (keyof typeof COPY.goingConcern.options)[];
  return (
    <section
      data-aud19="going-concern"
      data-state={view.state}
      aria-readonly="true"
      className="m-[14px] rounded-[12px] bg-card p-[14px] shadow-e1"
    >
      <p className="flex gap-[8px] text-[13px] font-medium">
        <span aria-hidden className="text-ink-3">
          ?
        </span>
        {view.subject === "entity" ? COPY.goingConcern.questionEntity : COPY.goingConcern.question}
      </p>
      <ol className="mt-[10px] flex flex-col gap-[6px]">
        {options.map((key) => {
          const chosen = view.conclusion === key;
          return (
            <li
              key={key}
              data-option={key}
              {...(chosen ? { "data-selected": "" } : {})}
              title={COPY.goingConcern.reserved}
              className={cn(
                "rounded-[10px] px-[12px] py-[8px] text-[12.5px]",
                chosen ? "bg-green-tint text-green-ink" : "bg-nested text-ink-2",
              )}
            >
              <div className={cn(chosen && "font-medium")}>{COPY.goingConcern.options[key]}</div>
              {chosen &&
                view.inputs.map((input, i) => (
                  <div key={i} className="mt-[2px] text-[11.5px]">
                    {input.label === "" ? input.value : `${input.label} ${input.value}`}
                  </div>
                ))}
            </li>
          );
        })}
      </ol>
      {view.decided_by_name != null && view.decided_at != null && (
        <p data-aud19="decided" className="mt-[10px] text-[11.5px] text-ink-3">
          {COPY.goingConcern.decided(view.decided_by_name, date(view.decided_at))}
        </p>
      )}
    </section>
  );
}

export function useCompletionCanvas(
  workItemId: string,
  options: CompletionOptions = {},
): CockpitCanvas {
  const fmt = useFormat();
  const date = (iso: string): string => fmt.date(iso);
  const tab = options.tab ?? "checklist";
  const on = options.active !== false;
  const path = { path: { work_item_id: workItemId } };
  const checklist = useQuery({ ...auditCompletionOptions(path), enabled: on, retry: false });
  const events = useQuery({
    ...subsequentEventsOptions(path),
    enabled: on && tab === "subsequent_events",
    retry: false,
  });
  const legal = useQuery({
    ...legalLettersOptions(path),
    enabled: on && tab === "legal_letters",
    retry: false,
  });
  const going = useQuery({
    ...auditGoingConcernOptions(path),
    enabled: on && tab === "going_concern",
    retry: false,
  });
  const query =
    tab === "checklist"
      ? checklist
      : tab === "subsequent_events"
        ? events
        : tab === "legal_letters"
          ? legal
          : going;
  let state: ViewState = { kind: "ready" };
  if (query.isError) {
    const code = (query.error as { status?: number } | null)?.status;
    state =
      code === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void query.refetch() };
  } else if (query.data === undefined) state = { kind: "loading" };
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const linkProps = options.onLink === undefined ? {} : { onLink: options.onLink };
  return {
    title: COPY.title,
    well: true,
    state,
    actions: (
      <>
        <PaneAction label={COPY.signOff} {...signOff} />
        <PaneAction icon="cloud-download" label={COPY.openInExcel} />
      </>
    ),
    controls: (
      <Segmented
        label={COPY.title}
        size="small"
        active={COPY.tabs[tab]}
        options={TABS.map((t) => COPY.tabs[t])}
        onChange={(label) => {
          const next = TABS.find((t) => COPY.tabs[t] === label);
          if (next !== undefined) options.onTab?.(next);
        }}
      />
    ),
    children: (
      <div data-screen="AUD-19" data-tab={tab} className="min-h-0 flex-1 overflow-y-auto">
        {tab === "checklist" && checklist.data !== undefined && (
          <Checklist view={checklist.data} date={date} {...linkProps} />
        )}
        {tab === "subsequent_events" && events.data !== undefined && (
          <SubsequentEvents view={events.data} date={date} />
        )}
        {tab === "legal_letters" && legal.data !== undefined && (
          <LegalLetters
            view={legal.data}
            {...(options.onRequestLegalLetter === undefined
              ? {}
              : { onRequest: options.onRequestLegalLetter })}
          />
        )}
        {tab === "going_concern" && going.data !== undefined && (
          <GoingConcern view={going.data} date={date} />
        )}
      </div>
    ),
  };
}
