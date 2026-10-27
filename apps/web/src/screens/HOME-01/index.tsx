import type { HomeOut, HomeTileOut, HumanGateCountsOut, HumanGateOut } from "@abacus/api-client";
import {
  DashTile,
  DashboardLayout,
  DeadlineRow,
  ErrorState,
  Icon,
  QueueEmpty,
  type ToolbarProps,
  date,
  status,
} from "@abacus/ui";
import { meOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow, useToday } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  HomeSegmented,
  WaitingOnYou,
  useGateCounts,
  useHome,
  useWaitingOnYou,
} from "../../domain/home";
import { to } from "../../routes/to";
import { COPY } from "./copy";

// HOME-01 · Home dashboard, the main region (I-01-T06; docs/screens/HOME-01.md). T11
// DashboardLayout: the subbar (greeting and date, "Open Today →" behind `today_brief.enabled`, the
// Home segmented with the Approvals count, the Office chip and the running pill), the tile row,
// and "Waiting on you" with its summary, bands and rows. The pane header's count, the summary line
// and the Approvals badge all read the one counts response (`GET /v1/human-gates/counts`); the rows
// come from the list beside it. No row renders a gate verb: a row opens where its gate is decided.
// The right column (deadlines, client activity) is I-01-T11's and T12's; it draws the deadlines
// the home read model already carries.
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

function pathOf(target: { to: string; params: Readonly<Record<string, string>> }): string {
  return target.to.replace(/\$(\w+)/gu, (_m, name: string) =>
    encodeURIComponent(target.params[name] ?? ""),
  );
}

/** Where a row opens while `home.approvals` is off (DV-3): its host gate, when that screen is
 * built; HOME-02 and the other hosts are planned, so their rows stay plain text. */
function hostHref(gate: HumanGateOut): string | undefined {
  if (
    gate.subkind === "acceptance_decision_due" &&
    gate.client_id !== null &&
    gate.engagement_id !== null
  ) {
    return pathOf(to.CLI07({ clientId: gate.client_id, engagementId: gate.engagement_id }));
  }
  return undefined;
}

function longDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
}

function hourIn(now: Date, tz: string): number {
  return Number(
    new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone: tz }).format(
      now,
    ),
  );
}

function statusN(tile: HomeTileOut, code: string): number {
  return tile.by_status.find((s) => s.code === code)?.n ?? 0;
}

/** The tile row: one tile per registered home count; an unregistered key has none (AC3.1). */
function Tiles({ home }: { home: HomeOut }): JSX.Element {
  return (
    <>
      {home.tiles.flatMap((tile) => {
        if (tile.key === "returns") {
          return TAX_TILES.map((code) => (
            <DashTile
              key={`returns:${code}`}
              kind="single"
              value={String(statusN(tile, code))}
              label={COPY.tiles.tax[code]}
              variant={status("return", code).variant ?? "neutral"}
            />
          ));
        }
        if (tile.key === "audits") {
          const phases = Object.keys(
            COPY.tiles.auditPhases,
          ) as (keyof typeof COPY.tiles.auditPhases)[];
          return [
            <DashTile
              key="audits"
              kind="group"
              width={360}
              title={COPY.tiles.audits(tile.total)}
              counts={phases.map((p) => ({
                value: String(statusN(tile, p)),
                label: COPY.tiles.auditPhases[p],
              }))}
            />,
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
          : [<DashTile key={tile.key} kind="stat" value={String(tile.total)} caption={label} />];
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
  const offices = useQuery(meOptions()).data?.offices ?? [];
  const home = useHome(office);
  const counts = useGateCounts(office);
  const list = useWaitingOnYou();
  const now = useNow();
  const briefOn = useFlag("today_brief.enabled") === true;
  const tz = session.tz ?? "America/Chicago";
  const loading = home.isPending || counts.isPending;
  const view = home.data;
  const greetingName = view?.greeting.first_name ?? "";
  const greeting =
    hourIn(now, tz) < 12
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
        <HomeSegmented total={total} segments={view?.segments} />
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
      {...(hrefOf === undefined ? {} : { hrefOf })}
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
      date={view === undefined ? "" : longDate(view.greeting.date)}
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
          <Tiles home={view} />
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
        { title: COPY.activity.title, children: null },
      ]}
      sideTopHeight={334}
    />
  );
}
