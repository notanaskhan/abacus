import type { HomeOut, HomeTileOut, HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import {
  ActivityRow,
  DashTile,
  DashboardLayout,
  DeadlineRow,
  ErrorState,
  Icon,
  type IconName,
  Popover,
  QueueEmpty,
  type ToolbarProps,
  date,
  status,
  time,
  weekdayDate,
} from "@abacus/ui";
import { meOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow, useToday } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useOpenHref } from "../../app-core/open";
import { useSession } from "../../app-core/session";
import { hrefOf as linkOf, to } from "../../routes/to";
import { hostHref } from "./hosts";
import {
  HOME_SEGMENTS,
  HomeSegmented,
  WaitingOnYou,
  useGateCounts,
  useHome,
  useWaitingOnYou,
} from "../../domain/home";
import { COPY } from "./copy";

// HOME-01 · Home dashboard, the main region (I-01-T06; docs/screens/HOME-01.md). T11
// DashboardLayout: the subbar (greeting and date, "Open Today →" behind `today_brief.enabled`, the
// Home segmented with the Approvals count, the Office chip and the running pill), the tile row,
// and "Waiting on you" with its summary, bands and rows. The pane header's count, the summary line
// and the Approvals badge all read the one counts response (`GET /v1/human-gates/counts`); the rows
// come from the list beside it. No row renders a gate verb: a row opens where its gate is decided.
// I-01-T11: the right column (deadlines, then client activity rows once I-01-T12 fills them), the
// your-work band, the Office chip opening on `/v1/me`'s default office, the 266 px by-office
// popover on a tile (click or keyboard), and the running pill polled every 30 s.
//
//   a     Daniel Reyes at E0: 11 = 3 + 6 + 2, four tax tiles, audits, closes, notices, 3 running
//   a2    a, with "Your returns 6" below the bands
//   b–e   Margaret, Samuel, Kevin and Grace (spec-only role states)
//   f     the counts read 0: "Nothing waiting on you."
//   g     the home read and the counts never answer: skeleton tiles and rows, aria-busy
//   h, i  Hannah and Marcus at 12:40 PM (their R2 bands are I-01-T24's)

const TAX_TILES = ["prepared", "in_review", "action_required", "approved"] as const;

export interface HOME01Props {
  /** The firm toolbar, when the screen draws its own frame (the gallery); routed, the app's
   * shell holds the toolbar and the screen renders bare. */
  toolbar?: ToolbarProps;
  height?: number;
  /** The office the chip opens on (the office-denver interaction). */
  initialOffice?: string | null;
  /** Where a Waiting-on-you row goes; undefined while the target is planned (DV-3). */
  hrefOf?: (gate: HumanGateOut) => string | undefined;
}

/** Morning until noon in the firm's zone ("Good morning" at 9:24 AM, "Good afternoon" at 12:40 PM). */
function isMorning(now: Date, tz: string): boolean {
  return time(now, { tz }).endsWith("AM");
}

function statusN(tile: HomeTileOut, code: string): number {
  return tile.by_status.find((s) => s.code === code)?.n ?? 0;
}

type OfficeName = (id: string) => string;

/** I-01-T11: a tile with an office breakdown opens a 266 px popover listing it, by click or by
 * keyboard (Enter or Space on the tile; Escape closes it and returns focus). */
function ByOffice({
  tile,
  name,
  label,
  href,
  n,
  children,
}: {
  tile: HomeTileOut;
  name: OfficeName;
  label: string;
  /** Where the tile opens (HOME-01 R3: a tax tile opens TAX-01 filtered by its status). */
  href?: string | undefined;
  /** The tile's own number, for the popover's All offices line. */
  n?: number;
  children: ReactNode;
}): JSX.Element {
  if (tile.by_office.length === 0) {
    return href === undefined ? (
      <>{children}</>
    ) : (
      <a
        href={href}
        data-home="tile-link"
        className="block rounded-dialog focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {children}
      </a>
    );
  }
  return (
    <Popover
      width={266}
      align="start"
      label={COPY.byOffice.label(label)}
      trigger={
        <button
          type="button"
          data-home="tile-office"
          aria-label={COPY.byOffice.label(label)}
          className="block rounded-dialog text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {children}
        </button>
      }
    >
      <ul className="flex flex-col gap-[6px]">
        {tile.by_office.map((o) => (
          <li key={o.office_id} className="text-body tabular-nums">
            {COPY.byOffice.row(name(o.office_id), o.n)}
          </li>
        ))}
      </ul>
      {href !== undefined && n !== undefined && (
        <a
          href={href}
          data-home="tile-link"
          className="mt-[8px] block text-body font-medium tabular-nums hover:underline"
        >
          {COPY.byOffice.row(COPY.office.all, n)}
        </a>
      )}
    </Popover>
  );
}

/** The tile row: one tile per registered home count; an unregistered key has none (AC3.1). */
function Tiles({ home, name }: { home: HomeOut; name: OfficeName }): JSX.Element {
  return (
    <>
      {home.tiles.flatMap((tile) => {
        if (tile.key === "returns") {
          return TAX_TILES.map((code) => (
            <ByOffice
              key={`returns:${code}`}
              tile={tile}
              name={name}
              label={COPY.tiles.tax[code]}
              href={linkOf(to.TAX01(), { tile: code })}
              n={statusN(tile, code)}
            >
              <DashTile
                kind="single"
                value={String(statusN(tile, code))}
                label={COPY.tiles.tax[code]}
                variant={status("return", code).variant ?? "neutral"}
              />
            </ByOffice>
          ));
        }
        if (tile.key === "audits") {
          const phases = Object.keys(
            COPY.tiles.auditPhases,
          ) as (keyof typeof COPY.tiles.auditPhases)[];
          return [
            <ByOffice key="audits" tile={tile} name={name} label={COPY.tiles.audits(tile.total)}>
              <DashTile
                kind="group"
                width={360}
                title={COPY.tiles.audits(tile.total)}
                counts={phases.map((p) => ({
                  value: String(statusN(tile, p)),
                  label: COPY.tiles.auditPhases[p],
                }))}
              />
            </ByOffice>,
          ];
        }
        if (tile.key === "closes") {
          return [
            <DashTile
              key="closes"
              kind="meter"
              value={String(statusN(tile, "in_progress"))}
              pill={{
                label: COPY.tiles.closesPill,
                variant: status("close", "in_progress").variant ?? "amber",
              }}
              caption={COPY.tiles.closesCaption(tile.total)}
            />,
          ];
        }
        if (tile.key === "notices") {
          const fresh = statusN(tile, "received");
          return [
            <DashTile
              key="notices"
              kind="meter"
              value={String(tile.total)}
              {...(fresh > 0
                ? {
                    pill: {
                      label: COPY.tiles.noticesNew(fresh),
                      variant: status("notice", "received").variant ?? "red-tint",
                    },
                  }
                : {})}
              caption={COPY.tiles.noticesCaption}
            />,
          ];
        }
        const label = (COPY.tiles.admin as Record<string, string>)[tile.key];
        return label === undefined
          ? []
          : [
              <ByOffice key={tile.key} tile={tile} name={name} label={label}>
                <DashTile kind="stat" value={String(tile.total)} caption={label} />
              </ByOffice>,
            ];
      })}
    </>
  );
}

function YourWork({ work }: { work: NonNullable<HomeOut["your_work"]> }): JSX.Element {
  const title = COPY.yourWork[work.label] ?? "";
  return (
    <section aria-label={title} data-home="your-work">
      <h3 className="-mt-[0.5px] flex h-[31px] items-center gap-[8px] bg-band-hd px-[14px] text-body font-medium hairline-t hairline-b">
        <span className="min-w-0 flex-1 truncate">{title}</span>
        <span className="text-dense font-normal text-ink-3 tabular-nums">{work.rows.length}</span>
      </h3>
      <ul>
        {work.rows.map((row) => (
          <li
            key={row.work_item_id}
            className="flex min-h-[38px] items-center gap-[10px] px-[14px] hairline-b"
          >
            <span className="min-w-0 flex-1 truncate text-body">{`${row.name} · ${row.client}`}</span>
            {row.tags.map((tag) => (
              <span key={tag} className="text-meta text-ink-3">
                {tag}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Deadlines({ home, now }: { home: HomeOut; now: Date }): JSX.Element {
  const on = (iso: string): string => date(iso, { now });
  const next = home.deadlines.next;
  return (
    <div className="flex flex-col">
      <ul>
        {home.deadlines.rows.map((row) => (
          <DeadlineRow
            key={row.work_item_id}
            date={on(row.due_on)}
            dateTone={row.risk === "due_soon" || row.risk === "overdue" ? "red" : "plain"}
            client={row.client}
            form={row.filing_label}
          />
        ))}
      </ul>
      {next !== null && (
        <p className="px-[12px] py-[10px] text-dense text-ink-3">
          {COPY.next(on(next.due_on), next.client, next.filing_label)}
        </p>
      )}
    </div>
  );
}

/** The activity glyph by code: I-01-T12's allowlist, plus the mail and envelope rows S29 adds
 * (I-01-T23; fixture content until then). */
const ACTIVITY_ICON: Readonly<Record<string, IconName>> = {
  client_upload: "upload",
  follow_up_sent: "send",
  letter_recorded: "file",
  agent_pre_screen: "bot",
  inbound_mail: "mail",
  envelope_sent: "send",
};

type ActivityItem = HomeOut["client_activity"][number];

/** A row's two lines from its code, labels and facts (DEC-1001): codes and counts on the wire,
 * names resolved by the reader now. */
export function activityLines(
  row: ActivityItem,
  viewer: string | null,
  now: Date,
): { text: string; context: string } {
  const a = COPY.activity;
  const labels = row.labels ?? {};
  const facts = row.facts;
  const actor =
    row.actor.type === "user" && row.actor.id !== null && row.actor.id === viewer
      ? a.you
      : (row.actor.label ?? a.someone);
  const docClass = typeof facts.document_class === "string" ? facts.document_class : "";
  const [one, many] = a.documents[docClass] ?? ["", ""];
  const count = typeof facts.count === "number" ? facts.count : 0;
  const subject = labels.subject ?? "";
  let text: string;
  let context = labels.context ?? "";
  switch (row.event_type) {
    case "inbound_mail":
      text = a.mailed(
        actor,
        count > 1 && many !== "" ? a.counted(count, many) : a.quoted(subject),
      );
      break;
    case "envelope_sent":
      text = a.sent(actor, one, subject, labels.recipient ?? "");
      if (typeof facts.due_on === "string") context = a.envelope(date(facts.due_on, { now }));
      break;
    case "agent_pre_screen":
      text = a.preScreened(actor, row.client_label);
      if (typeof facts.flags === "number") context = a.flags(facts.flags);
      break;
    case "client_upload":
      text = a.uploaded(actor, subject);
      break;
    case "follow_up_sent":
      text = a.followUpSent(actor);
      break;
    case "letter_recorded":
      text = a.letterRecorded;
      break;
    default:
      text = row.client_label;
  }
  return { text, context: context === "" ? row.client_label : context };
}

function Activity({
  home,
  tz,
  now,
  viewer,
}: {
  home: HomeOut;
  tz: string | undefined;
  now: Date;
  viewer: string | null;
}): JSX.Element | null {
  if (home.client_activity.length === 0) return null;
  const today = date(now.toISOString(), { now, ...(tz === undefined ? {} : { tz }) });
  return (
    <ul data-home="activity">
      {home.client_activity.map((row) => {
        const at = new Date(row.occurred_at);
        const day = date(row.occurred_at, { now, ...(tz === undefined ? {} : { tz }) });
        const lines = activityLines(row, viewer, now);
        return (
          <ActivityRow
            key={row.id}
            icon={ACTIVITY_ICON[row.event_type] ?? "file"}
            text={lines.text}
            context={lines.context}
            when={day === today ? time(at, tz === undefined ? {} : { tz }) : day}
          />
        );
      })}
    </ul>
  );
}

export interface HomeQueueProps {
  counts: HumanGateCountsOut;
  gates: readonly HumanGateOut[];
  office: string | null;
  hrefOf?: (gate: HumanGateOut) => string | undefined;
  work: HomeOut["your_work"] | undefined;
}

function Queue({ counts, gates, office, hrefOf, work }: HomeQueueProps): JSX.Element {
  const now = useNow();
  const today = useToday();
  const tz = useSession().tz ?? undefined;
  const mine = gates.filter((g) => office === null || g.office_id === office);
  return (
    <>
      {counts.total === 0 ? (
        <QueueEmpty title={COPY.empty.title}>{COPY.empty.body}</QueueEmpty>
      ) : (
        <WaitingOnYou
          counts={counts}
          gates={mine}
          today={today}
          now={now}
          {...(tz === undefined ? {} : { tz })}
          {...(hrefOf === undefined ? {} : { hrefOf })}
        />
      )}
      {work != null && work.rows.length > 0 && <YourWork work={work} />}
    </>
  );
}

export function HOME01({
  toolbar,
  height,
  initialOffice = null,
  hrefOf = hostHref,
}: HOME01Props): JSX.Element {
  const [office, setOffice] = useState<string | null>(initialOffice);
  const session = useSession();
  const me = useQuery(meOptions()).data;
  // I-01-T11 (DEC-649): the person's default office (`/v1/me`) heads the chip's list; Home opens
  // on all offices, as E0 shows it, and the chip's amber state marks a chosen office.
  const preferred = me?.default_office_id ?? null;
  const offices = [...(me?.offices ?? [])].sort(
    (a, b) => Number(b.id === preferred) - Number(a.id === preferred),
  );
  const officeLabel = (id: string): string =>
    offices.find((o) => o.id === id)?.name ?? COPY.byOffice.unnamed;
  const home = useHome(office);
  const counts = useGateCounts(office);
  const list = useWaitingOnYou();
  const now = useNow();
  const briefOn = useFlag("today_brief.enabled") === true;
  const tz = session.tz ?? "America/Chicago";
  const open = useOpenHref();
  const loading = home.isPending || counts.isPending;
  const view = home.data;
  const greetingName = view?.greeting.first_name ?? "";
  const greeting = isMorning(now, tz)
    ? COPY.greeting.morning(greetingName)
    : COPY.greeting.afternoon(greetingName);
  const officeName = offices.find((o) => o.id === office)?.name ?? null;
  const returns = view?.tiles.find((t) => t.key === "returns");
  const caption =
    returns === undefined
      ? undefined
      : officeName === null
        ? COPY.tiles.taxCaption(returns.total)
        : COPY.tiles.taxOfficeCaption(officeName, returns.total);
  const total = counts.data?.total;
  const subbar = (
    <>
      {briefOn && PLANNED_VISIBLE && (
        <span
          data-home="open-today"
          className="inline-flex items-center gap-[6px] text-body font-medium"
        >
          {COPY.openToday}
          <Icon name="arrow-right" size={12} className="text-ink-3" />
        </span>
      )}
      <span className="ml-[12px]">
        <HomeSegmented
          total={total}
          segments={view?.segments}
          onChange={(label) => {
            if (label === HOME_SEGMENTS.approvals) open(linkOf(to.HOME02()));
          }}
        />
      </span>
    </>
  );
  const queueBody = counts.isError ? (
    <ErrorState noun={COPY.error.queue} onRetry={() => void counts.refetch()} />
  ) : counts.data === undefined ? null : (
    <Queue
      counts={counts.data}
      gates={list.data?.items ?? []}
      office={office}
      hrefOf={hrefOf}
      work={view?.your_work}
    />
  );
  return (
    <DashboardLayout
      {...(toolbar === undefined
        ? { bare: true, toolbar: { nav: [], active: "Home", firm: "" } }
        : { toolbar, embedded: true })}
      {...(height === undefined ? {} : { height })}
      greeting={greeting}
      date={view === undefined ? "" : weekdayDate(view.greeting.date, { now, tz })}
      {...(caption === undefined ? {} : { caption })}
      subbar={subbar}
      office={{
        label: COPY.office.label,
        options: offices.map((o) => o.name),
        value: officeName,
        allLabel: COPY.office.all,
        onChange: (name) => {
          setOffice(offices.find((o) => o.name === name)?.id ?? null);
        },
      }}
      {...(view?.running_count == null ? {} : { running: COPY.running(view.running_count) })}
      loading={loading}
      tiles={
        home.isError ? (
          <ErrorState noun={COPY.error.tiles} onRetry={() => void home.refetch()} />
        ) : view === undefined ? null : (
          <Tiles home={view} name={officeLabel} />
        )
      }
      queue={{
        title: COPY.pane.title,
        ...(total === undefined || total === 0 ? {} : { count: total }),
        ...(PLANNED_VISIBLE
          ? {
              action: (
                <span
                  data-home="open-queue"
                  aria-disabled="true"
                  className="inline-flex items-center gap-[6px] text-body text-ink-2"
                >
                  {COPY.pane.openQueue}
                  <Icon name="arrow-right" size={12} className="text-ink-3" />
                </span>
              ),
            }
          : {}),
        children: queueBody,
      }}
      side={[
        {
          title: COPY.deadlines.title,
          children: view === undefined ? null : <Deadlines home={view} now={now} />,
        },
        {
          title: COPY.activity.title,
          children:
            view === undefined ? null : (
              <Activity home={view} tz={tz} now={now} viewer={session.user?.id ?? null} />
            ),
        },
      ]}
      sideTopHeight={334}
    />
  );
}
