import type {
  MePortalScopeOut,
  PortalHomeOut,
  PortalHomeTeamMemberOut,
  PortalHomeTodoOut,
  PortalHomeWorkCardOut,
} from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  EmptyState,
  Icon,
  IconButton,
  type MenuItem,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  type PortalNavItem,
  type PortalUserMenu,
  ProgressBar,
  StatusDisc,
  StatusPill,
  count,
  date,
  portalNav,
  usePortalBrand,
  weekdayDate,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { goToSignIn, portalSignOut } from "../../app-core/auth/bff";
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

// POR-02 · Portal home (P-08-T15 part 1, P-08-T23 part 2; docs/screens/POR-02.md). T7 split over
// `GET /v1/portal/home` for the chosen scope, and T7-M at 390: the rail (household card, team rows
// with their client-facing labels, the Recent messages band and "Account & people", both planned and
// drawn only in fixture builds), the greeting on `useNow`, the to-do cards from a kind registry, the
// work cards with their StageTracker and note, My K-1s, the notices info row, the Documents binder
// card and the Earlier list. Each artboard is its data (fixtures/scenarios/POR-02.ts):
//
//   a  Claire Feld at E0: Upload 2, Answer 3, nothing to sign, 2 ready; the return at Review
//   b  her first visit (Mon Feb 2, 2026): the welcome card, 0 of 21, sign and upload to-dos
//   c  every open item done: "You're all set for now."
//   d  Tess Moreno, Copperleaf: Approvals in the nav, red tint only on the past-due upload
//   e  Meera Shah's role union: her own 1040 and My K-1s; the user chip switches scope
//   f  the home never answers: skeletons
//   g  Luis Ferrante, Granite Peak (Thu Oct 22): review the draft FY2026 statements
//   h  Marisol Vega, Tessellate: SOC 2 control requests and exceptions
//   M  a at 390: stacked to-dos, the tracker as a list, the team collapsed, tab bar badges
//
// g's and h's to-do kinds are fixture-only (the `statements_studio` and `attest` entitlements, P-08
// Story 6.7): production hides them until A-10/R-02 and X-01 register their home sources. White
// label: the firm's name comes from the branding; nothing here names the product or the agent
// (INV-5, DEC-01). Red appears only on a past-due to-do.

export interface POR02Props {
  /** The scope the person chose; null opens the first (P-08 §5.1). */
  scopeId: string | null;
  /** The person picked another scope in the user menu (the route keeps it in `?scope=`). */
  onScope?: (scopeId: string) => void;
  /** T7-M at 390 (the portal entry decides from the viewport). */
  mobile?: boolean;
  /** A nav item, a to-do's link or "Open binder" was chosen (the portal entry routes it). */
  onNavigate?: (area: string) => void;
  frame?: boolean;
}

/** Targets built in the portal, by the area that opens them (R-01-T10 mounted POR-03). */
const LIVE_TARGETS: Readonly<Partial<Record<string, string>>> = { "POR-03": "Documents" };

const TZ = DEFAULT_TZ;

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

/** Kinds whose home source is planned (P-08 §2.2): drawn in fixture builds, hidden in production
 * until their epics register them (reconnect A-02; statements review A-10 with R-02 behind
 * `statements_studio`; control requests, exceptions and the description X-01 behind `attest`). */
const PLANNED_KINDS: ReadonlySet<PortalHomeTodoOut["kind"]> = new Set([
  "reconnect",
  "review_statements",
  "control_requests",
  "exceptions",
  "description_approved",
]);

/** Scope kinds whose home is POR-02 (a full-client grant). A K-1 recipient's scope opens POR-13. */
const HOME_SCOPES: ReadonlySet<MePortalScopeOut["kind"]> = new Set([
  "client",
  "client_entity",
  "engagement",
]);

/** The team row the client writes to by default: the day-to-day contact (OQ-5). */
const DAY_TO_DAY: ReadonlySet<PortalHomeTeamMemberOut["role_code"]> = new Set([
  "preparer_day_to_day",
  "day_to_day_contact",
  "close_preparer",
  "preparer",
]);

/** The to-do kinds whose screens exist in this build (none yet: every target is planned). */
function goLink(todo: PortalHomeTodoOut): string | undefined {
  return PLANNED_VISIBLE ? COPY.todo.go[todo.kind] : undefined;
}

interface TodoWords {
  title: string;
  sub: string | null;
  /** The title reads in ink-3: nothing is asked of the client ("Nothing to sign yet"). */
  quiet?: boolean;
}

type Facts = Readonly<Record<string, string | number | boolean>>;

const fact = (facts: Facts | undefined, key: string): string => String(facts?.[key] ?? "");

/** A to-do card's words from its kind, count and facts (the kind registry). `day` formats a date
 * fact on the scenario's clock. */
export function todoWords(
  todo: PortalHomeTodoOut,
  firstVisit: boolean,
  day: (iso: string) => string = (iso) => iso,
): TodoWords | null {
  if (firstVisit && todo.state !== "none" && todo.detail != null) {
    return { title: todo.detail, sub: COPY.todo.firstVisit[todo.kind] ?? null };
  }
  if (PLANNED_KINDS.has(todo.kind) && !PLANNED_VISIBLE) return null;
  const detail = todo.detail ?? null;
  const facts = todo.facts;
  switch (todo.kind) {
    case "upload": {
      if (todo.count === 0) return null;
      const month = facts?.close_month;
      return {
        title:
          month === undefined
            ? COPY.todo.upload(todo.count)
            : COPY.todo.uploadForClose(todo.count, String(month)),
        sub: detail,
      };
    }
    case "answer":
      return todo.count === 0 ? null : { title: COPY.todo.answer(todo.count), sub: detail };
    case "sign": {
      if (todo.state !== "none") return null;
      const after = COPY.todo.nothingToSignAfter[fact(facts, "after")];
      return {
        ...COPY.todo.nothingToSign,
        ...(after === undefined ? {} : { sub: after }),
        quiet: true,
      };
    }
    case "deliverables":
      return todo.count === 0 ? null : { title: COPY.todo.ready(todo.count), sub: detail };
    case "approve":
      return todo.state === "none" ? { ...COPY.todo.nothingToApprove, quiet: true } : null;
    case "reconnect":
      return todo.count === 0
        ? null
        : COPY.todo.reconnect(fact(facts, "institution"), fact(facts, "month"));
    case "review_statements":
      return todo.state === "none"
        ? null
        : COPY.todo.reviewStatements(
            fact(facts, "fiscal_year"),
            fact(facts, "shared_by"),
            day(fact(facts, "shared_on")),
          );
    case "control_requests":
      return todo.count === 0 ? null : COPY.todo.controlRequests(todo.count, fact(facts, "grc"));
    case "exceptions":
      return todo.count === 0 ? null : COPY.todo.exceptions(todo.count, fact(facts, "criteria"));
    case "description_approved":
      return {
        ...COPY.todo.descriptionApproved(day(fact(facts, "approved_on"))),
        quiet: true,
      };
  }
}

interface ShownTodo {
  todo: PortalHomeTodoOut;
  words: TodoWords;
}

function shownTodos(home: PortalHomeOut, day: (iso: string) => string): ShownTodo[] {
  return (home.todos ?? []).flatMap((todo) => {
    const words = todoWords(todo, home.first_visit, day);
    return words === null ? [] : [{ todo, words }];
  });
}

/** The area a to-do opens when its target is built, with the person's way there. */
function liveArea(todo: PortalHomeTodoOut, onNavigate: Navigate): string | undefined {
  if (onNavigate === undefined || todo.state === "none") return undefined;
  return LIVE_TARGETS[todo.target?.screen ?? ""];
}

type Navigate = ((area: string) => void) | undefined;

function TodoCard({
  shown,
  now,
  onNavigate,
}: {
  shown: ShownTodo;
  now: Date;
  onNavigate: Navigate;
}): JSX.Element {
  const { todo, words } = shown;
  const area = liveArea(todo, onNavigate);
  const link = todo.state === "none" ? undefined : (COPY.todo.go[todo.kind] ?? undefined);
  const overdue = todo.state === "overdue" && todo.due_date != null;
  return (
    <li
      data-todo={todo.kind}
      className="flex min-h-[116px] flex-col gap-[4px] rounded-pane bg-card p-[14px] shadow-e1"
    >
      <span className="flex items-start gap-[8px]">
        <Icon
          name={COPY.todo.glyph[todo.kind]}
          size={15}
          className="mt-[2px] flex-none text-ink-2"
        />
        <span className={`text-section font-medium ${words.quiet === true ? "text-ink-3" : ""}`}>
          {words.title}
        </span>
      </span>
      {overdue && todo.due_date != null && (
        <span>
          <StatusPill variant="red-tint">
            {COPY.todo.overdue(date(onDay(todo.due_date), { now, tz: TZ }))}
          </StatusPill>
        </span>
      )}
      {words.sub !== null && <span className="text-cell text-ink-2">{words.sub}</span>}
      {link !== undefined && area !== undefined && (
        <button
          type="button"
          onClick={() => onNavigate?.(area)}
          className="mt-auto self-start text-cell font-medium text-ink hover:underline"
        >
          {link}
        </button>
      )}
      {link !== undefined && area === undefined && PLANNED_VISIBLE && (
        <span className="mt-auto text-cell font-medium text-ink" title={COPY.planned}>
          {link}
        </span>
      )}
    </li>
  );
}

/** T7-M's to-do card: 76 high, full width, glyph, title, line and a chevron when it leads on. */
function MobileTodoCard({
  shown,
  now,
  onNavigate,
}: {
  shown: ShownTodo;
  now: Date;
  onNavigate: Navigate;
}): JSX.Element {
  const { todo, words } = shown;
  const area = liveArea(todo, onNavigate);
  const link = area !== undefined ? COPY.todo.go[todo.kind] : goLink(todo);
  const overdue = todo.state === "overdue" && todo.due_date != null;
  return (
    <li
      data-todo={todo.kind}
      className="flex min-h-[76px] items-center gap-[12px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1"
    >
      <Icon name={COPY.todo.glyph[todo.kind]} size={15} className="flex-none text-ink-2" />
      <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
        <span className={`text-section font-medium ${words.quiet === true ? "text-ink-3" : ""}`}>
          {words.title}
        </span>
        {overdue && todo.due_date != null && (
          <span>
            <StatusPill variant="red-tint">
              {COPY.todo.overdue(date(onDay(todo.due_date), { now, tz: TZ }))}
            </StatusPill>
          </span>
        )}
        {words.sub !== null && <span className="text-cell text-ink-2">{words.sub}</span>}
      </span>
      {link !== undefined && area !== undefined && (
        <button
          type="button"
          aria-label={link}
          onClick={() => onNavigate?.(area)}
          className="inline-flex size-[44px] flex-none items-center justify-center text-ink-3"
        >
          <Icon name="chevron-right" size={14} />
        </button>
      )}
      {link !== undefined && area === undefined && (
        <Icon name="chevron-right" size={14} className="flex-none text-ink-3" />
      )}
    </li>
  );
}

function StageTracker({
  card,
  vertical = false,
}: {
  card: PortalHomeWorkCardOut;
  vertical?: boolean;
}): JSX.Element {
  const stages = card.stages ?? [];
  return (
    <ol
      aria-label={card.title}
      className={vertical ? "flex flex-col gap-[14px]" : "flex items-start gap-[8px]"}
    >
      {stages.map((s) => {
        const done = s.facts?.done;
        const total = s.facts?.total;
        const tally =
          typeof done === "number" && typeof total === "number"
            ? COPY.stageCount(done, total)
            : null;
        return (
          <li
            key={s.code}
            {...(s.state === "current" ? { "aria-current": "step" as const } : {})}
            className={
              vertical
                ? "flex items-center gap-[10px]"
                : "flex min-w-0 flex-1 flex-col items-center gap-[6px] text-center"
            }
          >
            <span className="flex items-center gap-[6px]">
              <StatusDisc
                state={s.state === "done" ? "done" : s.state === "current" ? "half" : "todo"}
              />
              <span className="sr-only">{COPY.stageState[s.state]}</span>
            </span>
            <span
              className={s.state === "upcoming" ? "text-cell text-ink-3" : "text-cell text-ink"}
            >
              {COPY.stages[s.code]}
            </span>
            {tally !== null && <span className="text-meta text-ink-3">{tally}</span>}
          </li>
        );
      })}
    </ol>
  );
}

function NoteRow({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="flex items-start gap-[8px] rounded-nested bg-nested px-[12px] py-[10px] text-cell text-ink-2">
      <Icon name="info" size={14} className="mt-[1px] flex-none text-ink-2" />
      <span>{children}</span>
    </p>
  );
}

function WorkCard({
  card,
  firm,
  now,
  mobile,
}: {
  card: PortalHomeWorkCardOut;
  firm: string;
  now: Date;
  mobile: boolean;
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
  const pill = (
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
  );
  return (
    <section
      aria-label={card.title}
      data-work-card={card.kind}
      className="flex flex-col gap-[14px] rounded-pane bg-card p-[16px] shadow-e1"
    >
      <div
        className={mobile ? "flex flex-col items-start gap-[8px]" : "flex items-start gap-[10px]"}
      >
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-section font-medium">{card.title}</span>
          {card.sub != null && <span className="text-cell text-ink-3">{card.sub}</span>}
        </span>
        {pill}
      </div>
      {(card.stages ?? []).length > 0 && <StageTracker card={card} vertical={mobile} />}
      {note !== null && <NoteRow>{note}</NoteRow>}
    </section>
  );
}

/** e: the K-1 packages the person receives, released or not. Nothing of the partnership's own
 * return reaches this card (INV-4): a label, released, expected by. */
function MyK1s({ home, now }: { home: PortalHomeOut; now: Date }): JSX.Element | null {
  const k1s = home.my_k1s ?? [];
  if (k1s.length === 0) return null;
  return (
    <section
      aria-label={COPY.myK1s.title}
      className="flex flex-col rounded-pane bg-card shadow-e1"
    >
      <h2 className="px-[16px] pt-[12px] pb-[10px] text-section font-medium">
        {COPY.myK1s.title}
      </h2>
      <ul className="flex flex-col">
        {k1s.map((k) => (
          <li
            key={k.k1_package_id}
            className="flex min-h-[52px] items-center gap-[10px] px-[16px] py-[8px] hairline-t"
          >
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-body">{k.label}</span>
              {!k.released && k.expected_by != null && (
                <span className="text-cell text-ink-3">
                  {COPY.myK1s.expected(date(onDay(k.expected_by), { now, tz: TZ }))}
                </span>
              )}
            </span>
            {!k.released && <StatusPill variant="neutral">{COPY.myK1s.notReleased}</StatusPill>}
            {PLANNED_VISIBLE && (
              <span title={COPY.planned} className="flex-none text-ink-3">
                <Icon name="chevron-right" size={14} />
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Notices({ home, firm }: { home: PortalHomeOut; firm: string }): JSX.Element | null {
  const notices = home.notices_info ?? [];
  if (notices.length === 0) return null;
  return (
    <>
      {notices.map((n) => (
        <section
          key={n.notice_id}
          data-notice={n.code}
          className="flex items-start gap-[8px] rounded-pane bg-card px-[16px] py-[12px] text-cell text-ink-2 shadow-e1"
        >
          <Icon name="info" size={14} className="mt-[1px] flex-none text-ink-2" />
          <span>{COPY.notice[n.code](n.subject, firm)}</span>
        </section>
      ))}
    </>
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
                <div
                  key={t.thread_id}
                  className="flex items-center gap-[8px] px-[12px] py-[6px] hairline-b"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className={t.unread ? "text-body font-medium" : "text-body"}>
                      {t.subject}
                    </span>
                    <span className="text-meta text-ink-3">
                      {`${t.from_name} · ${date(t.at, { now: new Date(t.at), tz: TZ })}`}
                    </span>
                  </span>
                  {t.unread && (
                    <span
                      data-part="unread"
                      aria-hidden="true"
                      className="size-[8px] flex-none rounded-pill bg-amber"
                    />
                  )}
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

/** T7-M's collapsed team: "4 people · Message Kevin" (the day-to-day contact's first name). */
function MobileTeam({ home }: { home: PortalHomeOut }): JSX.Element | null {
  const team = home.team ?? [];
  if (team.length === 0) return null;
  const contact = team.find((m) => DAY_TO_DAY.has(m.role_code));
  const first = contact?.display_name.split(/\s+/)[0] ?? null;
  return (
    <section
      aria-label={COPY.rail.title}
      className="flex min-h-[64px] items-center gap-[12px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1"
    >
      <Icon name="circle-user-round" size={15} className="flex-none text-ink-2" />
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="text-section font-medium">{COPY.rail.title}</span>
        <span className="text-cell text-ink-2">{COPY.mobile.team(team.length, first)}</span>
      </span>
      <Icon name="chevron-right" size={14} className="flex-none text-ink-3" />
    </section>
  );
}

function Main({
  home,
  scopeId,
  firstName,
  mobile,
  onNavigate,
}: {
  home: PortalHomeOut;
  scopeId: string;
  firstName: string;
  mobile: boolean;
  onNavigate: Navigate;
}): JSX.Element {
  const now = useNow();
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const dismiss = useDismissWelcome(scopeId);
  const [dismissed, setDismissed] = useState(false);
  const day = (iso: string): string => date(onDay(iso), { now, tz: TZ });
  const todos = shownTodos(home, day);
  const binder = home.binder;
  const showWelcome = home.first_visit && !home.welcome_dismissed && !dismissed;
  return (
    <div className={mobile ? "flex flex-col gap-[10px]" : "flex flex-col gap-[14px] p-[18px]"}>
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
      ) : mobile ? (
        <ul aria-label={COPY.todo.label} className="flex flex-col gap-[10px]">
          {todos.map((t) => (
            <MobileTodoCard key={t.todo.kind} shown={t} now={now} onNavigate={onNavigate} />
          ))}
        </ul>
      ) : (
        <ul
          aria-label={COPY.todo.label}
          className="grid gap-[10px]"
          style={{
            gridTemplateColumns: `repeat(${String(Math.max(todos.length, 1))}, minmax(0, 1fr))`,
          }}
        >
          {todos.map((t) => (
            <TodoCard key={t.todo.kind} shown={t} now={now} onNavigate={onNavigate} />
          ))}
        </ul>
      )}
      {(home.work_cards ?? []).map((card) => (
        <WorkCard key={card.work_item_id} card={card} firm={firm} now={now} mobile={mobile} />
      ))}
      <MyK1s home={home} now={now} />
      <Notices home={home} firm={firm} />
      {binder != null && (
        <section
          aria-label={COPY.binder.title}
          className="flex flex-col gap-[10px] rounded-pane bg-card p-[16px] shadow-e1"
        >
          <div className="flex items-center">
            <h2 className="flex-1 text-section font-medium">{COPY.binder.title}</h2>
            {onNavigate !== undefined ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onNavigate("Documents");
                }}
              >
                {COPY.binder.open}
              </Button>
            ) : (
              PLANNED_VISIBLE && (
                <Button variant="secondary" size="sm" disabled title={COPY.planned}>
                  {COPY.binder.open}
                </Button>
              )
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
      {mobile && <MobileTeam home={home} />}
    </div>
  );
}

/** The user chip's menu (e): each scope the person holds with its role, then the account links
 * and Sign out. A full-client scope switches the home; a K-1 recipient's scope opens POR-13 (My
 * K-1s), planned: drawn disabled in fixture builds and left out in production (DEC-346). The
 * account links (POR-12, POR-16, POR-10, Security) are planned too. */
export function userMenuOf(
  scopes: readonly MePortalScopeOut[],
  current: string | null,
  entity: boolean,
  onScope: (scopeId: string) => void,
  onSignOut: () => void,
): PortalUserMenu {
  const scopeItems: MenuItem[] = scopes.flatMap((s): MenuItem[] => {
    const home = HOME_SCOPES.has(s.kind);
    if (!home && !PLANNED_VISIBLE) return [];
    return [
      {
        label: s.label,
        hint: s.role_label,
        checked: s.id === current,
        ...(home
          ? {
              onSelect: () => {
                onScope(s.id);
              },
            }
          : { disabled: true, onSelect: () => undefined }),
      },
    ];
  });
  const planned: MenuItem[] = PLANNED_VISIBLE
    ? [
        COPY.userMenu.account,
        ...(entity ? [COPY.userMenu.connections] : []),
        COPY.userMenu.billing,
        COPY.userMenu.security,
      ].map((label) => ({ label, disabled: true, onSelect: () => undefined }))
    : [];
  return {
    label: COPY.userMenu.label,
    sections: [
      ...(scopeItems.length > 0 ? [scopeItems] : []),
      ...(planned.length > 0 ? [planned] : []),
      [{ label: COPY.userMenu.signOut, icon: "log-out", onSelect: onSignOut }],
    ],
  };
}

/** The nav with T7-M's count badges: Documents (open uploads) and Messages (unread threads). */
export function navWithCounts(
  nav: readonly PortalNavItem[],
  home: PortalHomeOut | undefined,
): PortalNavItem[] {
  if (home === undefined) return [...nav];
  const uploads = (home.todos ?? [])
    .filter((t) => t.kind === "upload" && t.state !== "none")
    .reduce((n, t) => n + t.count, 0);
  const unread = (home.recent_threads ?? []).filter((t) => t.unread).length;
  const counts: Readonly<Record<string, number>> = {
    Documents: uploads,
    ...(PLANNED_VISIBLE ? { Messages: unread } : {}),
  };
  return nav.map((item) => {
    const n = counts[item.label];
    return n === undefined || n === 0
      ? item
      : { ...item, count: n, countLabel: COPY.todo.countLabel(item.label, n) };
  });
}

export function POR02({
  scopeId,
  onScope,
  mobile = false,
  onNavigate,
  frame = false,
}: POR02Props): JSX.Element | null {
  const [picked, setPicked] = useState<string | null>(scopeId);
  const bar = usePortalToolbar(picked);
  const chosen = picked ?? bar?.scope?.id ?? null;
  const home = usePortalHome(picked);
  if (bar === undefined) return null;
  const firstName = bar.user.split(/\s+/)[0] ?? bar.user;
  const data = home.data;
  const userMenu = userMenuOf(
    bar.scopes,
    chosen,
    bar.scope?.kind === "client_entity",
    (id) => {
      setPicked(id);
      onScope?.(id);
    },
    () => {
      void portalSignOut().finally(() => {
        goToSignIn("/");
      });
    },
  );
  const body =
    data === undefined || chosen === null ? (
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
      <Main
        home={data}
        scopeId={chosen}
        firstName={firstName}
        mobile={mobile}
        onNavigate={onNavigate}
      />
    );
  if (mobile) {
    return (
      <div data-screen="POR-02" className="flex min-h-0 flex-1 flex-col">
        <PortalLayout
          variant="mobile"
          user={bar.user}
          nav={navWithCounts(bar.nav, data)}
          active="Home"
          userMenu={userMenu}
          frame={frame}
          {...(frame ? { height: 844 } : {})}
          {...(onNavigate === undefined ? {} : { onNavigate })}
        >
          {body}
        </PortalLayout>
      </div>
    );
  }
  return (
    <div data-screen="POR-02" className="flex min-h-0 flex-1 flex-col">
      <PortalLayout
        variant="split"
        user={bar.user}
        nav={bar.nav}
        active="Home"
        userMenu={userMenu}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        {...(onNavigate === undefined ? {} : { onNavigate })}
        rail={<Rail home={data} />}
      >
        <Pane header={false}>{body}</Pane>
      </PortalLayout>
    </div>
  );
}

/** ADM-10's live preview (R-01-T28; R-01 Story 8.2): this home for a projection the firm app read
 * in preview mode, under the brand the caller provides. Nothing in it navigates or writes: no
 * user menu and no `onNavigate`, so every control is inert. Approvals shows for an entity only. */
export function PortalHomePreview({
  home,
  user,
  mobile,
}: {
  home: PortalHomeOut;
  user: string;
  mobile: boolean;
}): JSX.Element {
  const firstName = user.split(/\s+/)[0] ?? user;
  const nav = portalNav(home.scope.kind === "client_entity" ? "entity" : "individual");
  const body = (
    <Main
      home={home}
      scopeId={home.scope.id}
      firstName={firstName}
      mobile={mobile}
      onNavigate={undefined}
    />
  );
  if (mobile) {
    return (
      <PortalLayout
        variant="mobile"
        user={user}
        nav={navWithCounts(nav, home)}
        active="Home"
        frame
        height={844}
      >
        {body}
      </PortalLayout>
    );
  }
  return (
    <PortalLayout
      variant="split"
      user={user}
      nav={nav}
      active="Home"
      frame
      height={860}
      rail={<Rail home={home} />}
    >
      <Pane header={false}>{body}</Pane>
    </PortalLayout>
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
