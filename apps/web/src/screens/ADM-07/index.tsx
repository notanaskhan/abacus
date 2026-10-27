import {
  type AuditEventDetail,
  type AuditEventRow,
  type AuditValuesOut,
  listAuditEvents,
} from "@abacus/api-client";
import {
  auditEventOptions,
  listAuditEventsOptions,
  requestAuditExportMutation,
  settingsOverviewOptions,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  DEFAULT_TZ,
  Dialog,
  Drawer,
  EmptyState,
  ErrorState,
  FilterChip,
  Icon,
  type IconName,
  SearchField,
  SettingsLayout,
  Skeleton,
  Tag,
  Toggle,
  count,
  date,
  dateTime,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { GROUPS } from "../ADM-01/copy";
import {
  AUTHORITY,
  COPY,
  LEVELS,
  NOT_INCLUDED,
  STATUS_WORDS,
  actorName,
  detailOf,
  drawerTitle,
  titleOf,
} from "./copy";

// ADM-07 · Audit log explorer (G-02-T13; G-02 §3.1–3.3; docs/screens/ADM-07.md): the T1 feed in
// the T12 frame, section "Audit log". Every artboard is a data condition of one screen:
//
//   a  Felix Andersen at E0: 14 rows, "18,406 events · immutable", the policy-principal note
//   b  ?actor=via_agent: rows 6, 9, 11, 14; the chip amber; "4 of 1,962"
//   c  ?event=<seq>: the O2 drawer; values for Margaret Okonkwo, withheld for Felix (DEC-60)
//   d  the dormant policy principal (fixture only): "Policy: BH AJE thresholds v2", "2 events"
//   e  Export…: Dialog 440, Sep 8–14, CSV + signed JSON manifest, before/after values on
//   f  ?q=pell street iii: "No events match 'pell street iii'."
//   g  after e: the toast "Export ready · SHA-256 manifest included"
//
// The server sends codes and facts; titles and detail lines come from copy.ts. Nothing here
// edits or removes an event, and no row names the agent as an actor.

export interface Adm07Search {
  actor?: string;
  object?: string;
  action?: string;
  date?: string;
  office?: string;
  ip?: string;
  q?: string;
  event?: string;
}
const KEYS = ["actor", "object", "action", "date", "office", "ip", "q", "event"] as const;

/** The URL's search, kept to the keys this screen reads. */
export function parseSearch(search: Record<string, unknown> | string): Adm07Search {
  const entries =
    typeof search === "string"
      ? [...new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).entries()]
      : Object.entries(search);
  const out: Adm07Search = {};
  for (const [key, value] of entries) {
    if ((KEYS as readonly string[]).includes(key) && typeof value === "string" && value !== "") {
      out[key as (typeof KEYS)[number]] = value;
    }
  }
  return out;
}

const ACTOR_KINDS = new Set(["person", "via_agent", "policy", "system", "support"]);
type ActorKind = "person" | "via_agent" | "policy" | "system" | "support";

const GLYPHS: Record<string, IconName> = {
  "engagement_run.started": "play",
  "workbench_session.started": "message-square",
  "inbox_email.received": "upload",
  "agent_run.report_prepared": "file-text",
  "agent_run.reminders_drafted": "file-text",
  "acceptance_prescreen.drafted": "file-text",
  "envelope.sent": "send",
  "pii.revealed": "eye",
  "session.started": "log-in",
  "tax_return.self_checked": "list-checks",
};
const CATEGORY_GLYPHS: Record<AuditEventRow["category"], IconName> = {
  decision: "check",
  change: "file-text",
  access: "eye",
  run: "play",
  sign_in: "log-in",
  communication: "send",
  export: "download",
};

function Marker({ row }: { row: AuditEventRow }): JSX.Element {
  if (row.mark === "ok") {
    return (
      <span
        role="img"
        aria-label={COPY.marks.ok}
        className="inline-flex size-[20px] items-center justify-center rounded-full bg-espresso text-on-dark"
      >
        <Icon name="check" size={12} />
      </span>
    );
  }
  if (row.mark === "no") {
    return (
      <span
        role="img"
        aria-label={COPY.marks.no}
        className="inline-flex size-[20px] items-center justify-center rounded-full bg-ink-3 text-on-dark"
      >
        <Icon name="x" size={12} />
      </span>
    );
  }
  return (
    <span
      role="img"
      aria-label={COPY.marks.pl}
      className="inline-flex size-[20px] items-center justify-center bg-card text-ink-2"
    >
      <Icon name={GLYPHS[row.action] ?? CATEGORY_GLYPHS[row.category]} size={14} />
    </span>
  );
}

function ActorTag({ kind }: { kind: ActorKind }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-[4px] text-meta text-ink-2">
      {kind === "via_agent" && <Icon name="atom" size={12} />}
      {kind === "policy" && <Icon name="scale" size={12} />}
      {COPY.tags[kind]}
    </span>
  );
}

function PlannedRun(): JSX.Element | null {
  if (!PLANNED_VISIBLE) return null;
  return (
    <span
      aria-disabled="true"
      title={COPY.plannedRun}
      className="text-meta whitespace-nowrap text-ink-3"
    >
      {COPY.run}
    </span>
  );
}

function Row({
  row,
  now,
  onOpen,
  onIp,
}: {
  row: AuditEventRow;
  now: Date;
  onOpen: () => void;
  onIp: (ip: string) => void;
}): JSX.Element {
  const title = titleOf(row);
  const when = date(row.effective_at, { now, tz: DEFAULT_TZ });
  const at = time(row.effective_at, { tz: DEFAULT_TZ });
  const detail = detailOf(row, (iso) => date(iso, { now, tz: DEFAULT_TZ }));
  const object = row.target.label ?? "";
  return (
    <li
      data-seq={row.seq}
      className="relative grid grid-cols-[76px_20px_minmax(0,1fr)_260px_96px_120px_16px] items-start gap-[14px] px-[18px] py-[9px]"
    >
      <span className="flex flex-col items-end pt-[1px] text-right">
        <span className="text-dense text-ink-2">{when}</span>
        <span className="text-meta text-ink-3">{at}</span>
      </span>
      <span className="relative z-[1] flex justify-center pt-[1px]">
        <Marker row={row} />
      </span>
      <button
        type="button"
        onClick={onOpen}
        aria-label={COPY.rowName(title, object, `${when} ${at}`)}
        className="flex min-w-0 flex-col gap-[2px] text-left"
      >
        <span className="text-chat leading-[1.3] font-medium">{title}</span>
        {detail !== "" && <span className="text-dense leading-[1.4] text-ink-2">{detail}</span>}
      </button>
      <span className="min-w-0 pt-[1px]">
        {object !== "" && <Tag className="max-w-full truncate">{object}</Tag>}
      </span>
      <span className="pt-[3px]">
        <ActorTag kind={row.actor.kind} />
      </span>
      <span className="flex items-center gap-[8px] pt-[3px] text-meta text-ink-3 tabular-nums">
        {row.ip !== undefined && row.ip !== null ? (
          <button
            type="button"
            aria-label={COPY.filterByIp(row.ip)}
            className="hover:underline"
            onClick={() => {
              onIp(row.ip ?? "");
            }}
          >
            {row.ip}
          </button>
        ) : (
          <span>{COPY.noIp}</span>
        )}
        {row.link_kind === "run" && <PlannedRun />}
      </span>
      <span aria-hidden="true" className="pt-[3px] text-ink-3">
        <Icon name="chevron-right" size={14} />
      </span>
    </li>
  );
}

function Kv({ label, children }: { label: string; children: React.ReactNode }): JSX.Element {
  return (
    <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-[10px] py-[6px] text-body">
      <dt className="text-ink-2">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function Values({ values }: { values: AuditValuesOut }): JSX.Element {
  if (values.status === "withheld") {
    // DEC-43: a wall reads as "withheld" like need to know, never as a wall.
    const reason = values.reason === "not_enabled" ? COPY.drawer.notEnabled : COPY.drawer.withheld;
    return (
      <p role="note" className="text-dense text-ink-3">
        {reason}
      </p>
    );
  }
  if (values.status === "unavailable") {
    return <p className="text-dense text-ink-3">{COPY.drawer.unavailable}</p>;
  }
  const rows = values.rows ?? [];
  const amounts = rows
    .map((r) => r.amount)
    .filter((a): a is string => a !== null && a !== undefined);
  // Code adds, the model never does (ADR-050): the footing in integer cents.
  const cents = amounts.map(centsOf);
  const total =
    amounts.length === rows.length && rows.length > 0 && cents.every((c) => c !== null)
      ? decimalOf(cents.reduce<number>((sum, c) => sum + c, 0))
      : null;
  return (
    <table className="w-full text-body">
      <caption className="sr-only">{COPY.drawer.beforeAfter}</caption>
      <thead>
        <tr className="text-left text-meta text-ink-3">
          <th scope="col" className="py-[4px] font-normal">
            {COPY.drawer.entry}
          </th>
          <th scope="col" className="py-[4px] text-right font-normal">
            {COPY.drawer.amount}
          </th>
          <th scope="col" className="py-[4px] pl-[12px] font-normal">
            {COPY.drawer.status}
          </th>
        </tr>
      </thead>
      <tbody className="divide-y-[0.5px] divide-hair">
        {rows.map((r, i) => (
          <tr key={`${r.item_label}-${String(i)}`}>
            <td className="py-[5px]">{r.item_label}</td>
            <td className="py-[5px] text-right tabular-nums">
              {r.amount !== null && r.amount !== undefined ? <Amount value={r.amount} /> : null}
            </td>
            <td className="py-[5px] pl-[12px] text-ink-2">
              {`${STATUS_WORDS[r.before ?? ""] ?? r.before ?? ""} → ${STATUS_WORDS[r.after ?? ""] ?? r.after ?? ""}`}
            </td>
          </tr>
        ))}
        {total !== null && (
          <tr>
            <td className="py-[5px] font-medium">{COPY.drawer.total}</td>
            <td className="py-[5px] text-right font-medium tabular-nums">
              <Amount value={total} />
            </td>
            <td />
          </tr>
        )}
      </tbody>
    </table>
  );
}

/** "11860.00" → 1186000 cents; null for anything but a two-place decimal string. */
function centsOf(value: string): number | null {
  const m = /^(-?)(\d+)\.(\d{2})$/.exec(value);
  if (m === null) return null;
  const whole = Number(m[2]) * 100 + Number(m[3]);
  return m[1] === "-" ? -whole : whole;
}

/** 2002000 cents → "20020.00", the decimal string `Amount` formats. */
function decimalOf(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return `${sign}${String(Math.trunc(abs / 100))}.${String(abs % 100).padStart(2, "0")}`;
}

function EventDrawer({
  seq,
  row,
  onClose,
}: {
  seq: number;
  row: AuditEventRow | undefined;
  onClose: () => void;
}): JSX.Element {
  const found = useQuery(auditEventOptions({ path: { seq } }));
  const event: AuditEventDetail | undefined = found.data;
  const title =
    event !== undefined ? drawerTitle(event) : row !== undefined ? drawerTitle(row) : "";
  const actor = event?.actor;
  const person = actor?.person ?? actor?.on_behalf_of ?? null;
  const authority =
    event?.authority !== undefined && event.authority !== null
      ? (AUTHORITY[event.authority.code]?.(event.authority.facts ?? {}) ?? event.authority.code)
      : null;
  const notIncluded = event?.values.not_included ?? [];
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={title}
      width={480}
      footer={<p className="text-meta text-ink-3">{COPY.drawer.footer}</p>}
    >
      {found.isPending && <Skeleton />}
      {found.isError && <ErrorState title={COPY.error} />}
      {event !== undefined && actor !== undefined && (
        <div className="flex flex-col gap-[14px]">
          <dl className="divide-y-[0.5px] divide-hair">
            <Kv label={COPY.drawer.actor}>
              {actorName(actor, event.labels ?? {})}
              {person !== null && person.level !== null && person.level !== undefined && (
                <span className="text-ink-3">{` · ${LEVELS[person.level] ?? person.level}`}</span>
              )}
            </Kv>
            {authority !== null && <Kv label={COPY.drawer.authority}>{authority}</Kv>}
            <Kv label={COPY.drawer.time}>
              {dateTime(event.occurred_at, { tz: DEFAULT_TZ, seconds: true, zone: true })}
            </Kv>
            {(event.ip ?? null) !== null && (
              <Kv label={COPY.drawer.ipDevice}>
                {[event.ip, event.device_label]
                  .filter((v) => v !== null && v !== undefined)
                  .join(" · ")}
              </Kv>
            )}
            {event.session !== undefined && event.session !== null && (
              <Kv label={COPY.drawer.session}>
                {[
                  event.session.auth_method === "sso" ? "SSO" : event.session.auth_method,
                  event.session.mfa_at !== null && event.session.mfa_at !== undefined
                    ? `MFA ${time(event.session.mfa_at, { tz: DEFAULT_TZ })}`
                    : null,
                ]
                  .filter((v) => v !== null && v !== undefined)
                  .join(" · ")}
              </Kv>
            )}
            <Kv label={COPY.drawer.contentHash}>
              <span className="font-mono text-meta">{`sha256 ${event.content_hash.slice(0, 4)}…${event.content_hash.slice(-4)}`}</span>
            </Kv>
          </dl>
          <section aria-label={COPY.drawer.beforeAfter} className="flex flex-col gap-[6px]">
            <h3 className="text-meta text-ink-3">{COPY.drawer.beforeAfter}</h3>
            <Values values={event.values} />
          </section>
          {notIncluded.length > 0 && (
            <section aria-label={COPY.drawer.notIncluded} className="flex flex-col gap-[6px]">
              <h3 className="text-meta text-ink-3">{COPY.drawer.notIncluded}</h3>
              <ul className="flex flex-col gap-[4px] text-body">
                {notIncluded.map((n) => (
                  <li key={n.item_label} className="flex flex-wrap gap-x-[8px]">
                    <span>{n.item_label}</span>
                    {n.amount !== null && n.amount !== undefined && (
                      <span className="tabular-nums">
                        <Amount value={n.amount} />
                      </span>
                    )}
                    <span className="text-ink-2">
                      {`${NOT_INCLUDED[n.reason_code] ?? n.reason_code}${n.routed_to !== null && n.routed_to !== undefined ? ` → ${n.routed_to.display_name}` : ""}`}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {event.source !== undefined && event.source !== null && (
            <section aria-label={COPY.drawer.source} className="flex flex-col gap-[6px]">
              <h3 className="text-meta text-ink-3">{COPY.drawer.source}</h3>
              <p className="text-body">
                {[
                  event.source.initiator !== null && event.source.initiator !== undefined
                    ? `Proposed by ${event.source.initiator.display_name} via Agent`
                    : null,
                  event.source.run_no !== null && event.source.run_no !== undefined
                    ? `Close run ${String(event.source.run_no)}`
                    : null,
                  event.source.started_at !== null && event.source.started_at !== undefined
                    ? `started ${time(event.source.started_at, { tz: DEFAULT_TZ })}`
                    : null,
                ]
                  .filter((v): v is string => v !== null)
                  .join(" · ")}
              </p>
              {PLANNED_VISIBLE && (
                <span
                  aria-disabled="true"
                  title={COPY.plannedRun}
                  className="text-dense text-ink-3"
                >
                  {COPY.drawer.openRun}
                </span>
              )}
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

function ExportDialog({
  open,
  onOpenChange,
  onExported,
  onStepUp,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onExported: () => void;
  onStepUp: () => void;
}): JSX.Element {
  const [includeValues, setIncludeValues] = useState(true);
  const request = useMutation(requestAuditExportMutation());
  // e: the past 7 days to E0, Sep 8–14, 2026 (the dialog's range).
  const from = "2026-09-08";
  const to = "2026-09-14";
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.exportDialog.title}
      size="sm"
      action={
        <Button
          disabled={request.isPending}
          onClick={() => {
            request.mutate(
              {
                body: { from_date: from, to_date: to, include_values: includeValues },
                headers: {
                  "Idempotency-Key": `audit-export:${from}:${to}:${String(includeValues)}`,
                },
              },
              {
                onSuccess: () => {
                  onOpenChange(false);
                  onExported();
                },
                onError: (error) => {
                  if (detailOf403(error)) onStepUp();
                  else toast.show(COPY.exportDialog.failed);
                },
              },
            );
          }}
        >
          {COPY.exportDialog.submit}
        </Button>
      }
    >
      <dl className="divide-y-[0.5px] divide-hair">
        <Kv label={COPY.exportDialog.range}>
          {`${date(`${from}T17:00:00Z`, { now: new Date(`${to}T17:00:00Z`), tz: DEFAULT_TZ })}–${date(`${to}T17:00:00Z`, { now: new Date(`${to}T17:00:00Z`), tz: DEFAULT_TZ, withYear: true })}`}
        </Kv>
        <Kv label={COPY.exportDialog.format}>{COPY.exportDialog.formatValue}</Kv>
      </dl>
      <div className="flex items-center justify-between pt-[10px] text-body">
        <span id="adm07-include-values">{COPY.exportDialog.includeValues}</span>
        <Toggle
          label={COPY.exportDialog.includeValues}
          aria-labelledby="adm07-include-values"
          checked={includeValues}
          onChange={setIncludeValues}
        />
      </div>
    </Dialog>
  );
}

function detailOf403(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const detail = (error as { detail?: unknown }).detail;
  return detail === "forbidden";
}

export interface ADM07Props {
  search: Adm07Search;
  onSearch: (next: Adm07Search) => void;
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

export function ADM07({ search, onSearch, onNavigate, onBack }: ADM07Props): JSX.Element {
  const now = useNow();
  const overview = useQuery(settingsOverviewOptions());
  const [exporting, setExporting] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const actor =
    search.actor !== undefined && ACTOR_KINDS.has(search.actor)
      ? (search.actor as ActorKind)
      : undefined;
  const query = useMemo(
    () => ({
      ...(actor === undefined ? {} : { actor_kind: actor }),
      ...(search.object === undefined ? {} : { object_type: search.object }),
      ...(search.action === undefined ? {} : { action: search.action }),
      ...(search.office === undefined ? {} : { office_id: search.office }),
      ...(search.ip === undefined ? {} : { ip: search.ip }),
      ...(search.q === undefined ? {} : { q: search.q }),
    }),
    [actor, search.object, search.action, search.office, search.ip, search.q],
  );
  const list = useQuery(listAuditEventsOptions({ query }));
  const [more, setMore] = useState<AuditEventRow[]>([]);
  const rows = [...(list.data?.items ?? []), ...more];
  const total = list.data?.total ?? 0;
  const all = list.data?.counts?.all ?? total;
  const policyEvents = list.data?.counts?.policy ?? 0;
  const filtered = Object.keys(query).length > 0;
  const set = (patch: { [K in keyof Adm07Search]?: string | undefined }): void => {
    const next = { ...search, ...patch } as Record<string, string | undefined>;
    const clean: Adm07Search = {};
    for (const key of KEYS) {
      const value = next[key];
      if (value !== undefined && value !== "") clean[key] = value;
    }
    setMore([]);
    onSearch(clean);
  };
  const open = search.event === undefined ? undefined : Number(search.event);

  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={overview.data?.firm_name ?? ""}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
      navTitle={COPY.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (s) =>
            ["general", "people", "offices", "security", "audit-log"].includes(s.id) ||
            PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="audit-log"
      onSelect={(id) => {
        if (id !== "audit-log") onNavigate?.(id);
      }}
      dirty={false}
      headerActions={
        <Button
          variant="secondary"
          onClick={() => {
            setExporting(true);
          }}
        >
          <Icon name="download" size={14} />
          {COPY.exportButton}
        </Button>
      }
      stepUp={
        <Dialog
          open={stepUp}
          onOpenChange={setStepUp}
          title={COPY.stepUpTitle}
          description={COPY.stepUpBody}
        >
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setStepUp(false);
              }}
            >
              {COPY.exportDialog.cancel}
            </Button>
            <Button
              onClick={() => {
                signIn(currentRoute(), { forceLogin: true });
              }}
            >
              {COPY.signInAgain}
            </Button>
          </div>
        </Dialog>
      }
    >
      <div className="flex flex-col gap-[8px] p-[12px]">
        <div className="flex flex-wrap items-center gap-[8px]">
          <FilterChip
            label={COPY.filters.actor}
            icon="user"
            options={COPY.actorOptions}
            value={actor ?? null}
            placeholder={COPY.filters.all}
            clearLabel={COPY.filters.all}
            onChange={(value) => {
              set({ actor: value ?? undefined });
            }}
          />
          <FilterChip
            label={COPY.filters.object}
            icon="box"
            options={COPY.objectOptions}
            value={search.object ?? null}
            placeholder={COPY.filters.all}
            clearLabel={COPY.filters.all}
            onChange={(value) => {
              set({ object: value ?? undefined });
            }}
          />
          <FilterChip
            label={COPY.filters.action}
            icon="zap"
            options={COPY.actionOptions}
            value={search.action ?? null}
            placeholder={COPY.filters.all}
            clearLabel={COPY.filters.all}
            onChange={(value) => {
              set({ action: value ?? undefined });
            }}
          />
          <FilterChip
            label={COPY.filters.date}
            icon="calendar"
            options={COPY.dateOptions}
            value={search.date ?? "7d"}
            onChange={(value) => {
              set({ date: value === null || value === "7d" ? undefined : value });
            }}
          />
          <FilterChip
            label={COPY.filters.office}
            icon="map-pin"
            options={[]}
            value={null}
            placeholder={COPY.filters.all}
          />
          <span className="ml-auto inline-flex items-center gap-[5px] text-dense text-ink-3">
            {filtered && list.data !== undefined
              ? COPY.countOf(count(String(rows.length)), count(String(total)))
              : COPY.count(count(String(all)))}
            <Icon name="lock" size={12} label={COPY.immutable} />
          </span>
        </div>
        <p className="text-meta text-ink-3">{COPY.policyNote(policyEvents)}</p>
        <section
          aria-label={COPY.section}
          className="flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
        >
          <div className="flex h-[46px] items-center gap-[10px] border-b-[0.5px] border-hair px-[12px]">
            <SearchField
              label={COPY.search}
              placeholder={COPY.search}
              clearLabel={COPY.clearSearch}
              className="w-[220px]"
              value={search.q ?? ""}
              onChange={(q) => {
                set({ q: q === "" ? undefined : q });
              }}
            />
            <h2 className="flex-1 text-center text-pane font-medium">{COPY.section}</h2>
            {search.ip !== undefined && (
              <button
                type="button"
                className="text-meta text-ink-2 hover:underline"
                onClick={() => {
                  set({ ip: undefined });
                }}
              >
                {`IP ${search.ip} ✕`}
              </button>
            )}
          </div>
          {list.isPending && <Skeleton />}
          {list.isError && (
            <ErrorState
              title={COPY.error}
              retryLabel={COPY.retry}
              onRetry={() => {
                void list.refetch();
              }}
            />
          )}
          {list.data !== undefined && rows.length === 0 && (
            <div className="p-[24px]">
              {search.q !== undefined ? (
                <EmptyState title={COPY.noMatch(search.q)}>{COPY.noMatchBody}</EmptyState>
              ) : (
                <EmptyState title={COPY.empty} />
              )}
            </div>
          )}
          {rows.length > 0 && (
            <ol className="relative py-[6px]" aria-label={COPY.section}>
              <i
                aria-hidden="true"
                className="absolute top-[16px] bottom-[16px] left-[107px] w-px bg-hair"
              />
              {rows.map((row) => (
                <Row
                  key={row.seq}
                  row={row}
                  now={now}
                  onOpen={() => {
                    set({ event: String(row.seq) });
                  }}
                  onIp={(ip) => {
                    set({ ip });
                  }}
                />
              ))}
            </ol>
          )}
          {rows.length > 0 && (
            <div className="flex h-[36px] items-center gap-[6px] border-t-[0.5px] border-hair px-[18px] text-dense text-ink-3">
              <span>{COPY.showing(count(String(rows.length)), count(String(total)))}</span>
              {list.data?.next_cursor !== null && list.data?.next_cursor !== undefined && (
                <>
                  <span aria-hidden="true">·</span>
                  <button
                    type="button"
                    className="text-ink-2 hover:underline"
                    onClick={() => {
                      // Keyset on `seq` (AC-7): the next page carries on below the last row.
                      void listAuditEvents({
                        query: { ...query, cursor: list.data?.next_cursor ?? null },
                        throwOnError: true,
                      }).then(({ data }) => {
                        setMore((m) => [...m, ...data.items]);
                      });
                    }}
                  >
                    {COPY.loadMore}
                  </button>
                </>
              )}
            </div>
          )}
        </section>
      </div>
      {open !== undefined && Number.isFinite(open) && (
        <EventDrawer
          seq={open}
          row={rows.find((r) => r.seq === open)}
          onClose={() => {
            set({ event: undefined });
          }}
        />
      )}
      <ExportDialog
        open={exporting}
        onOpenChange={setExporting}
        onExported={() => {
          toast.show(COPY.exportDialog.ready);
        }}
        onStepUp={() => {
          setStepUp(true);
        }}
      />
    </SettingsLayout>
  );
}

/** The routed page, or a test's: the search kept in state. */
export function AuditLogPage({
  initial = "",
  onNavigate,
}: {
  initial?: string;
  onNavigate?: (section: string) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Adm07Search>(() => parseSearch(initial));
  return (
    <ADM07
      search={search}
      onSearch={setSearch}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    />
  );
}
