import type {
  ClientOverviewItemOut,
  ClientOverviewOut,
  ClientOverviewSectionOut,
  ClientRecordOut,
  ClientRelationshipOut,
} from "@abacus/api-client";
import { clientRelationshipsOptions } from "@abacus/api-client/query";
import {
  AppShell,
  Button,
  Count,
  DASH,
  DEFAULT_TZ,
  Icon,
  IconButton,
  KvRowView,
  type KvRow,
  Menu,
  Pill,
  RecordBand,
  RecordCockpit,
  type RegistryObject,
  StatRow,
  StatusDisc,
  StatusPill,
  Tabsbar,
  Timeline,
  type ToolbarProps,
  type ViewState,
  count,
  date,
  sameDay,
  status,
  time,
  toast,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  MaskedTin,
  daysUntil,
  givenName,
  itemOf,
  patchOf,
  sectionOf,
  statItems,
  sumFigures,
  tinEntity,
  useClientOverview,
  useClientRecord,
  useStaff,
  useUpdateClient,
} from "../../domain/clients";
import { CLI04, type Cli04Open } from "../CLI-04";
import { COPY } from "./copy";

// CLI-02 · Client record · Overview (P-07-T19; docs/screens/CLI-02.md). T2 without the dock (the
// SHL-13 dock host is P-09's) over `GET /v1/clients/{id}` and `/overview`: the subbar, the tabs,
// the Summary rail (name block with the engagements menu, stat rows, Details with the masked TIN
// and Reveal, Team with the relationship-partner picker, Client Portal, Links) and the overview
// cards the registered sections return. Each artboard is its data (fixtures/scenarios/CLI-02.ts):
//
//   a, a2  Ridgeline (business)   b  Feld (household)   c  Northwind (plan sponsor)
//   e      Copperleaf, no engagements: "No engagements yet."
//   f      Granite Peak with the `insights` entitlement: the Client responsiveness card
//
// A walled or unknown client is a 404: the record cannot be opened and nothing says why (INV-3).
// Planned targets (CLI-04, CLI-05, CLI-07, CLI-08, ENG-01, ENG-03, FIL-01, INB-04, INS-05, BND-04,
// TAX-02, TXP-10, TXP-12, HOME-03) are hidden in production and disabled with their hint elsewhere.

export type Cli02Tab = "overview" | "engagements" | "relationships" | "contacts";

/** Where a CLI-02 control goes: a `to.<ID>()` link the route navigates to. */
export type Cli02Target =
  | { screen: "CLI-01" }
  | { screen: "ENG-02"; engagementId: string }
  | { screen: "BND-02"; binderId: string };

export interface CLI02Props {
  clientId: string;
  tab: Cli02Tab;
  onTab: (tab: Cli02Tab) => void;
  onNavigate?: (target: Cli02Target) => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
  /** CLI-04's artboards: the overlay the contacts tab opens on (the gallery only). */
  contactsOpen?: Cli04Open | undefined;
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** "12-31" → "December 31". */
function fiscalYearEnd(md: string | null | undefined): string {
  if (md == null) return DASH;
  const [m, d] = md.split("-").map(Number);
  const month = MONTHS[(m ?? 0) - 1];
  return month === undefined || d === undefined ? DASH : `${month} ${String(d)}`;
}

function notFound(error: unknown): boolean {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" && detail.replace(" ", "_") === "not_found";
}

/** An overview item's pill: its own object's word from the status registry. */
export function ItemPill({ item }: { item: ClientOverviewItemOut }): JSX.Element | null {
  if (item.pill_object == null || item.pill_code == null) return null;
  const resolved = status(item.pill_object as RegistryObject, item.pill_code as never);
  return <StatusPill variant={resolved.variant ?? "neutral"}>{resolved.label}</StatusPill>;
}

/** A planned control: drawn disabled with its "Opens …" hint outside production, absent in it. */
function Planned({ children }: { children: ReactNode }): JSX.Element | null {
  return PLANNED_VISIBLE ? <>{children}</> : null;
}

const ROW =
  "flex min-h-[33px] w-full items-center gap-[8px] px-[12px] py-[5px] text-body hairline-b";

function Card({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-pane bg-card shadow-e1">
      <h3 className="flex h-[34px] items-center px-[14px] text-section font-medium hairline-b">
        {title}
      </h3>
      {children}
    </section>
  );
}

// ---- subbar -------------------------------------------------------------------------------------

function Subbar({
  record,
  partner,
  onBack,
}: {
  record: ClientRecordOut | undefined;
  partner: string | undefined;
  onBack?: () => void;
}): JSX.Element {
  const primary = record?.entities[0];
  const kind =
    record?.kind == null
      ? undefined
      : record.kind === "business"
        ? (COPY.entityKind[primary?.entity_type ?? ""] ?? COPY.kind.business)
        : COPY.kind[record.kind];
  return (
    <div
      data-shell="record-header"
      data-variant="client"
      className="relative flex h-(--subbar-h) flex-none items-center gap-[8px] px-(--edge-app)"
    >
      <Button variant="secondary" size="sm" title={COPY.backHint} onClick={onBack}>
        {COPY.back}
      </Button>
      {record !== undefined && (
        <h1 className="absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-[8px] text-title font-medium tracking-[-0.012em] whitespace-nowrap">
          {record.name}
          {kind !== undefined && (
            <Pill variant="neutral" size="state">
              {kind}
            </Pill>
          )}
          {record.is_attest_client && record.kind === "plan_sponsor" && (
            <Pill variant="tag" size="state">
              {COPY.attest}
            </Pill>
          )}
          {record.risk_tier != null && (
            <Pill variant="amber" size="state">
              {COPY.risk[record.risk_tier]}
            </Pill>
          )}
        </h1>
      )}
      <div className="ml-auto flex items-center gap-[8px]">
        {record !== undefined && partner !== undefined && (
          <span className="text-body text-ink-3">
            {COPY.partnerMeta(partner, record.office_name ?? DASH)}
          </span>
        )}
        <IconButton icon="ellipsis" label={COPY.more} variant="white" disabled />
      </div>
    </div>
  );
}

// ---- rail ---------------------------------------------------------------------------------------

function statValue(item: ClientOverviewItemOut, of: string | null, now: Date, tz: string): string {
  if (item.figure != null) {
    return of === null ? count(item.figure) : COPY.stat.of(count(item.figure), count(of));
  }
  if (item.pill_object != null && item.pill_code != null) {
    return status(item.pill_object as RegistryObject, item.pill_code as never).label;
  }
  if (item.on != null) {
    return item.key === "days_to_due"
      ? COPY.stat.days(daysUntil(item.on, now, tz))
      : date(`${item.on}T12:00:00Z`, { now, tz });
  }
  return item.text ?? DASH;
}

function TinRow({
  label,
  record,
}: {
  label: string;
  record: ClientRecordOut;
}): JSX.Element | null {
  const entity = tinEntity(record);
  if (entity === undefined) return null;
  const individual = entity.tin?.kind !== "ein";
  return (
    <div data-record="kv" data-kind="tin" className={ROW}>
      <span className="text-ink-2">{label}</span>
      <span className="ml-auto min-w-0">
        <MaskedTin
          entity={entity}
          canReveal={(record.allowed_actions ?? []).includes("tin.reveal")}
          {...(individual ? { suffix: `(${givenName(entity)})` } : {})}
        />
      </span>
    </div>
  );
}

function Rail({
  record,
  overview,
  now,
  tz,
  onNavigate,
  onTab,
}: {
  record: ClientRecordOut;
  overview: ClientOverviewOut | undefined;
  now: Date;
  tz: string;
  onNavigate?: ((target: Cli02Target) => void) | undefined;
  onTab: (tab: Cli02Tab) => void;
}): JSX.Element {
  const staff = useStaff();
  const update = useUpdateClient(record.id);
  const nameOf = (id: string | null | undefined): string | undefined =>
    id == null ? undefined : staff.names.get(id);
  const engagements = record.active_engagements ?? [];
  const profile = sectionOf(overview, "profile");
  const portal = sectionOf(overview, "portal");
  const links = sectionOf(overview, "links");
  const stats = statItems(sectionOf(overview, "stats"));
  const canUpdate = (record.allowed_actions ?? []).includes("client.update");

  const detailRows: KvRow[] = [];
  const profileText = (key: string): void => {
    const item = itemOf(profile, key);
    if (item?.text == null) return;
    const label = (COPY.details as Record<string, string>)[key] ?? key;
    detailRows.push({ id: key, label, value: item.text });
  };
  if (record.kind === "business" || record.kind === "nonprofit") {
    detailRows.push({
      id: "fye",
      label: COPY.details.fiscalYearEnd,
      value: fiscalYearEnd(record.entities[0]?.fye_month_day),
    });
    profileText("accounting_method");
    detailRows.push({
      id: "attest",
      label: COPY.details.attest,
      value: record.is_attest_client ? COPY.details.yes : COPY.details.no,
    });
    detailRows.push({
      id: "office",
      label: COPY.details.office,
      value: record.office_name ?? DASH,
    });
  } else {
    for (const item of profile?.items ?? []) profileText(item.key);
  }

  const partnerName = nameOf(record.relationship_partner_id) ?? DASH;
  const people = staff.ids.flatMap((id) => {
    const n = staff.names.get(id);
    return n === undefined ? [] : [n];
  });
  const assignPartner = async (name: string): Promise<void> => {
    const id = staff.ids.find((i) => staff.names.get(i) === name);
    if (id === undefined) return;
    try {
      await update.mutateAsync(patchOf(record, { relationship_partner_id: id }));
      toast.show({ kind: "success", text: COPY.partnerSaved });
    } catch (error) {
      const detail = (error as { detail?: unknown } | null)?.detail;
      toast.show({
        kind: "error",
        text: detail === "stale_version" ? COPY.partnerStale : COPY.partnerFailed,
      });
    }
  };
  const teamRows: KvRow[] = [
    {
      id: "partner",
      label: COPY.team.partner,
      value: partnerName,
      ...(canUpdate ? { kind: "person" as const } : {}),
    },
    ...(record.manager_user_ids ?? []).slice(0, 1).map((id) => ({
      id: "manager",
      label: COPY.team.manager,
      value: nameOf(id) ?? DASH,
    })),
    ...(record.preparer_user_ids ?? []).slice(0, 1).map((id) => ({
      id: "preparer",
      label: COPY.team.preparer,
      value: nameOf(id) ?? DASH,
    })),
  ];

  const contact = itemOf(portal, "contact")?.text;
  const email = itemOf(portal, "email")?.text;
  const requests = itemOf(portal, "requests")?.figure;
  const portalWord = status("invitation", record.portal_status);
  const binder = itemOf(links, "binder");
  const relationships = record.tab_counts.relationships;

  return (
    <section
      aria-label={COPY.rail.title}
      className="pane flex min-h-0 flex-1 flex-col overflow-hidden"
    >
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail.title}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="flex flex-col items-center px-[12px] pt-[14px] pb-[12px] text-center hairline-b">
          <p className="text-section font-medium">{record.name}</p>
          {record.descriptor != null && (
            <p className="mt-[2px] text-meta text-ink-3">{record.descriptor}</p>
          )}
          {engagements.length > 0 && (
            <span className="mt-[8px]">
              <Menu
                label={COPY.rail.engagementsMenu}
                align="start"
                width={280}
                trigger={
                  <button type="button" className="rounded-pill">
                    <Pill variant="neutral" size="state">
                      {COPY.rail.engagementsPill(engagements.length)}
                    </Pill>
                  </button>
                }
                sections={[
                  engagements.map((e) => ({
                    label: e.name,
                    onSelect: () => {
                      onNavigate?.({ screen: "ENG-02", engagementId: e.id });
                    },
                  })),
                ]}
              />
            </span>
          )}
        </div>
        {stats.map(({ item, of }) => (
          <StatRow
            key={item.key}
            stat={{
              id: item.key,
              value: statValue(item, of, now, tz),
              caption: item.text ?? "",
            }}
          />
        ))}
        <RecordBand title={COPY.rail.bands.details} />
        {(record.kind === "business" || record.kind === "nonprofit") && (
          <TinRow label={COPY.details.ein} record={record} />
        )}
        {record.kind === "household" && <TinRow label={COPY.details.ssns} record={record} />}
        {detailRows.map((row) => (
          <KvRowView key={row.id} row={row} />
        ))}
        <RecordBand title={COPY.rail.bands.team} />
        {teamRows.map((row) => (
          <KvRowView
            key={row.id}
            row={row}
            people={people}
            onAssign={(_row, name) => void assignPartner(name)}
          />
        ))}
        <RecordBand title={COPY.rail.bands.portal} />
        {contact != null && (
          <KvRowView row={{ id: "contact", label: COPY.portal.contact, value: contact }} />
        )}
        {email != null && (
          <KvRowView row={{ id: "email", label: COPY.portal.email, value: email }} />
        )}
        <div data-record="kv" data-kind="status" className={ROW}>
          <span className="text-ink-2">{COPY.portal.status}</span>
          <span className="ml-auto">
            <StatusPill variant={portalWord.variant ?? "neutral"}>{portalWord.label}</StatusPill>
          </span>
        </div>
        {record.tab_counts.contacts != null && record.tab_counts.contacts > 0 && (
          <Planned>
            <div
              data-record="kv"
              data-kind="link"
              className={ROW}
              title={COPY.portal.identitiesHint}
            >
              <span className="text-ink-2">{COPY.portal.portal}</span>
              <span className="ml-auto text-ink">
                {COPY.portal.identities(count(String(record.tab_counts.contacts)))}
              </span>
              <Icon name="arrow-right" size={12} className="text-ink-3" />
            </div>
          </Planned>
        )}
        {requests != null && (
          <KvRowView
            row={{
              id: "requests",
              label: COPY.portal.requests,
              value: COPY.portal.pending(count(requests)),
            }}
          />
        )}
        <RecordBand title={COPY.rail.bands.links} />
        <KvRowView
          row={{
            id: "entities",
            label: COPY.links.entities,
            value: count(String(record.entities.length)),
            kind: "link",
            trail: "arrow",
          }}
          onOpen={() => {
            onTab("relationships");
          }}
        />
        <KvRowView
          row={{
            id: "relationships",
            label: COPY.links.relationships,
            value: COPY.links.parties(count(String(relationships))),
            kind: "link",
            trail: "arrow",
          }}
          onOpen={() => {
            onTab("relationships");
          }}
        />
        <Planned>
          <div data-record="kv" data-kind="link" className={ROW} title={COPY.links.filesHint}>
            <span className="text-ink-2">{COPY.links.files}</span>
            <span className="ml-auto min-w-0 truncate text-ink">
              {COPY.links.filesOf(record.name)}
            </span>
            <Icon name="arrow-right" size={12} className="text-ink-3" />
          </div>
        </Planned>
        {binder?.text != null && binder.ref != null && (
          <KvRowView
            row={{
              id: "binder",
              label: COPY.links.binder,
              value: binder.text,
              kind: "link",
              trail: "arrow",
            }}
            onOpen={() => {
              if (binder.ref != null) onNavigate?.({ screen: "BND-02", binderId: binder.ref.id });
            }}
          />
        )}
        {record.tab_counts.messages != null && (
          <Planned>
            <div data-record="kv" data-kind="link" className={ROW} title={COPY.links.messagesHint}>
              <span className="text-ink-2">{COPY.links.messages}</span>
              <span className="ml-auto text-ink">
                {COPY.links.unread(count(String(record.tab_counts.messages)))}
              </span>
              <Icon name="arrow-right" size={12} className="text-ink-3" />
            </div>
          </Planned>
        )}
      </div>
    </section>
  );
}

// ---- canvas cards -------------------------------------------------------------------------------

const RUNNING = new Set(["active", "in_review", "preparing", "gathering", "processing"]);

function WorkRow({
  item,
  onOpen,
}: {
  item: ClientOverviewItemOut;
  onOpen?: (() => void) | undefined;
}): JSX.Element {
  const disc = RUNNING.has(item.pill_code ?? "") ? "half" : "todo";
  const body = (
    <>
      <StatusDisc state={disc} />
      <span className="min-w-0 flex-1 truncate text-body font-medium">{item.text}</span>
      <ItemPill item={item} />
      {item.figure != null && (
        <Count
          value={Number(item.figure)}
          tone="bad"
          aria-label={COPY.card.openIssues(count(item.figure))}
        />
      )}
      <Icon name="chevron-right" size={12} className="text-ink-3" />
    </>
  );
  const classes = "flex h-[52px] w-full items-center gap-[10px] px-[14px] text-left hairline-b";
  return onOpen === undefined ? (
    <div data-row="work" className={classes}>
      {body}
    </div>
  ) : (
    <button
      type="button"
      data-row="work"
      className={`${classes} hover:bg-nested`}
      onClick={onOpen}
    >
      {body}
    </button>
  );
}

function K1Table({ section }: { section: ClientOverviewSectionOut }): JSX.Element {
  const rows = section.items.filter((i) => i.key === "k1_package");
  const total = sumFigures(rows.map((r) => r.figure ?? "0"));
  const th = "h-[28px] bg-band-hd px-[10px] text-meta font-medium text-ink-3";
  return (
    <div className="m-[10px] overflow-hidden rounded-tile inset-shadow-hair">
      <p className="px-[10px] py-[6px] text-meta font-medium">{COPY.card.k1}</p>
      <table className="w-full text-cell tabular-nums">
        <thead>
          <tr>
            <th className={`${th} text-left`}>{COPY.card.k1Columns.recipient}</th>
            <th className={`${th} text-right`}>{COPY.card.k1Columns.box2}</th>
            <th className={`${th} text-left`}>{COPY.card.k1Columns.status}</th>
            <th className={`${th} text-left`}>{COPY.card.k1Columns.feeds}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.text} className="h-[30px] hairline-t">
              <td className="px-[10px]">{r.text}</td>
              <td className="px-[10px] text-right">{count(r.figure ?? "0")}</td>
              <td className="px-[10px]">
                <ItemPill item={r} />
              </td>
              <td className="px-[10px]">
                {r.ref == null ? (
                  <span className="text-ink-4">{DASH}</span>
                ) : (
                  <span
                    title={COPY.card.feedsHint}
                    className="inline-flex items-center text-ink-3"
                  >
                    <Icon name="arrow-right" size={12} />
                    <span className="sr-only">{COPY.card.feedsHint}</span>
                  </span>
                )}
              </td>
            </tr>
          ))}
          <tr className="h-[30px] font-medium hairline-t">
            <td className="px-[10px]">{COPY.card.k1Total}</td>
            <td data-total="schedule-k" className="px-[10px] text-right">
              {count(total)}
            </td>
            <td />
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function ActiveWork({
  overview,
  onNavigate,
}: {
  overview: ClientOverviewOut;
  onNavigate?: ((target: Cli02Target) => void) | undefined;
}): JSX.Element | null {
  const work = sectionOf(overview, "work_items");
  const engagements = sectionOf(overview, "engagements");
  const k1 = sectionOf(overview, "k1_packages");
  const rows = work?.items ?? engagements?.items ?? [];
  const received = (k1?.items ?? []).filter((i) => i.key === "k1_received");
  if (rows.length === 0 && received.length === 0) return null;
  return (
    <Card title={COPY.card.activeWork}>
      {rows.map((item) => (
        <WorkRow
          key={`${item.key}:${item.text ?? ""}`}
          item={item}
          {...(item.ref?.type === "engagement"
            ? {
                onOpen: () => {
                  if (item.ref != null)
                    onNavigate?.({ screen: "ENG-02", engagementId: item.ref.id });
                },
              }
            : {})}
        />
      ))}
      {received.map((item) => (
        <div
          key={item.text}
          data-row="k1-received"
          className="flex h-[36px] items-center gap-[8px] px-[14px] text-cell hairline-b"
        >
          <span className="min-w-0 flex-1 truncate text-ink-2">{item.text}</span>
          <span className="tabular-nums">{count(item.figure ?? "0")}</span>
          <ItemPill item={item} />
        </div>
      ))}
      {k1 !== undefined && k1.items.some((i) => i.key === "k1_package") && (
        <K1Table section={k1} />
      )}
    </Card>
  );
}

function Waiting({
  section,
  now,
  tz,
}: {
  section: ClientOverviewSectionOut;
  now: Date;
  tz: string;
}): JSX.Element {
  const total = String(section.total ?? section.items.length);
  return (
    <Card title={COPY.card.waiting(count(total))}>
      {section.items.map((item) => (
        <div
          key={item.text}
          className="flex min-h-[44px] items-center gap-[10px] px-[14px] py-[6px] hairline-b"
        >
          <Icon name="flag" size={12} className="flex-none text-amber" />
          <span className="min-w-0 flex-1 text-body">{item.text}</span>
          {item.at != null && (
            <span className="flex-none text-meta text-ink-3">{date(item.at, { now, tz })}</span>
          )}
        </div>
      ))}
      <Planned>
        <p
          title={COPY.card.waitingHint}
          className="flex items-center gap-[6px] px-[14px] py-[10px] text-cell font-medium text-ink"
        >
          {COPY.card.waitingAll(count(total))}
          <Icon name="arrow-right" size={12} className="text-ink-3" />
        </p>
      </Planned>
    </Card>
  );
}

function Responsiveness({ section }: { section: ClientOverviewSectionOut }): JSX.Element {
  const rate = itemOf(section, "on_time_rate")?.figure ?? null;
  const firm = itemOf(section, "firm_rate")?.figure ?? null;
  const overdue = itemOf(section, "overdue_now")?.figure ?? null;
  const below = rate !== null && firm !== null && Number(rate) < Number(firm);
  const cell = (label: string, value: string | null, bad = false): JSX.Element => (
    <div className="flex h-[64px] flex-1 flex-col justify-center px-[14px]">
      <span className="text-kpi-label text-ink-3 uppercase">{label}</span>
      <span className={`text-title tabular-nums ${bad ? "font-medium text-red-ink" : ""}`}>
        {value === null ? DASH : value}
      </span>
    </div>
  );
  return (
    <Card title={COPY.responsiveness.title}>
      <div className="flex">
        {cell(COPY.responsiveness.onTime, rate === null ? null : `${rate}%`, below)}
        {cell(COPY.responsiveness.firm, firm === null ? null : `${firm}%`)}
        {cell(COPY.responsiveness.overdue, overdue === null ? null : count(overdue))}
      </div>
      {below && (
        <p
          title={COPY.responsiveness.flagHint}
          className="flex items-center gap-[8px] px-[14px] pb-[10px] text-cell text-ink-2"
        >
          <Icon name="flag" size={12} className="text-amber" />
          {COPY.responsiveness.flag}
        </p>
      )}
      <div className="flex min-h-[28px] items-center gap-[12px] px-[14px] py-[6px] text-meta text-ink-3 hairline-t">
        <span className="min-w-0 flex-1">{COPY.responsiveness.footer}</span>
        <Planned>
          <span
            title={COPY.responsiveness.insightsHint}
            className="flex flex-none items-center gap-[4px] text-ink"
          >
            {COPY.responsiveness.insights}
            <Icon name="arrow-right" size={12} className="text-ink-3" />
          </span>
          <span title={COPY.responsiveness.followUpsHint} className="flex-none text-ink">
            {COPY.responsiveness.followUps}
          </span>
        </Planned>
      </div>
    </Card>
  );
}

function KeyDates({
  section,
  now,
  tz,
}: {
  section: ClientOverviewSectionOut;
  now: Date;
  tz: string;
}): JSX.Element {
  return (
    <Card title={COPY.card.keyDates}>
      {section.items.map((item) => (
        <div
          key={`${item.on ?? ""}:${item.text ?? ""}`}
          className="flex min-h-[36px] items-center gap-[12px] px-[14px] py-[6px] hairline-b"
        >
          <span className="w-[96px] flex-none text-cell text-ink-2 tabular-nums">
            {item.on == null ? DASH : date(`${item.on}T12:00:00Z`, { now, tz, withYear: true })}
          </span>
          <span className="min-w-0 flex-1 text-body">{item.text ?? item.figure}</span>
        </div>
      ))}
    </Card>
  );
}

function Recent({
  section,
  now,
  tz,
}: {
  section: ClientOverviewSectionOut;
  now: Date;
  tz: string;
}): JSX.Element {
  return (
    <Timeline
      label={COPY.card.recent}
      className="m-0"
      events={section.items.map((item, i) => ({
        id: `${item.key}:${String(i)}`,
        date:
          item.at == null
            ? DASH
            : sameDay(item.at, now, { tz })
              ? time(item.at, { tz })
              : date(item.at, { now, tz }),
        state: "done",
        title: item.text ?? "",
      }))}
    />
  );
}

function Overview({
  overview,
  now,
  tz,
  onNavigate,
}: {
  overview: ClientOverviewOut;
  now: Date;
  tz: string;
  onNavigate?: ((target: Cli02Target) => void) | undefined;
}): JSX.Element {
  const waiting = sectionOf(overview, "waiting_on_client");
  const responsiveness = sectionOf(overview, "responsiveness");
  const dates = sectionOf(overview, "key_dates");
  const activity = sectionOf(overview, "activity");
  return (
    // The canvas scrolls; its content takes focus so the keyboard can scroll it (WCAG 2.1.1).
    <div
      role="group"
      aria-label={COPY.canvas.title}
      tabIndex={0}
      className="flex flex-col gap-[10px] p-[10px] outline-offset-[-2px]"
    >
      <ActiveWork overview={overview} onNavigate={onNavigate} />
      {waiting !== undefined && <Waiting section={waiting} now={now} tz={tz} />}
      {responsiveness !== undefined && <Responsiveness section={responsiveness} />}
      {dates !== undefined && dates.items.length > 0 && (
        <KeyDates section={dates} now={now} tz={tz} />
      )}
      {activity !== undefined && activity.items.length > 0 && (
        <section aria-label={COPY.card.recent} className="flex flex-col gap-[6px]">
          <h3 className="px-[4px] text-section font-medium">{COPY.card.recent}</h3>
          <Recent section={activity} now={now} tz={tz} />
        </section>
      )}
    </div>
  );
}

const RELATIONSHIP_WORDS: Readonly<Record<ClientRelationshipOut["kind"], string>> = {
  spouse: "Spouse of",
  owner_of: "Owner of",
  trustee_of: "Trustee of",
  beneficiary_of: "Beneficiary of",
  sponsor_of: "Sponsor of",
  upper_tier_of: "Upper tier of",
  executor_of: "Executor of",
  gp_of: "General partner of",
  lp_of: "Limited partner of",
  estate_of: "Estate of",
};

function Relationships({ clientId }: { clientId: string }): JSX.Element {
  const list = useQuery({
    ...clientRelationshipsOptions({ path: { client_id: clientId } }),
    retry: false,
  });
  const items = list.data?.items ?? [];
  return (
    <ul
      aria-label={COPY.tabs.relationships}
      className="m-[10px] overflow-hidden rounded-pane bg-card shadow-e1"
    >
      {items.map((r) => (
        <li
          key={r.id}
          className="flex min-h-[40px] items-center gap-[8px] px-[14px] text-body hairline-b"
        >
          <span className="font-medium">{r.from_entity_name}</span>
          <span className="text-ink-3">{RELATIONSHIP_WORDS[r.kind]}</span>
          <span>{r.to_entity_name}</span>
          {r.percent != null && (
            <span className="ml-auto text-ink-3 tabular-nums">{r.percent}%</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Engagements({
  record,
  onNavigate,
}: {
  record: ClientRecordOut;
  onNavigate?: ((target: Cli02Target) => void) | undefined;
}): JSX.Element {
  return (
    <div className="m-[10px] overflow-hidden rounded-pane bg-card shadow-e1">
      {(record.active_engagements ?? []).map((e) => (
        <WorkRow
          key={e.id}
          item={{
            key: "engagement",
            text: e.name,
            pill_object: "engagement",
            pill_code: e.status,
          }}
          onOpen={() => {
            onNavigate?.({ screen: "ENG-02", engagementId: e.id });
          }}
        />
      ))}
    </div>
  );
}

// ---- the screen ---------------------------------------------------------------------------------

export function CLI02({
  clientId,
  tab,
  onTab,
  onNavigate,
  toolbar,
  frame = false,
  contactsOpen,
}: CLI02Props): JSX.Element {
  // CLI-04 (P-07-T33) is live behind `contacts.v2`; without it the tab stays planned.
  const contactsLive = useFlag("contacts.v2") === true;
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const record = useClientRecord(clientId);
  const overview = useClientOverview(clientId);
  const staff = useStaff();
  const data = record.data;
  const partner =
    data?.relationship_partner_id == null
      ? undefined
      : staff.names.get(data.relationship_partner_id);

  let state: ViewState;
  if (record.isError) {
    state = notFound(record.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void record.refetch() };
  } else if (data === undefined || (tab === "overview" && overview.data === undefined)) {
    state = overview.isError
      ? { kind: "error", retry: () => void overview.refetch() }
      : { kind: "loading" };
  } else if (
    tab === "overview" &&
    (data.active_engagements ?? []).length === 0 &&
    (overview.data?.sections.length ?? 0) === 0
  ) {
    state = PLANNED_VISIBLE
      ? { kind: "empty", action: { label: COPY.empty.action, onSelect: () => undefined } }
      : { kind: "empty" };
  } else state = { kind: "ready" };

  const counts = data?.tab_counts;
  const tabs = (
    <Tabsbar
      label={COPY.tabs.label}
      options={[
        { label: COPY.tabs.overview },
        {
          label: COPY.tabs.engagements,
          ...(counts === undefined || counts.engagements === 0
            ? {}
            : { count: counts.engagements }),
        },
        { label: COPY.tabs.relationships },
        ...(contactsLive || PLANNED_VISIBLE
          ? [
              {
                label: COPY.tabs.contacts,
                ...(contactsLive ? {} : { disabled: true }),
                ...(counts?.contacts == null || counts.contacts === 0
                  ? {}
                  : { count: counts.contacts }),
              },
            ]
          : []),
        ...(PLANNED_VISIBLE
          ? [
              { label: COPY.tabs.taxProfile, disabled: true },
              { label: COPY.tabs.files, disabled: true },
              {
                label: COPY.tabs.messages,
                disabled: true,
                bad: true,
                ...(counts?.messages == null ? {} : { count: counts.messages }),
              },
            ]
          : []),
      ]}
      active={
        tab === "engagements"
          ? COPY.tabs.engagements
          : tab === "relationships"
            ? COPY.tabs.relationships
            : tab === "contacts" && contactsLive
              ? COPY.tabs.contacts
              : COPY.tabs.overview
      }
      onChange={(label) => {
        onTab(
          label === COPY.tabs.engagements
            ? "engagements"
            : label === COPY.tabs.relationships
              ? "relationships"
              : label === COPY.tabs.contacts
                ? "contacts"
                : "overview",
        );
      }}
    />
  );

  const rail =
    data === undefined ? (
      <section aria-label={COPY.rail.title} className="pane flex min-h-0 flex-1 flex-col">
        <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
          <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail.title}</h2>
        </div>
      </section>
    ) : (
      <Rail
        record={data}
        overview={overview.data}
        now={now}
        tz={tz}
        onNavigate={onNavigate}
        onTab={onTab}
      />
    );

  const title =
    tab === "engagements"
      ? COPY.tabs.engagements
      : tab === "relationships"
        ? COPY.tabs.relationships
        : COPY.canvas.title;

  const subbar = (
    <Subbar
      record={data}
      partner={partner}
      {...(onNavigate === undefined
        ? {}
        : {
            onBack: () => {
              onNavigate({ screen: "CLI-01" });
            },
          })}
    />
  );
  if (tab === "contacts" && contactsLive) {
    // CLI-04: T1 inside the record — the same subbar and tabs over one full-width pane.
    const pane = (
      <div data-shell="cols" className="flex min-h-0 flex-1 items-stretch pt-(--gutter-pane)">
        <CLI04 clientId={clientId} record={data} opens={contactsOpen} />
      </div>
    );
    return (
      <div data-screen="CLI-02" className="flex min-h-0 flex-1 flex-col">
        {toolbar === undefined ? (
          <div className="flex min-h-0 flex-1 flex-col">
            {subbar}
            {tabs}
            {pane}
          </div>
        ) : (
          <AppShell
            toolbar={toolbar}
            frame={frame}
            {...(frame ? { height: 860 } : {})}
            record={subbar}
            tabs={tabs}
          >
            {pane}
          </AppShell>
        )}
      </div>
    );
  }

  return (
    <div data-screen="CLI-02" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={subbar}
        tabs={tabs}
        rail={rail}
        canvas={{
          title,
          well: true,
          state,
          empty: { title: COPY.empty.title },
          ...(PLANNED_VISIBLE
            ? {
                actions: (
                  <span className="flex items-center gap-[8px]">
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="message-circle"
                      disabled
                      title={COPY.canvas.messageHint}
                    >
                      {COPY.canvas.message}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled
                      title={COPY.canvas.newEngagementHint}
                    >
                      {COPY.canvas.newEngagement}
                    </Button>
                  </span>
                ),
              }
            : {}),
          children:
            data === undefined ? null : tab === "relationships" ? (
              <Relationships clientId={clientId} />
            ) : tab === "engagements" ? (
              <Engagements record={data} onNavigate={onNavigate} />
            ) : overview.data === undefined ? null : (
              <Overview overview={overview.data} now={now} tz={tz} onNavigate={onNavigate} />
            ),
        }}
      />
    </div>
  );
}

/** The screen with its own tab: the gallery's artboard and the route's page. */
export function ClientRecordPage({
  clientId,
  onNavigate,
  toolbar,
  frame = false,
  initialTab = "overview",
  contactsOpen,
}: {
  clientId: string;
  onNavigate?: (target: Cli02Target) => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
  initialTab?: Cli02Tab;
  contactsOpen?: Cli04Open | undefined;
}): JSX.Element {
  const [tab, setTab] = useState<Cli02Tab>(initialTab);
  return (
    <CLI02
      clientId={clientId}
      tab={tab}
      onTab={setTab}
      contactsOpen={contactsOpen}
      {...(onNavigate === undefined ? {} : { onNavigate })}
      {...(toolbar === undefined ? {} : { toolbar })}
      frame={frame}
    />
  );
}
