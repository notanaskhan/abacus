import type {
  EngagementRailRowOut,
  EngagementRecordOut,
  LetterRecordIn,
  WorkItemOut,
} from "@abacus/api-client";
import {
  Button,
  DASH,
  DEFAULT_TZ,
  EmptyState,
  Fieldset,
  Icon,
  KvRowView,
  RecordBand,
  RecordCockpit,
  type RegistryObject,
  SheetModal,
  StatusDisc,
  StatusPill,
  Tabsbar,
  type ToolbarProps,
  ValueRow,
  type ViewState,
  date,
  status,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { useStaff } from "../../domain/clients";
import {
  GateBlock,
  allows,
  bandRows,
  conflictOf,
  gateOf,
  useEngagementRecord,
  useEngagementWorkItems,
  useRecordLetter,
  waitsOnLetter,
} from "../../domain/engagements";
import { COPY } from "./copy";

// ENG-02 · Engagement record, core (P-07-T20; docs/screens/ENG-02.md). T2 without the dock over
// `GET /v1/engagements/{id}/record` and its work items: the subbar, the tabs (Overview, Work
// items, Letter & terms; Team waits on ENG-05), the Summary rail (status block, Details, Review
// and Delivery, Client Portal), the gate rows, the prospect and G3 banners, and the Letter & terms
// record-mode card with the Record signed letter sheet (O3; the interim G3 until C7). Each artboard
// is its data (fixtures/scenarios/ENG-02.ts):
//
//   b  Northwind "PY2025 EBP Audit", Active: gates G1–G3 met, G4 blocked, G5–G9 not started
//   c  Bluestem "2026 Close (from Oct)", Accepted, letter viewed Sep 11: the G3 banner
//   d  Meridian "FY2025 FS Audit", Archived and locked: every action disabled
//   e  the record never answers: skeletons
//   prospect  the Thornbury estate, Prospect: "Acceptance pending — Daniel Reyes"
//
// a (Copperleaf with the RunCard and close groups), f and g are P-07-T28's.

export type Eng02Tab = "overview" | "work-items" | "letter";

export type Eng02Target = { screen: "CLI-02"; clientId: string } | { screen: "ENG-01" };

export interface ENG02Props {
  engagementId: string;
  tab: Eng02Tab;
  onTab: (tab: Eng02Tab) => void;
  onNavigate?: (target: Eng02Target) => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
}

function notFound(error: unknown): boolean {
  const detail = conflictOf(error);
  return detail !== null && detail.replace(" ", "_") === "not_found";
}

function initialsOf(name: string): string {
  const words = name.split(/\s+/).filter((w) => w !== "");
  const first = words[0]?.charAt(0) ?? "";
  const last = words.length > 1 ? (words[words.length - 1]?.charAt(0) ?? "") : "";
  return `${first}${last}`.toUpperCase();
}

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function Pane({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={label} className="pane flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{label}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

function EngagementPill({ record }: { record: EngagementRecordOut }): JSX.Element {
  const word = status("engagement", record.status);
  return (
    <StatusPill variant={word.variant ?? "neutral"} size="state">
      {record.status === "archived" && <Icon name="lock" size={12} />}
      {word.label}
    </StatusPill>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-pane bg-card shadow-e1">
      <h3 className="flex items-center bg-shell pt-[10px] pr-[10px] pb-[10px] pl-[13px] text-section font-medium">
        {title}
      </h3>
      {children}
    </section>
  );
}

// ---- rail ---------------------------------------------------------------------------------------

function rowValue(
  row: EngagementRailRowOut,
  names: ReadonlyMap<string, string>,
  now: Date,
  tz: string,
): string {
  if (row.key === "archive_locked") {
    return row.on == null
      ? DASH
      : COPY.archiveLocked(date(onDay(row.on), { now, tz, withYear: true }));
  }
  if (row.user_id != null) return names.get(row.user_id) ?? DASH;
  if (row.pill_object != null && row.pill_code != null) {
    const word = status(row.pill_object as RegistryObject, row.pill_code as never).label;
    // "Signed Jun 2, 2026": the letter's state and its date (the record's own facts).
    if (row.key === "letter" && row.pill_code === "signed" && row.on != null) {
      return `${COPY.letter.signedOn} ${date(onDay(row.on), { now, tz, withYear: true })}`;
    }
    return word;
  }
  if (row.on != null) return date(onDay(row.on), { now, tz, withYear: true });
  return row.text ?? DASH;
}

function Rail({
  record,
  onNavigate,
  onTab,
  now,
  tz,
}: {
  record: EngagementRecordOut;
  onNavigate?: ((target: Eng02Target) => void) | undefined;
  onTab: (tab: Eng02Tab) => void;
  now: Date;
  tz: string;
}): JSX.Element {
  const staff = useStaff();
  const bands = (["details", "review_delivery", "client_portal"] as const).filter(
    (b) => bandRows(record, b).length > 0,
  );
  return (
    <Pane label={COPY.rail.title}>
      <div className="flex flex-col items-center px-[12px] pt-[14px] pb-[15px] text-center hairline-b">
        <p className="text-section font-medium">{record.name}</p>
        <span className="mt-[8px]">
          <EngagementPill record={record} />
        </span>
      </div>
      {bands.map((b) => (
        <div key={b} className="flex flex-col">
          <RecordBand title={COPY.rail.bands[b]} />
          {bandRows(record, b).map((row) => {
            if (row.key === "post_lock_additions") {
              return (
                <div
                  key={row.key}
                  data-record="kv"
                  className="flex min-h-[33px] items-center px-[12px] text-body text-ink-2 hairline-b"
                >
                  {COPY.postLock(row.text ?? "0")}
                </div>
              );
            }
            if (row.key === "archive_locked") {
              return (
                <div
                  key={row.key}
                  data-record="kv"
                  className="flex min-h-[33px] items-center gap-[8px] px-[12px] text-body text-ink-2 hairline-b"
                >
                  <Icon name="lock" size={12} className="text-ink-3" />
                  {rowValue(row, staff.names, now, tz)}
                </div>
              );
            }
            const label = COPY.keys[row.key] ?? row.key;
            const value = rowValue(row, staff.names, now, tz);
            if (row.key === "client") {
              return (
                <span key={row.key} title={COPY.clientHint} className="contents">
                  <KvRowView
                    row={{ id: row.key, label, value, kind: "link" }}
                    onOpen={() => {
                      onNavigate?.({ screen: "CLI-02", clientId: record.client_id });
                    }}
                  />
                </span>
              );
            }
            if (row.key === "letter") {
              return (
                <KvRowView
                  key={row.key}
                  row={{ id: row.key, label, value, kind: "link" }}
                  onOpen={() => {
                    onTab("letter");
                  }}
                />
              );
            }
            return <KvRowView key={row.key} row={{ id: row.key, label, value }} />;
          })}
        </div>
      ))}
    </Pane>
  );
}

// ---- canvas -------------------------------------------------------------------------------------

function Banner({ children, action }: { children: ReactNode; action?: ReactNode }): JSX.Element {
  return (
    <div
      role="status"
      data-banner=""
      className="flex min-h-[40px] items-center gap-[10px] rounded-tile bg-amber-tint px-[12px] py-[6px] text-body text-amber-ink"
    >
      <Icon name="triangle-alert" size={14} className="flex-none" />
      <span className="min-w-0 flex-1">{children}</span>
      {action}
    </div>
  );
}

function WorkItemRows({
  items,
  archived,
}: {
  items: readonly WorkItemOut[];
  archived: boolean;
}): JSX.Element {
  if (items.length === 0) {
    return (
      <div className="bg-card">
        <EmptyState title={COPY.empty.workItems} />
      </div>
    );
  }
  return (
    <ul aria-label={COPY.group.workItems} className="flex flex-col">
      {items.map((w) => {
        const phase =
          w.phase == null
            ? null
            : status(w.kind === "assurance" ? "audit_engagement" : "close", w.phase as never);
        return (
          <li
            key={w.id}
            title={w.kind === "assurance" ? COPY.workItemHint : undefined}
            className="flex items-center gap-[10px] bg-card pt-[8px] pr-[12px] pb-[9px] pl-[13px] hairline-t"
          >
            <StatusDisc state={archived || w.status === "archived" ? "done" : "half"} size={17} />
            <span className="min-w-0 flex-1 truncate text-body">{w.name}</span>
            {phase !== null && (
              <StatusPill variant={phase.variant ?? "neutral"}>{phase.label}</StatusPill>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function LetterCard({
  record,
  onRecord,
  now,
  tz,
}: {
  record: EngagementRecordOut;
  onRecord: () => void;
  now: Date;
  tz: string;
}): JSX.Element {
  const word = status("letter_record", record.letter.status);
  const g1 = gateOf(record, "G1");
  const can =
    allows(record, "letter.record") &&
    record.read_only_reason !== "archived" &&
    g1?.met === true &&
    record.letter.status === "not_signed";
  return (
    <Group title={COPY.letter.title}>
      <div className="flex min-h-[33px] items-center px-[13px] text-body hairline-t">
        <span className="text-ink-2">{COPY.letter.status}</span>
        <span className="ml-auto">
          <StatusPill variant={word.variant ?? "neutral"}>{word.label}</StatusPill>
        </span>
      </div>
      {record.letter.signed_on != null && (
        <div className="flex min-h-[33px] items-center px-[13px] text-body hairline-t">
          <span className="text-ink-2">{COPY.letter.signedOn}</span>
          <span className="ml-auto">
            {date(onDay(record.letter.signed_on), { now, tz, withYear: true })}
          </span>
        </div>
      )}
      <div className="flex justify-end bg-card px-[13px] py-[10px] hairline-t">
        <Button variant="secondary" size="sm" opensDialog disabled={!can} onClick={onRecord}>
          {COPY.letter.record}
        </Button>
      </div>
    </Group>
  );
}

function RecordLetterSheet({
  record,
  open,
  onOpenChange,
}: {
  record: EngagementRecordOut;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const staff = useStaff();
  const save = useRecordLetter(record.id);
  const [clientOn, setClientOn] = useState("");
  const [firmOn, setFirmOn] = useState("");
  const signers = (record.contacts ?? []).filter((c) => c.designation === "signing_officer");
  const [clientSigner, setClientSigner] = useState<string | undefined>(signers[0]?.contact_id);
  const partner = bandRows(record, "review_delivery").find((r) => r.key === "partner")?.user_id;
  const [firmSigner, setFirmSigner] = useState<string | undefined>(partner ?? undefined);
  const [problem, setProblem] = useState<string | null>(null);
  const valid = ISO_DAY.test(clientOn) && ISO_DAY.test(firmOn);
  const dirty = clientOn !== "" || firmOn !== "";
  const close = (): void => {
    setClientOn("");
    setFirmOn("");
    setProblem(null);
    onOpenChange(false);
  };
  const submit = async (): Promise<void> => {
    const body: LetterRecordIn = {
      mode: "signed",
      client_signed_on: clientOn,
      firm_signed_on: firmOn,
      ...(clientSigner === undefined ? {} : { client_signer_contact_id: clientSigner }),
      ...(firmSigner === undefined ? {} : { firm_signer_user_id: firmSigner }),
    };
    try {
      await save.mutateAsync({ path: { engagement_id: record.id }, body });
      toast.show({ kind: "success", text: COPY.letter.saved });
      close();
    } catch (error) {
      const code = conflictOf(error);
      const known = COPY.letter.errors as Readonly<Record<string, string>>;
      setProblem(
        code !== null && code in known ? (known[code] ?? null) : COPY.letter.errors.failed,
      );
    }
  };
  const dateError = (v: string): string | undefined =>
    v !== "" && !ISO_DAY.test(v) ? COPY.letter.errors.date : undefined;
  const clientDateError = problem ?? dateError(clientOn);
  const firmDateError = dateError(firmOn);
  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (next) onOpenChange(true);
        else close();
      }}
      title={COPY.letter.sheetTitle}
      description={COPY.letter.sheetDescription}
      dirty={dirty}
      action={
        <Button
          variant="primary"
          disabled={!valid}
          loading={save.isPending}
          onClick={() => void submit()}
        >
          {COPY.letter.save}
        </Button>
      }
    >
      <Fieldset flush>
        <ValueRow
          kind="text"
          label={COPY.letter.clientSignedOn}
          value={clientOn}
          placeholder={COPY.letter.datePlaceholder}
          onChange={(v) => {
            setProblem(null);
            setClientOn(v);
          }}
          {...(clientDateError === undefined ? {} : { error: clientDateError })}
        />
        <ValueRow
          kind="select"
          label={COPY.letter.clientSigner}
          placeholder={COPY.letter.choose}
          options={signers.map((c) => ({ value: c.contact_id, label: c.name }))}
          {...(clientSigner === undefined ? {} : { value: clientSigner })}
          onChange={setClientSigner}
        />
        <ValueRow
          kind="text"
          label={COPY.letter.firmSignedOn}
          value={firmOn}
          placeholder={COPY.letter.datePlaceholder}
          onChange={(v) => {
            setProblem(null);
            setFirmOn(v);
          }}
          {...(firmDateError === undefined ? {} : { error: firmDateError })}
        />
        <ValueRow
          kind="select"
          label={COPY.letter.firmSigner}
          placeholder={COPY.letter.choose}
          options={staff.ids.map((id) => ({ value: id, label: staff.names.get(id) ?? id }))}
          {...(firmSigner === undefined ? {} : { value: firmSigner })}
          onChange={setFirmSigner}
        />
      </Fieldset>
    </SheetModal>
  );
}

// ---- the screen ---------------------------------------------------------------------------------

export function ENG02({
  engagementId,
  tab,
  onTab,
  onNavigate,
  toolbar,
  frame = false,
}: ENG02Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const recordQuery = useEngagementRecord(engagementId);
  const record = recordQuery.data;
  const work = useEngagementWorkItems(
    engagementId,
    record !== undefined && !waitsOnLetter(record),
  );
  const staff = useStaff();
  const [recording, setRecording] = useState(false);

  const initials = new Map([...staff.names].map(([id, n]) => [id, initialsOf(n)]));

  let state: ViewState;
  if (recordQuery.isError) {
    state = notFound(recordQuery.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void recordQuery.refetch() };
  } else if (record === undefined) state = { kind: "loading" };
  else state = { kind: "ready" };

  const archived = record?.read_only_reason === "archived";

  const header = (
    <div
      data-shell="record-header"
      data-variant="engagement"
      className="relative flex h-(--subbar-h) flex-none items-center gap-[8px] px-(--edge-app)"
    >
      <Button
        variant="secondary"
        size="sm"
        title={COPY.backHint}
        onClick={() => {
          onNavigate?.({ screen: "ENG-01" });
        }}
      >
        {COPY.back}
      </Button>
      {record !== undefined && (
        <h1 className="absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-[8px] text-title tracking-[-0.012em] whitespace-nowrap">
          <span className="font-medium">{record.name}</span>
          <span className="text-ink-2">{record.client_name}</span>
          <EngagementPill record={record} />
        </h1>
      )}
      {record?.letter.signed_on != null && (
        <span className="ml-auto text-body text-ink-3">
          {COPY.contracted(date(onDay(record.letter.signed_on), { now, tz, withYear: true }))}
        </span>
      )}
    </div>
  );

  const tabs = (
    <Tabsbar
      label={COPY.tabs.label}
      options={[
        { label: COPY.tabs.overview },
        {
          label: COPY.tabs.workItems,
          ...(record === undefined || record.tab_counts.work_items === 0
            ? {}
            : { count: record.tab_counts.work_items }),
        },
        ...(PLANNED_VISIBLE
          ? [
              {
                label: COPY.tabs.team,
                disabled: true,
                ...(record === undefined ? {} : { count: record.tab_counts.team }),
              },
            ]
          : []),
        { label: COPY.tabs.letter },
      ]}
      active={
        tab === "work-items"
          ? COPY.tabs.workItems
          : tab === "letter"
            ? COPY.tabs.letter
            : COPY.tabs.overview
      }
      onChange={(label) => {
        onTab(
          label === COPY.tabs.workItems
            ? "work-items"
            : label === COPY.tabs.letter
              ? "letter"
              : "overview",
        );
      }}
    />
  );

  const rail =
    record === undefined ? (
      <Pane label={COPY.rail.title}>
        <span className="sr-only">{COPY.rail.title}</span>
      </Pane>
    ) : (
      <Rail record={record} onNavigate={onNavigate} onTab={onTab} now={now} tz={tz} />
    );

  const items = work.data ?? [];
  const audit = record?.service_line === "audit";
  const partnerId =
    record === undefined
      ? undefined
      : bandRows(record, "review_delivery").find((r) => r.key === "partner")?.user_id;
  const partnerName = partnerId == null ? undefined : staff.names.get(partnerId);
  const signer = record?.contacts?.find((c) => c.designation === "signing_officer");
  const g3 = record === undefined ? undefined : gateOf(record, "G3");
  const g3By = g3?.met_by_user_id == null ? undefined : initials.get(g3.met_by_user_id);
  const signers =
    signer !== undefined && g3By !== undefined ? `${signer.name} and ${g3By}` : undefined;

  let body: ReactNode = null;
  if (record !== undefined) {
    const banners = (
      <>
        {record.status === "prospect" && (
          <Banner
            action={
              PLANNED_VISIBLE ? (
                <Button variant="secondary" size="sm" disabled title={COPY.banner.prospectHint}>
                  {COPY.banner.prospectAction}
                </Button>
              ) : undefined
            }
          >
            {COPY.banner.prospect(partnerName ?? DASH)}
          </Banner>
        )}
        {waitsOnLetter(record) && (
          <Banner
            action={
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onTab("letter");
                }}
              >
                {COPY.banner.g3Action}
              </Button>
            }
          >
            {record.letter.last_event === "viewed" &&
            record.letter.last_event_on != null &&
            signer !== undefined
              ? COPY.banner.g3(signer.name, date(onDay(record.letter.last_event_on), { now, tz }))
              : COPY.banner.g3NoView}
          </Banner>
        )}
      </>
    );
    const workGroup = (
      <Group title={COPY.group.workItems}>
        <WorkItemRows items={waitsOnLetter(record) ? [] : items} archived={archived} />
      </Group>
    );
    body = (
      <div
        role="group"
        aria-label={COPY.canvas.title}
        tabIndex={0}
        className="flex flex-col gap-[10px] p-[10px] outline-offset-[-2px]"
      >
        {banners}
        {tab === "letter" ? (
          <LetterCard
            record={record}
            now={now}
            tz={tz}
            onRecord={() => {
              setRecording(true);
            }}
          />
        ) : tab === "work-items" ? (
          workGroup
        ) : (
          <>
            {audit && (
              <Group title={COPY.group.gates}>
                <GateBlock
                  gates={record.gates}
                  initials={initials}
                  now={now}
                  tz={tz}
                  {...(signers === undefined ? {} : { signers })}
                />
              </Group>
            )}
            {workGroup}
          </>
        )}
      </div>
    );
  }

  return (
    <div
      data-screen="ENG-02"
      data-read-only={archived ? "archived" : undefined}
      className="flex min-h-0 flex-1 flex-col"
    >
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={header}
        tabs={tabs}
        rail={rail}
        canvas={{
          title:
            tab === "letter"
              ? COPY.tabs.letter
              : tab === "work-items"
                ? COPY.tabs.workItems
                : COPY.canvas.title,
          well: true,
          state,
          ...(PLANNED_VISIBLE
            ? {
                actions: (
                  <Button variant="link" size="sm" disabled>
                    {COPY.canvas.activity}
                  </Button>
                ),
              }
            : {}),
          children: body,
        }}
      />
      {record !== undefined && (
        <RecordLetterSheet record={record} open={recording} onOpenChange={setRecording} />
      )}
    </div>
  );
}

/** The screen with its own tab: the gallery's artboard and the route's page. */
export function EngagementRecordPage({
  engagementId,
  initialTab = "overview",
  onNavigate,
  toolbar,
  frame = false,
}: {
  engagementId: string;
  initialTab?: Eng02Tab;
  onNavigate?: (target: Eng02Target) => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
}): JSX.Element {
  const [tab, setTab] = useState<Eng02Tab>(initialTab);
  return (
    <ENG02
      engagementId={engagementId}
      tab={tab}
      onTab={setTab}
      {...(onNavigate === undefined ? {} : { onNavigate })}
      {...(toolbar === undefined ? {} : { toolbar })}
      frame={frame}
    />
  );
}
