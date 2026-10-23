import type { PortalHomeOut, PortalHomeTodoOut, PortalHomeWorkCardOut } from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  Icon,
  IconButton,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  ProgressBar,
  StatusDisc,
  StatusPill,
  EmptyState,
  count,
  date,
  usePortalBrand,
  weekdayDate,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import {
  brandOf,
  useBranding,
  useDismissWelcome,
  usePortalHome,
  usePortalToolbar,
} from "../../domain/portal";
import { COPY } from "./copy";

// POR-02 · Portal home, part 1 (P-08-T15; docs/screens/POR-02.md). T7 split over
// `GET /v1/portal/home` for the chosen scope: the rail (household card, team rows with their
// client-facing labels, the Recent messages band and "Account & people", both planned and drawn
// only in fixture builds), the greeting on `useNow`, the to-do cards from a kind registry, the
// work card with its StageTracker and note, the Documents binder card and the Earlier list. Each
// artboard is its data (fixtures/scenarios/POR-02.ts):
//
//   a  Claire Feld at E0: Upload 2, Answer 3, nothing to sign, 2 ready; the return at Review
//   b  her first visit (Mon Feb 2, 2026): the welcome card, 0 of 21, sign and upload to-dos
//   c  every open item done: "You're all set for now."
//   f  the home never answers: skeletons
//
// d, e, g, h and M are P-08-T23's. White label: the firm's name comes from the branding; nothing
// here names the product or the agent (INV-5, DEC-01). Red appears only on a past-due to-do.

export interface POR02Props {
  /** The scope the person chose; null opens the first (P-08 §5.1). */
  scopeId: string | null;
  frame?: boolean;
}

const TZ = DEFAULT_TZ;

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

/** The to-do kinds whose screens exist in this build (none yet: every target is planned). */
function goLink(todo: PortalHomeTodoOut): string | undefined {
  return PLANNED_VISIBLE ? COPY.todo.go[todo.kind] : undefined;
}

interface TodoWords {
  title: string;
  sub: string | null;
}

/** A to-do card's words from its kind, count and facts (the kind registry). */
export function todoWords(todo: PortalHomeTodoOut, firstVisit: boolean): TodoWords | null {
  if (firstVisit && todo.state !== "none" && todo.detail != null) {
    return { title: todo.detail, sub: COPY.todo.firstVisit[todo.kind] ?? null };
  }
  const detail = todo.detail ?? null;
  switch (todo.kind) {
    case "upload":
      return todo.count === 0 ? null : { title: COPY.todo.upload(todo.count), sub: detail };
    case "answer":
      return todo.count === 0 ? null : { title: COPY.todo.answer(todo.count), sub: detail };
    case "sign":
      return todo.state === "none" ? { ...COPY.todo.nothingToSign } : null;
    case "deliverables":
      return todo.count === 0 ? null : { title: COPY.todo.ready(todo.count), sub: detail };
    case "approve":
      return todo.state === "none" ? { ...COPY.todo.nothingToApprove } : null;
    default:
      // The other kinds (reconnect, statements review, control requests) are P-08-T23's.
      return null;
  }
}

function TodoCard({
  todo,
  firstVisit,
  now,
}: {
  todo: PortalHomeTodoOut;
  firstVisit: boolean;
  now: Date;
}): JSX.Element | null {
  const words = todoWords(todo, firstVisit);
  if (words === null) return null;
  const link = todo.state === "none" ? undefined : goLink(todo);
  const overdue = todo.state === "overdue" && todo.due_date != null;
  return (
    <li
      data-todo={todo.kind}
      className="flex min-h-[116px] flex-col gap-[4px] rounded-pane bg-card p-[14px] shadow-e1"
    >
      <span className="text-section font-medium">{words.title}</span>
      {words.sub !== null && <span className="text-cell text-ink-2">{words.sub}</span>}
      {overdue && todo.due_date != null && (
        <span>
          <StatusPill variant="red-tint">
            {COPY.todo.overdue(date(onDay(todo.due_date), { now, tz: TZ }))}
          </StatusPill>
        </span>
      )}
      {link !== undefined && (
        <span className="mt-auto text-cell font-medium text-ink" title={COPY.planned}>
          {link}
        </span>
      )}
    </li>
  );
}

function StageTracker({ card }: { card: PortalHomeWorkCardOut }): JSX.Element {
  const stages = card.stages ?? [];
  return (
    <ol aria-label={card.title} className="flex items-start gap-[8px]">
      {stages.map((s) => (
        <li
          key={s.code}
          {...(s.state === "current" ? { "aria-current": "step" as const } : {})}
          className="flex min-w-0 flex-1 flex-col items-center gap-[6px] text-center"
        >
          <span className="flex items-center gap-[6px]">
            <StatusDisc
              state={s.state === "done" ? "done" : s.state === "current" ? "half" : "todo"}
            />
            <span className="sr-only">{COPY.stageState[s.state]}</span>
          </span>
          <span className={s.state === "upcoming" ? "text-cell text-ink-3" : "text-cell text-ink"}>
            {COPY.stages[s.code]}
          </span>
        </li>
      ))}
    </ol>
  );
}

function WorkCard({
  card,
  firm,
  now,
}: {
  card: PortalHomeWorkCardOut;
  firm: string;
  now: Date;
}): JSX.Element {
  const note =
    card.note_code === "waiting_on_k1" && card.note_subject != null && card.note_date != null
      ? COPY.notes.waiting_on_k1(
          card.note_subject,
          firm,
          date(onDay(card.note_date), { now, tz: TZ }),
        )
      : card.note_code === "waiting_on_your_k1" && card.note_subject != null
        ? COPY.notes.waiting_on_your_k1(card.note_subject)
        : null;
  return (
    <section
      aria-label={card.title}
      data-work-card={card.kind}
      className="flex flex-col gap-[14px] rounded-pane bg-card p-[16px] shadow-e1"
    >
      <div className="flex items-start gap-[10px]">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-section font-medium">{card.title}</span>
          {card.sub != null && <span className="text-cell text-ink-3">{card.sub}</span>}
        </span>
        <StatusPill
          variant={
            card.pill.variant === "success"
              ? "green-tint"
              : card.pill.variant === "state"
                ? "amber"
                : "neutral"
          }
        >
          {COPY.pills[card.pill.code]}
        </StatusPill>
      </div>
      {(card.stages ?? []).length > 0 && <StageTracker card={card} />}
      {note !== null && <p className="text-cell text-ink-2">{note}</p>}
    </section>
  );
}

/** The skeleton home (f): the to-do grid and the work card as resting bars. The portal draws its
 * own, because the kit's ViewState module carries the firm's product words, which the portal
 * bundle must not hold (portal-dist-check). */
function Loading(): JSX.Element {
  return (
    <div role="status" aria-label={COPY.loading} className="flex flex-col gap-[14px] p-[18px]">
      <div className="h-[18px] w-[38%] rounded-pill bg-nested" />
      <div className="grid grid-cols-4 gap-[10px]">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-[116px] rounded-pane bg-nested" />
        ))}
      </div>
      <div className="h-[160px] rounded-pane bg-nested" />
    </div>
  );
}

function Rail({ home }: { home: PortalHomeOut | undefined }): JSX.Element {
  return (
    <Pane header={false}>
      {home !== undefined && (
        <div className="flex flex-col">
          <div className="m-[10px] flex flex-col items-center rounded-pane bg-nested px-[12px] pt-[14px] pb-[13px] text-center">
            <p className="text-section font-medium">{home.scope.label}</p>
            {home.scope.sub != null && <p className="text-meta text-ink-3">{home.scope.sub}</p>}
          </div>
          <h2 className="px-[12px] pt-[6px] pb-[4px] text-section font-medium">
            {COPY.rail.title}
          </h2>
          <ul aria-label={COPY.rail.title} className="flex flex-col">
            {(home.team ?? []).map((m) => (
              <li
                key={m.user_id}
                className="flex min-h-[44px] items-center gap-[8px] px-[12px] py-[6px] hairline-b"
              >
                <Icon name="circle-user-round" size={16} className="flex-none text-ink-3" />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-body">{m.display_name}</span>
                  <span className="truncate text-meta text-ink-3">{COPY.team[m.role_code]}</span>
                </span>
                {PLANNED_VISIBLE && (
                  <IconButton
                    icon="message-circle"
                    label={COPY.rail.message(m.display_name)}
                    variant="white"
                    disabled
                  />
                )}
              </li>
            ))}
          </ul>
          {PLANNED_VISIBLE && (home.recent_threads ?? []).length > 0 && (
            <section aria-label={COPY.rail.recent} className="flex flex-col">
              <h2 className="px-[12px] pt-[12px] pb-[4px] text-section font-medium">
                {COPY.rail.recent}
              </h2>
              {(home.recent_threads ?? []).map((t) => (
                <div key={t.thread_id} className="flex flex-col px-[12px] py-[6px] hairline-b">
                  <span className={t.unread ? "text-body font-medium" : "text-body"}>
                    {t.subject}
                  </span>
                  <span className="text-meta text-ink-3">
                    {`${t.from_name} · ${date(t.at, { now: new Date(t.at), tz: TZ })}`}
                  </span>
                </div>
              ))}
            </section>
          )}
          {PLANNED_VISIBLE && (
            <span
              title={COPY.planned}
              className="flex items-center gap-[6px] px-[12px] py-[12px] text-cell font-medium text-ink"
            >
              {COPY.rail.account}
              <Icon name="arrow-right" size={12} className="text-ink-3" />
            </span>
          )}
        </div>
      )}
    </Pane>
  );
}

function Main({
  home,
  scopeId,
  firstName,
}: {
  home: PortalHomeOut;
  scopeId: string;
  firstName: string;
}): JSX.Element {
  const now = useNow();
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const dismiss = useDismissWelcome(scopeId);
  const [dismissed, setDismissed] = useState(false);
  const todos = home.todos ?? [];
  const binder = home.binder;
  const showWelcome = home.first_visit && !home.welcome_dismissed && !dismissed;
  return (
    <div className="flex flex-col gap-[14px] p-[18px]">
      <header className="flex flex-col">
        <h1 className="text-title font-medium">{COPY.greeting(firstName)}</h1>
        <p className="text-body text-ink-3">{weekdayDate(now, { now, tz: TZ })}</p>
      </header>
      {showWelcome && (
        <section
          aria-label={COPY.welcome.title(firm)}
          className="relative flex flex-col gap-[4px] rounded-pane bg-card p-[16px] pr-[48px] shadow-e1"
        >
          <p className="text-section font-medium">{COPY.welcome.title(firm)}</p>
          <p className="text-cell text-ink-2">{COPY.welcome.body}</p>
          <span className="absolute top-[12px] right-[12px]">
            <IconButton
              icon="x"
              label={COPY.welcome.dismiss}
              variant="white"
              onClick={() => {
                setDismissed(true);
                dismiss.mutate({
                  body: { scope_id: scopeId, welcome_dismissed: true, version: 0 },
                });
              }}
            />
          </span>
        </section>
      )}
      {home.all_done ? (
        <section className="flex flex-col gap-[4px] rounded-pane bg-card p-[16px] shadow-e1">
          <p className="text-section font-medium">{COPY.allSet.title}</p>
          <p className="text-cell text-ink-2">{COPY.allSet.body}</p>
        </section>
      ) : (
        <ul aria-label={COPY.todo.label} className="grid grid-cols-4 gap-[10px]">
          {todos.map((t) => (
            <TodoCard key={t.kind} todo={t} firstVisit={home.first_visit} now={now} />
          ))}
        </ul>
      )}
      {(home.work_cards ?? []).map((card) => (
        <WorkCard key={card.work_item_id} card={card} firm={firm} now={now} />
      ))}
      {binder != null && (
        <section
          aria-label={COPY.binder.title}
          className="flex flex-col gap-[10px] rounded-pane bg-card p-[16px] shadow-e1"
        >
          <div className="flex items-center">
            <h2 className="flex-1 text-section font-medium">{COPY.binder.title}</h2>
            {PLANNED_VISIBLE && (
              <Button variant="secondary" size="sm" disabled title={COPY.planned}>
                {COPY.binder.open}
              </Button>
            )}
          </div>
          <ProgressBar
            done={binder.done}
            total={binder.total}
            left={[
              COPY.binder.done(count(binder.done), count(binder.total)),
              ...(binder.sorted_count > 0
                ? [COPY.binder.sorted(firm, count(binder.sorted_count))]
                : []),
            ].join(" · ")}
          />
        </section>
      )}
      {(home.earlier ?? []).length > 0 && (
        <section
          aria-label={COPY.earlier.title}
          className="flex flex-col rounded-pane bg-card shadow-e1"
        >
          <h2 className="px-[16px] pt-[12px] pb-[6px] text-section font-medium">
            {COPY.earlier.title}
          </h2>
          <ul className="flex flex-col">
            {(home.earlier ?? []).map((e, i) => {
              const words = COPY.earlier.row[e.kind](e.facts ?? {});
              const when =
                e.date == null ? null : date(onDay(e.date), { now, tz: TZ, withYear: true });
              return (
                <li
                  key={`${e.kind}:${String(i)}`}
                  className="flex min-h-[40px] items-center gap-[8px] px-[16px] py-[6px] hairline-t"
                >
                  <StatusDisc state="done" />
                  <span className="min-w-0 flex-1 text-body">
                    {when === null ? words : `${words} · ${when}`}
                  </span>
                  {PLANNED_VISIBLE && (
                    <span title={COPY.planned} className="text-cell text-ink-3">
                      {COPY.earlier.view}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}

export function POR02({ scopeId, frame = false }: POR02Props): JSX.Element | null {
  const bar = usePortalToolbar(scopeId);
  const home = usePortalHome(scopeId);
  if (bar === undefined) return null;
  const chosen = scopeId ?? bar.scope?.id ?? null;
  const firstName = bar.user.split(/\s+/)[0] ?? bar.user;
  const data = home.data;
  return (
    <div data-screen="POR-02" className="flex min-h-0 flex-1 flex-col">
      <PortalLayout
        variant="split"
        user={bar.user}
        nav={bar.nav}
        active="Home"
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        rail={<Rail home={data} />}
      >
        <Pane header={false}>
          {data === undefined || chosen === null ? (
            home.isError ? (
              <EmptyState
                tone="error"
                icon="circle-alert"
                title={COPY.error.title}
                action={
                  <Button variant="secondary" size="sm" onClick={() => void home.refetch()}>
                    {COPY.error.retry}
                  </Button>
                }
              >
                {COPY.error.body}
              </EmptyState>
            ) : (
              <Loading />
            )
          ) : (
            <Main home={data} scopeId={chosen} firstName={firstName} />
          )}
        </Pane>
      </PortalLayout>
    </div>
  );
}

/** The page: the firm's branding first, then the home under its brand. */
export function PortalHome(props: POR02Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR02 {...props} />
    </PortalBrandProvider>
  );
}
