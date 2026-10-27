import type {
  FirmExportOut,
  SecurityIncidentOut,
  SecurityOverviewOut,
  SecuritySessionOut,
  SupportSessionOut,
} from "@abacus/api-client";
import {
  approveFirmExportMutation,
  approveSupportSessionMutation,
  firmExportScheduleOptions,
  listFirmExportsOptions,
  listSecurityIncidentsOptions,
  listSecuritySessionsOptions,
  listSupportSessionsOptions,
  putPortalSignInPolicyMutation,
  putSignInPolicyMutation,
  putSupportAccessMutation,
  requestFirmExportMutation,
  revokeSupportSessionMutation,
  safeguardsOptions,
  securityIncidentOptions,
  securityOverviewOptions,
  securityPostureOptions,
  settingsOverviewOptions,
  signOutSessionMutation,
  supportAccessOptions,
  unlockStaffMutation,
  wispPackMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  Drawer,
  ErrorState,
  Fieldset,
  FieldsetAdd,
  Icon,
  Menu,
  Pill,
  Segmented,
  SettingsLayout,
  SettingsLock,
  Skeleton,
  StatusDisc,
  Toggle,
  ValueRow,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { GROUPS } from "../ADM-01/copy";
import { COPY, IDLE_OPTIONS, PORTAL_OPTIONS, SESSION_OPTIONS } from "./copy";

// ADM-06 · Security center & data residency (G-02-T16; G-02 §3.4–3.9; docs/screens/ADM-06.md) on
// the T12 frame, section "Security": fieldsets A–F in the 760 column and the Data export, Support
// access and Posture cards in the 330 column. Every artboard is a data condition of one screen:
//
//   a  Felix Andersen at E0: SSO and MFA enforced, INC-2026-005 day 4 of 30, export scheduled
//   b  "Export now…": Dialog 460 "Export all firm data?" (Margaret Okonkwo approves)
//   c  ?export=history: the tray, Actions and History (Sep 1 386 GB · Aug 1 371 GB · Jul 1 359 GB)
//   d  ?incident=INC-2026-005: the drawer, timeline, the 4/30 clock bar, the two decisions
//   e  the Jan 11, 2026 snapshot: "41 of 46 enrolled" in red ink and the amber banner
//   f  Margaret Okonkwo: read-only (banner, locks), Export now hidden, Approve export shown
//   g  after b: "Waiting for approval · Margaret Okonkwo"
//   h  scrolled to WISP, residency and retention (read-only, FIL-02 planned)
//   i, j  revision R2's enterprise-identity rows, fixture only: passed in as `enterprise` by the
//         fixture scenarios; the route never passes it, so production shows the single Require
//         SSO toggle until G-03-T29.
//
// T03's rows: the sessions drawer (?sessions=1) with "Sign out of ‹firm›" and Unlock; the IdP-MFA
// attestation; the support-session states. What the viewer may do is the overview's `actions`
// (the matrix), never a role comparison; every write asks the step-up when the second factor is
// stale. No security "score" anywhere.

export interface Adm06Search {
  incident?: string;
  sessions?: string;
  export?: string;
}
const KEYS = ["incident", "sessions", "export"] as const;

export function parseSearch(search: Record<string, unknown> | string): Adm06Search {
  const entries =
    typeof search === "string"
      ? [...new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).entries()]
      : Object.entries(search);
  const out: Adm06Search = {};
  for (const [key, value] of entries) {
    if ((KEYS as readonly string[]).includes(key) && typeof value === "string" && value !== "") {
      out[key as (typeof KEYS)[number]] = value;
    }
  }
  return out;
}

/** Revision R2's fieldset A rows and states i and j (fixture only until G-03-T29). */
export interface EnterpriseIdentity {
  mode: "all" | "per_user";
  provider: string;
  idpInitiated: boolean;
  provisioned: number;
  seats: number;
  groups: readonly string[];
  seasonalEnds: string;
  lastSyncAt: string;
  errors: number;
  /** j: "1 user not provisioned · seat limit 46 of 46". */
  unprovisioned?: number;
  seatHolders: readonly { userId: string; name: string; sso: boolean; exempt: boolean }[];
}

function detailOf(error: unknown): string | undefined {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    return typeof detail === "string" ? detail : undefined;
  }
  return undefined;
}

const fmtDate = (iso: string, now: Date, withYear = true): string =>
  date(iso, { now, tz: DEFAULT_TZ, withYear });
const fmtTime = (iso: string): string => time(iso, { tz: DEFAULT_TZ });
/** "Oct 10" from an ISO date (no time) in the firm's zone. */
const dayOf = (day: string, now: Date): string =>
  date(`${day}T17:00:00Z`, { now, tz: DEFAULT_TZ });
/** "Jan 15, 2026": a date the handoff writes with its year. */
const fullDay = (day: string): string =>
  date(`${day}T17:00:00Z`, { now: new Date(`${day}T17:00:00Z`), tz: DEFAULT_TZ, withYear: true });
const monthYear = (ym: string): string => {
  const [y, m] = ym.split("-");
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${months[Number(m) - 1] ?? ""} ${y ?? ""}`;
};
const gb = (bytes: number | null | undefined): number =>
  bytes === null || bytes === undefined ? 0 : Math.round(bytes / 1_000_000_000);

function Card({
  title,
  pill,
  children,
}: {
  title: string;
  pill?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-pane bg-card shadow-e1">
      <div className="flex h-[33px] items-center justify-between border-b-[0.5px] border-hair px-[12px]">
        <h3 className="text-section font-medium">{title}</h3>
        {pill}
      </div>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function CardRow({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="grid min-h-[34px] grid-cols-[96px_minmax(0,1fr)] items-center gap-[8px] px-[12px] py-[6px] text-dense">
      <span className="text-ink-2">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function IncidentRow({
  incident,
  now,
  onOpen,
}: {
  incident: SecurityIncidentOut;
  now: Date;
  onOpen: () => void;
}): JSX.Element {
  const consumers = incident.consumers_affected ?? 0;
  const consumerText =
    incident.status === "investigating"
      ? COPY.confirmed(consumers)
      : incident.unencrypted === false
        ? COPY.encrypted(consumers)
        : String(consumers);
  return (
    <tr className="h-[44px] border-t-[0.5px] border-hair text-dense">
      <td className="px-[12px]">
        <button type="button" className="font-medium hover:underline" onClick={onOpen}>
          {incident.ref}
        </button>
      </td>
      <td className="px-[8px]">{incident.title}</td>
      <td className="px-[8px] whitespace-nowrap">{fmtDate(incident.discovered_at, now)}</td>
      <td className="px-[8px]">{consumerText}</td>
      <td className="px-[8px]">
        {incident.status === "investigating" && !incident.notification_event ? (
          <Pill variant="amber" size="sm">
            {COPY.clock(
              incident.clock_day,
              incident.clock_days,
              dayOf(incident.ftc_notify_by, now),
            )}
          </Pill>
        ) : (
          <Pill variant="muted" size="sm">
            {COPY.notNotification}
          </Pill>
        )}
      </td>
      <td className="px-[8px]">
        {incident.status === "investigating" ? (
          <span>{COPY.investigating}</span>
        ) : (
          <Pill variant="green-tint" size="sm">
            {COPY.closed}
          </Pill>
        )}
      </td>
    </tr>
  );
}

function IncidentDrawer({
  id,
  now,
  canDecide,
  onClose,
}: {
  id: string;
  now: Date;
  canDecide: boolean;
  onClose: () => void;
}): JSX.Element {
  const found = useQuery(securityIncidentOptions({ path: { incident_id: id } }));
  const incident = found.data;
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={incident === undefined ? "" : `${incident.ref} · ${incident.title}`}
      width={480}
      footer={
        canDecide && incident !== undefined && incident.status === "investigating" ? (
          <div className="flex flex-col gap-[6px]">
            {incident.pending_decision !== null && incident.pending_decision !== undefined && (
              <p className="text-dense text-ink-2">
                {COPY.waitingDecision(incident.pending_decision.waiting_for.display_name)}
              </p>
            )}
            <div className="flex items-center gap-[8px]">
              <Button variant="secondary" title={COPY.closeHint}>
                {COPY.closeNotReportable}
              </Button>
              <Button variant="secondary">{COPY.startNotification}</Button>
            </div>
          </div>
        ) : undefined
      }
    >
      {found.isPending && <Skeleton />}
      {found.isError && <ErrorState title={COPY.error} />}
      {incident !== undefined && (
        <div className="flex flex-col gap-[14px]">
          <div className="flex flex-col gap-[6px]">
            <div className="flex items-center justify-between text-dense">
              <span>{COPY.clockLabel(incident.clock_day, incident.clock_days)}</span>
              <span className="text-ink-3">
                {COPY.clock(
                  incident.clock_day,
                  incident.clock_days,
                  dayOf(incident.ftc_notify_by, now),
                )}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={COPY.clockLabel(incident.clock_day, incident.clock_days)}
              aria-valuemin={0}
              aria-valuemax={incident.clock_days}
              aria-valuenow={incident.clock_day}
              className="h-[3px] w-full rounded-pill bg-nested"
            >
              <div
                className="h-[3px] rounded-pill bg-amber"
                style={{
                  width: `${String(Math.min(100, (incident.clock_day / incident.clock_days) * 100))}%`,
                }}
              />
            </div>
          </div>
          <section aria-label={COPY.timeline}>
            <h3 className="pb-[6px] text-meta text-ink-3">{COPY.timeline}</h3>
            <ol className="flex flex-col gap-[8px]">
              {(incident.timeline ?? []).map((entry) => {
                const words = COPY.timelineWords[entry.code];
                return (
                  <li
                    key={entry.id}
                    className="grid grid-cols-[92px_minmax(0,1fr)] gap-[8px] text-dense"
                  >
                    <span className="text-ink-3">{fmtDate(entry.occurred_at, now, false)}</span>
                    <span>{words === undefined ? entry.code : words(entry.facts ?? {})}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        </div>
      )}
    </Drawer>
  );
}

function SessionsDrawer({
  firm,
  canEnd,
  canUnlock,
  now,
  onClose,
  onStepUp,
}: {
  firm: string;
  canEnd: boolean;
  canUnlock: boolean;
  now: Date;
  onClose: () => void;
  onStepUp: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const sessions = useQuery(listSecuritySessionsOptions());
  const signOut = useMutation(signOutSessionMutation());
  const unlock = useMutation(unlockStaffMutation());
  const [unlockNote, setUnlockNote] = useState<Record<string, string>>({});
  const rows: readonly SecuritySessionOut[] = sessions.data?.items ?? [];
  const fail = (error: unknown): void => {
    if (detailOf(error) === "forbidden") onStepUp();
    else toast.show(COPY.saveFailed);
  };
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.sessionsTitle}
      width={560}
    >
      {sessions.isPending && <Skeleton />}
      {sessions.isError && <ErrorState title={COPY.error} />}
      {sessions.data !== undefined && rows.length === 0 && (
        <p className="text-dense text-ink-3">{COPY.noSessions}</p>
      )}
      {rows.length > 0 && (
        <table className="w-full text-dense">
          <caption className="sr-only">{COPY.sessionsTitle}</caption>
          <thead>
            <tr className="text-left text-meta text-ink-3">
              {COPY.sessionColumns.map((c) => (
                <th key={c} scope="col" className="py-[4px] pr-[8px] font-normal">
                  {c}
                </th>
              ))}
              <th scope="col" className="sr-only">
                {COPY.actions}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y-[0.5px] divide-hair">
            {rows.map((s) => (
              <tr key={s.id} data-session={s.id}>
                <td className="py-[6px] pr-[8px]">{s.person.display_name}</td>
                <td className="py-[6px] pr-[8px] text-ink-2">{s.device_label ?? "—"}</td>
                <td className="py-[6px] pr-[8px] text-ink-2 tabular-nums">{s.ip ?? "—"}</td>
                <td className="py-[6px] pr-[8px] text-ink-2">{fmtTime(s.started_at)}</td>
                <td className="py-[6px] pr-[8px] text-ink-2">{fmtTime(s.last_seen_at)}</td>
                <td className="py-[6px] pr-[8px] text-ink-2">
                  {s.mfa_at === null || s.mfa_at === undefined ? "—" : fmtTime(s.mfa_at)}
                </td>
                <td className="py-[6px] text-right whitespace-nowrap">
                  {s.current ? (
                    <span className="text-ink-3">{COPY.thisSession}</span>
                  ) : (
                    <span className="inline-flex items-center gap-[6px]">
                      {canEnd && (
                        <Button
                          size="sm"
                          variant="secondary"
                          aria-label={`${COPY.signOutOf(firm)}: ${s.person.display_name}`}
                          onClick={() => {
                            signOut.mutate(
                              { path: { session_id: s.id } },
                              {
                                onSuccess: () => {
                                  toast.show(COPY.signedOut(s.person.display_name));
                                  void queryClient.invalidateQueries({
                                    queryKey: listSecuritySessionsOptions().queryKey,
                                  });
                                },
                                onError: fail,
                              },
                            );
                          }}
                        >
                          {COPY.signOutOf(firm)}
                        </Button>
                      )}
                      {canUnlock && (
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={`${COPY.unlock}: ${s.person.display_name}`}
                          onClick={() => {
                            unlock.mutate(
                              { path: { user_id: s.person.user_id } },
                              {
                                onSuccess: (lock) => {
                                  const note = lock.cleared
                                    ? COPY.unlocked
                                    : lock.locked &&
                                        lock.unlocks_at !== null &&
                                        lock.unlocks_at !== undefined
                                      ? COPY.unlocksAt(fmtTime(lock.unlocks_at))
                                      : COPY.notLocked;
                                  setUnlockNote((n) => ({ ...n, [s.person.user_id]: note }));
                                },
                                onError: fail,
                              },
                            );
                          }}
                        >
                          {COPY.unlock}
                        </Button>
                      )}
                      {unlockNote[s.person.user_id] !== undefined && (
                        <span role="status" className="text-meta text-ink-3">
                          {unlockNote[s.person.user_id]}
                        </span>
                      )}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="pt-[10px] text-meta text-ink-3">{fmtDate(now.toISOString(), now)}</p>
    </Drawer>
  );
}

function supportLine(session: SupportSessionOut, now: Date): string {
  const start = session.starts_at ?? session.created_at;
  const end = session.ended_at ?? session.expires_at ?? start;
  return COPY.supportSessionValue(
    fmtDate(start, now),
    fmtTime(start),
    fmtTime(end),
    session.staff_subject,
  );
}

function SupportPill({ session }: { session: SupportSessionOut }): JSX.Element {
  if (session.status === "requested") {
    return (
      <Pill variant="amber" size="sm">
        {COPY.awaitingApproval}
      </Pill>
    );
  }
  if (session.status === "active") {
    return (
      <Pill variant="green-tint" size="sm">
        {COPY.grantedUntil(fmtTime(session.expires_at ?? session.created_at))}
      </Pill>
    );
  }
  if (session.status === "revoked") {
    return (
      <Pill variant="muted" size="sm">
        {COPY.revoked}
      </Pill>
    );
  }
  return (
    <Pill variant="green-tint" size="sm">
      {COPY.closed}
    </Pill>
  );
}

interface Draft {
  require_sso?: boolean;
  session_absolute_minutes?: number;
  session_idle_minutes?: number;
  idp_mfa_attested?: boolean;
  portal_session_minutes?: number;
}

export interface ADM06Props {
  search: Adm06Search;
  onSearch: (next: Adm06Search) => void;
  /** Revision R2's rows and states i and j: fixture scenarios only (G-03-T29 makes them live). */
  enterprise?: EnterpriseIdentity;
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

export function ADM06({
  search,
  onSearch,
  enterprise,
  onNavigate,
  onBack,
}: ADM06Props): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const settings = useQuery(settingsOverviewOptions());
  const overview = useQuery(securityOverviewOptions());
  const posture = useQuery(securityPostureOptions());
  const incidents = useQuery(listSecurityIncidentsOptions());
  const safeguards = useQuery(safeguardsOptions());
  const schedule = useQuery(firmExportScheduleOptions());
  const exports = useQuery(listFirmExportsOptions());
  const support = useQuery(supportAccessOptions());
  const supportSessions = useQuery(listSupportSessionsOptions());
  const sessionList = useQuery(listSecuritySessionsOptions());
  const saveSignIn = useMutation(putSignInPolicyMutation());
  const savePortal = useMutation(putPortalSignInPolicyMutation());
  const setSupport = useMutation(putSupportAccessMutation());
  const approveSupport = useMutation(approveSupportSessionMutation());
  const revokeSupport = useMutation(revokeSupportSessionMutation());
  const requestExport = useMutation(requestFirmExportMutation());
  const approveExport = useMutation(approveFirmExportMutation());
  const wispPack = useMutation(wispPackMutation());
  const [draft, setDraft] = useState<Draft>({});
  const [stepUp, setStepUp] = useState(false);
  const [exportDialog, setExportDialog] = useState(false);
  const [perUser, setPerUser] = useState<boolean | null>(null);

  const firm = settings.data?.firm_name ?? "";
  const o: SecurityOverviewOut | undefined = overview.data;
  const actions = new Set(o?.actions ?? []);
  const canManage = actions.has("security.manage");
  const readOnly = o !== undefined && !canManage;
  const lock = readOnly ? { action: <SettingsLock /> } : {};
  const set = (patch: { [K in keyof Adm06Search]?: string | undefined }): void => {
    const next = { ...search, ...patch } as Record<string, string | undefined>;
    const clean: Adm06Search = {};
    for (const key of KEYS) {
      const value = next[key];
      if (value !== undefined && value !== "") clean[key] = value;
    }
    onSearch(clean);
  };
  const fail = (error: unknown): void => {
    const detail = detailOf(error);
    if (detail === "forbidden") setStepUp(true);
    else if (detail === "stale_version") toast.show(COPY.stale);
    else if (detail === "sso_not_verified") toast.show(COPY.ssoNotVerified);
    else if (detail === "policy_loosening_refused") toast.show(COPY.loosening);
    else if (detail === "session_limit_out_of_range") toast.show(COPY.tooShort);
    else toast.show(COPY.saveFailed);
  };
  const dirty = Object.keys(draft).length > 0;

  async function onSave(): Promise<void> {
    if (o === undefined) return;
    try {
      const signInChanged =
        draft.require_sso !== undefined ||
        draft.session_absolute_minutes !== undefined ||
        draft.session_idle_minutes !== undefined ||
        draft.idp_mfa_attested !== undefined;
      if (signInChanged) {
        await saveSignIn.mutateAsync({
          body: {
            require_sso: draft.require_sso ?? o.sign_in.require_sso,
            session_absolute_minutes:
              draft.session_absolute_minutes ?? o.sign_in.session_absolute_minutes,
            session_idle_minutes: draft.session_idle_minutes ?? o.sign_in.session_idle_minutes,
            idp_mfa_attested:
              draft.idp_mfa_attested ??
              (o.sign_in.idp_mfa_attested_at !== null &&
                o.sign_in.idp_mfa_attested_at !== undefined),
            version: o.sign_in.version,
          },
        });
      }
      if (draft.portal_session_minutes !== undefined) {
        await savePortal.mutateAsync({
          body: { session_minutes: draft.portal_session_minutes, version: o.portal.version },
        });
      }
    } catch (error) {
      fail(error);
      return;
    }
    setDraft({});
    await queryClient.invalidateQueries({ queryKey: securityOverviewOptions().queryKey });
    await queryClient.invalidateQueries({ queryKey: securityPostureOptions().queryKey });
    toast.show(COPY.saved);
  }

  const requireSso = draft.require_sso ?? o?.sign_in.require_sso ?? false;
  const attested =
    draft.idp_mfa_attested ??
    (o?.sign_in.idp_mfa_attested_at !== null && o?.sign_in.idp_mfa_attested_at !== undefined);
  const enrolled = o?.mfa.enrolled ?? 0;
  const seats = o?.mfa.seats ?? 0;
  const gap = seats - enrolled;
  const pending: FirmExportOut | undefined = exports.data?.items.find(
    (e) => e.status === "awaiting_approval",
  );
  const lastScheduled = exports.data?.items.find((e) => e.origin === "scheduled");
  const partnerApprover = schedule.data?.approvals?.find((a) => a.seat === "partner")?.approved_by;
  const qiApprover = schedule.data?.approvals?.find((a) => a.seat !== "partner")?.approved_by;
  const lastSupport = supportSessions.data?.[0];
  const allowSupport =
    support.data?.allow_support_requests ?? o?.support.allow_support_requests ?? true;
  const canSupport = actions.has("support_session.manage");
  const history = (exports.data?.items ?? []).filter((e) => e.origin === "scheduled");
  const incidentRows = incidents.data?.items ?? [];
  const openIncident =
    search.incident === undefined
      ? undefined
      : incidentRows.find((i) => i.ref === search.incident || i.id === search.incident);
  const perUserMode = perUser ?? enterprise?.mode === "per_user";

  const exportCard = (
    <Card
      title={COPY.dataExport}
      pill={
        pending !== undefined ? (
          <Pill variant="amber" size="sm" spin>
            {COPY.waitingFor(pending.approver.display_name)}
          </Pill>
        ) : schedule.data?.status === "active" ? (
          <Pill variant="green-tint" size="sm">
            {COPY.scheduledPill}
          </Pill>
        ) : undefined
      }
    >
      <CardRow label={COPY.schedule}>{COPY.scheduleValue}</CardRow>
      <CardRow label={COPY.contents}>{COPY.contentsValue}</CardRow>
      <CardRow label={COPY.format}>{COPY.formatValue}</CardRow>
      {lastScheduled !== undefined && (
        <CardRow label={COPY.lastExport}>
          {COPY.lastExportValue(
            fmtDate(lastScheduled.requested_at, now),
            gb(lastScheduled.size_bytes),
          )}
        </CardRow>
      )}
      {schedule.data?.next_run_on !== undefined && schedule.data.next_run_on !== null && (
        <CardRow label={COPY.next}>{dayOf(schedule.data.next_run_on, now)}</CardRow>
      )}
      {qiApprover !== undefined && partnerApprover !== undefined && (
        <CardRow label={COPY.approval}>
          {COPY.approvalValue(qiApprover.display_name, partnerApprover.display_name)}
        </CardRow>
      )}
      <div className="flex items-center justify-end gap-[8px] px-[12px] py-[8px]">
        <Menu
          label={COPY.history}
          width={462}
          align="end"
          open={search.export === "history"}
          onOpenChange={(openTray) => {
            set({ export: openTray ? "history" : undefined });
          }}
          trigger={
            <Button variant="secondary" size="sm">
              {COPY.history}
            </Button>
          }
          sections={[
            [
              ...(actions.has("firm_export.request")
                ? [
                    {
                      label: COPY.exportNow,
                      opensDialog: true,
                      onSelect: () => {
                        setExportDialog(true);
                      },
                    },
                  ]
                : []),
              ...(actions.has("firm_export.schedule")
                ? [{ label: COPY.changeSchedule, disabled: true, onSelect: () => undefined }]
                : []),
            ],
            history.map((e) => ({
              label: COPY.historyRow(fmtDate(e.requested_at, now), gb(e.size_bytes)),
              icon: "check" as const,
              onSelect: () => undefined,
            })),
          ].filter((section) => section.length > 0)}
        />
        {actions.has("firm_export.request") && pending === undefined && (
          <Button
            size="sm"
            onClick={() => {
              setExportDialog(true);
            }}
          >
            {COPY.exportNow}
          </Button>
        )}
        {!actions.has("firm_export.request") &&
          actions.has("firm_export.approve") &&
          pending !== undefined && (
            <Button
              size="sm"
              onClick={() => {
                approveExport.mutate(
                  { path: { export_id: pending.id } },
                  {
                    onSuccess: () => {
                      toast.show(COPY.exportApproved);
                      void queryClient.invalidateQueries({
                        queryKey: listFirmExportsOptions().queryKey,
                      });
                    },
                    onError: fail,
                  },
                );
              }}
            >
              {COPY.approveExport}
            </Button>
          )}
      </div>
    </Card>
  );

  const supportCard = (
    <Card title={COPY.supportAccess}>
      <p className="px-[12px] pt-[8px] text-dense text-ink-2">{COPY.supportBody}</p>
      {lastSupport !== undefined && (
        <div className="flex flex-col gap-[6px] px-[12px] py-[8px] text-dense">
          <span className="text-ink-2">{COPY.lastSession}</span>
          <span>{supportLine(lastSupport, now)}</span>
          <span className="flex items-center gap-[8px]">
            <SupportPill session={lastSupport} />
            {canSupport && lastSupport.status === "requested" && (
              <Button
                size="sm"
                onClick={() => {
                  approveSupport.mutate(
                    { path: { session_id: lastSupport.id } },
                    {
                      onSuccess: () => {
                        void queryClient.invalidateQueries({
                          queryKey: listSupportSessionsOptions().queryKey,
                        });
                      },
                      onError: fail,
                    },
                  );
                }}
              >
                {COPY.approve}
              </Button>
            )}
            {canSupport &&
              (lastSupport.status === "requested" || lastSupport.status === "active") && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    revokeSupport.mutate(
                      { path: { session_id: lastSupport.id } },
                      {
                        onSuccess: () => {
                          void queryClient.invalidateQueries({
                            queryKey: listSupportSessionsOptions().queryKey,
                          });
                        },
                        onError: fail,
                      },
                    );
                  }}
                >
                  {COPY.revoke}
                </Button>
              )}
          </span>
        </div>
      )}
      <div className="flex items-center justify-between px-[12px] py-[8px] text-dense">
        <span id="adm06-allow-support">{COPY.allowRequests}</span>
        <Toggle
          label={COPY.allowRequests}
          aria-labelledby="adm06-allow-support"
          size="small"
          checked={allowSupport}
          disabled={!canSupport || support.data === undefined}
          onChange={(checked) => {
            if (support.data === undefined) return;
            setSupport.mutate(
              { body: { allow_support_requests: checked, version: support.data.version } },
              {
                onSuccess: () => {
                  void queryClient.invalidateQueries({
                    queryKey: supportAccessOptions().queryKey,
                  });
                },
                onError: fail,
              },
            );
          }}
        />
      </div>
    </Card>
  );

  const p = posture.data;
  const postureCard = (
    <Card title={COPY.posture}>
      {p === undefined ? (
        posture.isError ? (
          <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.error}</p>
        ) : (
          <Skeleton />
        )
      ) : (
        <ul className="flex flex-col gap-[6px] px-[12px] py-[8px] text-dense">
          <li className="flex items-center gap-[8px]">
            <StatusDisc state={p.sso_enforced ? "done" : "warn"} />
            {p.sso_enforced ? COPY.postureSso : COPY.postureSsoOff}
          </li>
          <li className="flex items-center gap-[8px]">
            <StatusDisc state={p.mfa_enrolled === p.mfa_seats ? "done" : "warn"} />
            {COPY.postureMfa(p.mfa_enrolled, p.mfa_seats)}
          </li>
          <li className="flex items-center gap-[8px]">
            <StatusDisc state="done" />
            {COPY.postureUs}
          </li>
          {enterprise !== undefined && (
            <li className="flex items-center gap-[8px]">
              <StatusDisc state="done" />
              {COPY.scimPosture}
            </li>
          )}
          {p.open_incidents > 0 && (
            <li className="flex items-center gap-[8px]">
              <StatusDisc state="warn" />
              {COPY.postureIncidents(p.open_incidents)}
            </li>
          )}
          {p.pub4557_open > 0 && (
            <li className="flex items-center gap-[8px]">
              <StatusDisc state="warn" />
              {COPY.posturePub4557(p.pub4557_open)}
            </li>
          )}
        </ul>
      )}
    </Card>
  );

  const sg = safeguards.data;
  const sessionCount = sessionList.data?.total ?? 0;
  return (
    <SettingsLayout
      bare
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={firm}
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
      active="security"
      onSelect={(id) => {
        if (id !== "security") onNavigate?.(id);
      }}
      dirty={dirty}
      readOnly={readOnly}
      readOnlyText={COPY.readOnly}
      labels={{ unsaved: COPY.unsaved }}
      onDiscard={() => {
        setDraft({});
      }}
      onSave={() => {
        void onSave();
      }}
      aside={
        <div className="flex flex-col gap-[10px]">
          {exportCard}
          {supportCard}
          {postureCard}
        </div>
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
              {COPY.cancel}
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
      {overview.isPending && <Skeleton />}
      {overview.isError && (
        <ErrorState
          title={COPY.error}
          onRetry={() => {
            void overview.refetch();
          }}
        />
      )}
      {o !== undefined && (
        <>
          {gap > 0 && (
            <div
              role="status"
              className="mb-[10px] flex items-center gap-[7px] rounded-tile bg-amber-tint px-[12px] py-[8px] text-dense text-amber-ink"
            >
              <Icon name="triangle-alert" size={13} />
              {COPY.mfaGapBanner(gap)}
            </div>
          )}
          <Fieldset title={COPY.signIn} flush {...lock}>
            <ValueRow kind="value" label={COPY.identityProvider} readOnly={readOnly}>
              {o.sign_in.identity_provider === null || o.sign_in.identity_provider === undefined
                ? COPY.noProvider
                : COPY.sso(o.sign_in.identity_provider)}
            </ValueRow>
            {enterprise === undefined ? (
              <ValueRow
                kind="toggle"
                label={COPY.requireSso}
                readOnly={readOnly}
                disabled={readOnly}
                checked={requireSso}
                {...(o.sign_in.require_sso &&
                o.sign_in.sso_enforced_at !== null &&
                o.sign_in.sso_enforced_at !== undefined
                  ? {
                      help: COPY.ssoSince(
                        fmtDate(o.sign_in.sso_enforced_at, now),
                        o.sign_in.sso_enforced_by?.display_name ?? "",
                      ),
                    }
                  : {})}
                onChange={(checked) => {
                  setDraft((d) => ({ ...d, require_sso: checked }));
                }}
              />
            ) : (
              <>
                <ValueRow
                  kind="info"
                  label={COPY.requireSsoR2}
                  readOnly={readOnly}
                  {...(o.sign_in.sso_enforced_at !== null &&
                  o.sign_in.sso_enforced_at !== undefined
                    ? {
                        help: COPY.ssoSince(
                          fmtDate(o.sign_in.sso_enforced_at, now),
                          o.sign_in.sso_enforced_by?.display_name ?? "",
                        ),
                      }
                    : {})}
                >
                  <Segmented
                    size="small"
                    label={COPY.requireSsoR2}
                    active={perUserMode ? COPY.perUser : COPY.allUsers}
                    options={[{ label: COPY.allUsers }, { label: COPY.perUser }]}
                    onChange={(label) => {
                      setPerUser(label === COPY.perUser);
                    }}
                  />
                </ValueRow>
                <ValueRow kind="value" label={COPY.exceptions(1)} indented readOnly={readOnly}>
                  {""}
                </ValueRow>
                {perUserMode && (
                  <div className="max-h-[320px] overflow-auto px-[12px] py-[6px]">
                    <table className="w-full text-dense">
                      <caption className="sr-only">{COPY.perUserTable}</caption>
                      <thead>
                        <tr className="text-left text-meta text-ink-3">
                          <th scope="col" className="py-[4px] font-normal">
                            {COPY.person}
                          </th>
                          <th scope="col" className="py-[4px] text-right font-normal">
                            {COPY.ssoColumn}
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y-[0.5px] divide-hair">
                        {enterprise.seatHolders.map((s) => (
                          <tr key={s.userId} className="h-[30px]">
                            <td>{s.name}</td>
                            <td className="text-right">
                              {s.exempt ? (
                                <span className="inline-flex items-center gap-[4px] text-ink-3">
                                  <Icon name="lock" size={12} label={COPY.exempt} />
                                  {COPY.exempt}
                                </span>
                              ) : (
                                <Toggle
                                  label={`${COPY.ssoColumn}: ${s.name}`}
                                  size="small"
                                  checked={s.sso}
                                  disabled
                                />
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <ValueRow
                  kind="toggle"
                  label={COPY.idpInitiated}
                  readOnly={readOnly}
                  disabled
                  checked={enterprise.idpInitiated}
                  help={COPY.idpInitiatedHelp(enterprise.provider)}
                />
                <div className="px-[12px] pt-[8px] pb-[2px] text-meta font-medium text-ink-2">
                  {COPY.scim}
                </div>
                <ValueRow kind="value" label={COPY.scimStatus} indented readOnly={readOnly}>
                  <Pill variant="green-tint" size="sm">
                    {COPY.scimConnected(enterprise.provider)}
                  </Pill>
                </ValueRow>
                <ValueRow kind="value" label={COPY.scimUsers} indented readOnly={readOnly}>
                  {COPY.scimSeats(enterprise.provisioned, enterprise.seats)}
                </ValueRow>
                <ValueRow kind="value" label={COPY.scimGroups} indented readOnly={readOnly}>
                  {enterprise.groups.join(" · ")}
                </ValueRow>
                <ValueRow kind="value" label={COPY.scimDeprovision} indented readOnly={readOnly}>
                  {COPY.scimDeprovisionValue(enterprise.provider, enterprise.seasonalEnds)}
                </ValueRow>
                <ValueRow kind="value" label={COPY.scimLastSync} indented readOnly={readOnly}>
                  {enterprise.unprovisioned === undefined ? (
                    COPY.scimSynced(fmtTime(enterprise.lastSyncAt), enterprise.errors)
                  ) : (
                    <span className="inline-flex flex-wrap items-center gap-[8px]">
                      <span className="text-red-ink">
                        {COPY.scimError(
                          enterprise.unprovisioned,
                          enterprise.provisioned,
                          enterprise.seats,
                        )}
                      </span>
                      <button
                        type="button"
                        className="text-ink hover:underline"
                        onClick={() => {
                          onNavigate?.("people");
                        }}
                      >
                        {COPY.openSeats}
                      </button>
                    </span>
                  )}
                </ValueRow>
              </>
            )}
            <ValueRow kind="value" label={COPY.mfa} readOnly={readOnly} lock>
              <span className={gap > 0 ? "text-red-ink" : "text-green-ink"}>
                {gap > 0 ? COPY.mfaGap(enrolled, seats) : COPY.mfaEnrolled(enrolled, seats)}
              </span>
            </ValueRow>
            <ValueRow
              kind="toggle"
              label={COPY.idpMfa}
              help={COPY.idpMfaHelp}
              readOnly={readOnly}
              disabled={readOnly}
              checked={attested}
              onChange={(checked) => {
                setDraft((d) => ({ ...d, idp_mfa_attested: checked }));
              }}
            />
            <ValueRow
              kind="select"
              label={COPY.sessionLength}
              readOnly={readOnly}
              value={String(draft.session_absolute_minutes ?? o.sign_in.session_absolute_minutes)}
              options={SESSION_OPTIONS}
              onChange={(value) => {
                setDraft((d) => ({ ...d, session_absolute_minutes: Number(value) }));
              }}
            />
            <ValueRow
              kind="select"
              label={COPY.idleTimeout}
              readOnly={readOnly}
              value={String(draft.session_idle_minutes ?? o.sign_in.session_idle_minutes)}
              options={IDLE_OPTIONS}
              onChange={(value) => {
                setDraft((d) => ({ ...d, session_idle_minutes: Number(value) }));
              }}
            />
            <ValueRow kind="value" label={COPY.breakGlass} readOnly={readOnly}>
              {o.sign_in.sso_exempt_account === null || o.sign_in.sso_exempt_account === undefined
                ? COPY.breakGlassNone
                : COPY.breakGlassValue(
                    o.sign_in.sso_exempt_account.last_tested_at === null ||
                      o.sign_in.sso_exempt_account.last_tested_at === undefined
                      ? null
                      : fmtDate(o.sign_in.sso_exempt_account.last_tested_at, now),
                  )}
            </ValueRow>
            <div className="flex min-h-[34px] items-center gap-[10px] px-[12px] text-body">
              <span className="flex-1 text-ink-2">{COPY.sessions}</span>
              <button
                type="button"
                className="font-medium hover:underline"
                onClick={() => {
                  set({ sessions: "1" });
                }}
              >
                {COPY.sessionsOpen(sessionCount)}
              </button>
            </div>
          </Fieldset>

          <Fieldset title={COPY.portal} flush {...lock}>
            <ValueRow
              kind="value"
              label={COPY.passwordless}
              readOnly={readOnly}
              lock
              help={COPY.lockedFloor}
            >
              <Toggle
                label={COPY.passwordless}
                size="small"
                checked={o.portal.passwordless_email_code}
                disabled
              />
            </ValueRow>
            <ValueRow
              kind="value"
              label={COPY.portalMfa}
              readOnly={readOnly}
              lock
              help={COPY.lockedFloor}
            >
              <Toggle label={COPY.portalMfa} size="small" checked={o.portal.mfa_floor} disabled />
            </ValueRow>
            <ValueRow
              kind="select"
              label={COPY.portalSession}
              readOnly={readOnly}
              value={String(draft.portal_session_minutes ?? o.portal.session_minutes)}
              options={PORTAL_OPTIONS}
              onChange={(value) => {
                setDraft((d) => ({ ...d, portal_session_minutes: Number(value) }));
              }}
            />
            <ValueRow kind="value" label={COPY.lockout} readOnly={readOnly} lock>
              {COPY.lockoutValue(o.portal.failed_code_limit, o.portal.lockout_minutes)}
            </ValueRow>
          </Fieldset>

          <Fieldset
            title={COPY.incidents}
            flush
            {...(readOnly
              ? lock
              : PLANNED_VISIBLE
                ? {
                    action: (
                      <FieldsetAdd disabled aria-disabled="true">
                        <Icon name="plus" size={12} />
                        {COPY.addIncident}
                      </FieldsetAdd>
                    ),
                  }
                : {})}
          >
            {incidents.isError ? (
              <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.error}</p>
            ) : (
              <table className="w-full">
                <caption className="sr-only">{COPY.incidents}</caption>
                <thead>
                  <tr className="h-[30px] text-left text-meta text-ink-3">
                    {COPY.incidentColumns.map((c, i) => (
                      <th
                        key={c}
                        scope="col"
                        className={i === 0 ? "px-[12px] font-normal" : "px-[8px] font-normal"}
                      >
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {incidentRows.map((incident) => (
                    <IncidentRow
                      key={incident.id}
                      incident={incident}
                      now={now}
                      onOpen={() => {
                        set({ incident: incident.ref });
                      }}
                    />
                  ))}
                </tbody>
              </table>
            )}
            <p className="px-[12px] py-[8px] text-meta text-ink-3">{COPY.ftcHelp}</p>
          </Fieldset>

          <Fieldset
            title={COPY.wisp}
            flush
            {...(readOnly
              ? lock
              : {
                  action: (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        wispPack.mutate(
                          {},
                          {
                            onSuccess: (pack) => {
                              toast.show(COPY.wispReady(pack.document_count ?? 0));
                            },
                            onError: fail,
                          },
                        );
                      }}
                    >
                      {COPY.exportWisp}
                    </Button>
                  ),
                })}
          >
            {safeguards.isError || sg === undefined ? (
              <p className="px-[12px] py-[8px] text-dense text-ink-3">
                {safeguards.isError ? COPY.error : ""}
              </p>
            ) : (
              <>
                <ValueRow kind="value" label={COPY.qi} readOnly={readOnly}>
                  {sg.qualified_individual?.display_name ?? "—"}
                </ValueRow>
                {sg.wisp !== null && sg.wisp !== undefined && (
                  <ValueRow kind="value" label={COPY.wispPlan} readOnly={readOnly}>
                    {COPY.wispValue(
                      sg.wisp.name,
                      sg.wisp.approved_by?.display_name ?? "",
                      sg.wisp.approved_on === null || sg.wisp.approved_on === undefined
                        ? ""
                        : fullDay(sg.wisp.approved_on),
                    )}
                    {PLANNED_VISIBLE && <span className="pl-[6px] text-ink-3">{COPY.open}</span>}
                  </ValueRow>
                )}
                {sg.annual_report_last_on !== null && sg.annual_report_last_on !== undefined && (
                  <ValueRow kind="value" label={COPY.annualReport} readOnly={readOnly}>
                    {COPY.annualReportValue(
                      fullDay(sg.annual_report_last_on),
                      monthYear(sg.annual_report_next_due_month ?? ""),
                    )}
                  </ValueRow>
                )}
                <ValueRow kind="value" label={COPY.pub4557} readOnly={readOnly}>
                  <span
                    className={sg.controls_evidenced < sg.controls_total ? "text-amber-ink" : ""}
                  >
                    {COPY.pub4557Value(sg.controls_evidenced, sg.controls_total)}
                  </span>
                </ValueRow>
                {(sg.open_controls ?? []).map((c) => (
                  <ValueRow key={c.control_key} kind="value" label="" indented readOnly={readOnly}>
                    {c.scheduled_on !== null && c.scheduled_on !== undefined
                      ? COPY.scheduled(c.title, fullDay(c.scheduled_on))
                      : COPY.due(c.title, fullDay(c.due_on ?? ""))}
                  </ValueRow>
                ))}
                <ValueRow kind="value" label={COPY.training} readOnly={readOnly}>
                  {COPY.trainingValue(sg.training_completed ?? 0, sg.training_total ?? 0)}
                </ValueRow>
                <ValueRow kind="value" label={COPY.ptin} readOnly={readOnly}>
                  {COPY.ptinValue(sg.ptin_attested ?? 0, sg.ptin_total ?? 0)}
                </ValueRow>
                {sg.access_review !== null && sg.access_review !== undefined && (
                  <ValueRow kind="value" label={COPY.accessReview} readOnly={readOnly}>
                    {COPY.accessReviewValue(
                      sg.access_review.quarter.replace(/^(\d{4})-(Q\d)$/, "$2 $1"),
                      fullDay(sg.access_review.due_on),
                      sg.access_review.status === "in_progress"
                        ? COPY.inProgress
                        : sg.access_review.status,
                    )}
                  </ValueRow>
                )}
              </>
            )}
          </Fieldset>

          <Fieldset title={COPY.residency} flush>
            <ValueRow
              kind="value"
              label={COPY.region}
              help={COPY.regionHelp}
              readOnly={readOnly}
              lock
            >
              {o.residency.region === "us" ? COPY.regionValue : o.residency.region}
            </ValueRow>
            <ValueRow kind="value" label={COPY.storage} readOnly={readOnly}>
              {COPY.storageValue}
            </ValueRow>
            <ValueRow kind="value" label={COPY.aiInference} readOnly={readOnly} lock>
              {COPY.aiInferenceValue}
            </ValueRow>
            <ValueRow kind="value" label={COPY.logs} readOnly={readOnly} lock>
              {COPY.logsValue}
            </ValueRow>
            <ValueRow kind="value" label={COPY.encryption} readOnly={readOnly}>
              {COPY.encryptionValue}
            </ValueRow>
          </Fieldset>

          <Fieldset title={COPY.retention} flush>
            <p className="px-[12px] pt-[8px] text-meta text-ink-3">{COPY.retentionHelp}</p>
            {COPY.retentionRows.map(([label, value]) => (
              <ValueRow key={label} kind="value" label={label} readOnly>
                {value}
              </ValueRow>
            ))}
            {PLANNED_VISIBLE && (
              <ValueRow kind="value" label={COPY.legalHolds} readOnly>
                {COPY.legalHoldsValue}
              </ValueRow>
            )}
          </Fieldset>
        </>
      )}
      {openIncident !== undefined && (
        <IncidentDrawer
          id={openIncident.id}
          now={now}
          canDecide={actions.has("incident.decide")}
          onClose={() => {
            set({ incident: undefined });
          }}
        />
      )}
      {search.sessions === "1" && (
        <SessionsDrawer
          firm={firm}
          canEnd={actions.has("session.end")}
          canUnlock={actions.has("staff.unlock")}
          now={now}
          onClose={() => {
            set({ sessions: undefined });
          }}
          onStepUp={() => {
            setStepUp(true);
          }}
        />
      )}
      <Dialog
        open={exportDialog}
        onOpenChange={setExportDialog}
        title={COPY.exportDialogTitle}
        size="md"
        action={
          <Button
            disabled={partnerApprover === undefined || requestExport.isPending}
            onClick={() => {
              if (partnerApprover === undefined) return;
              requestExport.mutate(
                {
                  body: { approver_user_id: partnerApprover.user_id, scope: "all" },
                  headers: { "Idempotency-Key": `firm-export:${partnerApprover.user_id}` },
                },
                {
                  onSuccess: () => {
                    setExportDialog(false);
                    toast.show(COPY.exportRequested);
                    void queryClient.invalidateQueries({
                      queryKey: listFirmExportsOptions().queryKey,
                    });
                  },
                  onError: fail,
                },
              );
            }}
          >
            {COPY.requestExport}
          </Button>
        }
      >
        <p className="text-body">{COPY.exportDialogBody(partnerApprover?.display_name ?? "")}</p>
      </Dialog>
    </SettingsLayout>
  );
}

/** The routed page, or a test's: the search kept in state. */
export function SecurityPage({
  initial = "",
  enterprise,
  onNavigate,
}: {
  initial?: string;
  enterprise?: EnterpriseIdentity;
  onNavigate?: (section: string) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Adm06Search>(() => parseSearch(initial));
  return (
    <ADM06
      search={search}
      onSearch={setSearch}
      {...(enterprise === undefined ? {} : { enterprise })}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    />
  );
}
