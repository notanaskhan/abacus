import type {
  EngagementRecordOut,
  EqrCandidateOut,
  EqrCheckOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import {
  AgentAvatar,
  Button,
  Checkbox,
  ConfirmDialog,
  DEFAULT_TZ,
  Dialog,
  Fieldset,
  Icon,
  type IndexColumn,
  IndexList,
  Menu,
  type MenuItem,
  Pane,
  PersonAvatar,
  Pill,
  Radio,
  SheetModal,
  StatusDisc,
  Toggle,
  ValueRow,
  type ViewState,
  date,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import {
  type TeamRouteRole,
  allows,
  gateOf,
  hoursText,
  hoursTotal,
  tenthsOf,
  useEqrCandidates,
  useTeamApproval,
  useTeamCandidates,
  useTeamRoster,
  useTeamWrites,
} from "../../domain/engagements";
import { COPY } from "./copy";

// ENG-05 · Team & roles (P-07-T39; docs/screens/ENG-05.md). T1 inside the ENG-02 record (ENG-02
// draws the subbar and the tabs and hosts this pane on its Team tab) with the 330 inspector, over
// `GET /v1/engagements/{id}/team`, `…/team/approval`, `…/team/candidates` and `…/eqr/candidates`
// (P-07-T30, DEC-327). Each artboard is its data and the overlay it opens on
// (fixtures/scenarios/ENG-05.ts):
//
//   a  Northwind: five confirmed, Kira Ross proposed Sep 11 and pending; 172.0 budget hours; the
//      EQR inspector on Thomas Whitcombe
//   b  Fri Sep 11, before Kira's request: "+ Add person" → Kira Ross opens "Assignment pending
//      independence" (G2 on an attest engagement, DEC-39)
//   c  Fairhaven: "Replace EQR…" with Thomas Whitcombe not eligible (cooling-off, PY2024)
//   d  a after Kira confirmed: her row in ink, the banner gone
//   e  Granite Peak's new plan audit: "No team yet." and "Add the engagement partner"
//
// Every write is a person's click (INV-1): the agent row has no controls and never signs off. The
// agent's minutes stay out of the hours columns and are not drawn until P-10; actual hours show
// "—" until I-04 (P-07 §2.1).

/** The overlay an artboard opens on (the gallery passes it; the route never does). */
export type Eng05Open = { blocked: string } | { eqr: string } | { sheet: true };

export interface ENG05Props {
  record: EngagementRecordOut;
  opens?: Eng05Open | undefined;
}

type Member = TeamRosterMemberOut;
type Selection = { kind: "member"; userId: string } | { kind: "agent" } | null;

/** Where a member sits on this screen: the engagement partner, the EQR (the inspector's default
 * and never a team-route role, DEC-327) or the team. Data about the member, not the viewer's
 * permission, which `allowed_actions` answers. */
const SEAT: Readonly<Record<Member["role"], "ep" | "eqr" | "team" | "other">> = {
  engagement_partner: "ep",
  eqr_reviewer: "eqr",
  manager: "team",
  senior: "team",
  staff: "team",
  reviewer: "team",
  specialist: "team",
  client_service: "other",
};

/** The role "+ Add person" proposes: staff on a team with a lead, else its engagement partner. */
const ROLE_ON_ADD: Readonly<{ team: TeamRouteRole; lead: TeamRouteRole }> = {
  team: "staff",
  lead: "engagement_partner",
};

const ROUTE_ROLES: readonly TeamRouteRole[] = [
  "engagement_partner",
  "manager",
  "senior",
  "staff",
  "reviewer",
  "specialist",
];

function notFound(error: unknown): boolean {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" && detail.replace(" ", "_") === "not_found";
}

function confirmed(m: Member): boolean {
  return m.independence === "confirmed";
}

function pending(m: Member): boolean {
  return m.independence === "requested" || m.independence === "declined";
}

function shortClient(name: string): string {
  return name.split(" ")[0] ?? name;
}

function discOf(c: EqrCheckOut): "done" | "fail" | "wait" | "todo" {
  if (c.result === "pass") return "done";
  if (c.result === "fail") return "fail";
  if (c.result === "pending") return "wait";
  return "todo";
}

function coolingYear(c: EqrCandidateOut): string | null {
  const k = c.checks.find((x) => x.code === "cooling_off" && x.result === "fail");
  return k?.year == null ? null : `PY${String(k.year)}`;
}

function Kv({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center gap-[10px] px-[12px] py-[6px] text-body hairline-t first:shadow-none">
      <span className="w-[42%] flex-none text-ink-2">{k}</span>
      <span className="min-w-0 flex-1 text-right tabular-nums">{children}</span>
    </div>
  );
}

export function ENG05({ record, opens }: ENG05Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const engagementId = record.id;
  const roster = useTeamRoster(engagementId);
  const approval = useTeamApproval(engagementId);
  const writes = useTeamWrites(engagementId);
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const candidates = useTeamCandidates(engagementId, allows(record, "engagement.member_add"));
  const [blocked, setBlocked] = useState<string | null>(
    opens !== undefined && "blocked" in opens ? opens.blocked : null,
  );
  const [eqrPick, setEqrPick] = useState<string | null>(
    opens !== undefined && "eqr" in opens ? opens.eqr : null,
  );
  const [sheet, setSheet] = useState(opens !== undefined && "sheet" in opens);
  const [unticked, setUnticked] = useState<ReadonlySet<string>>(new Set());
  const [reminded, setReminded] = useState<ReadonlySet<string>>(new Set());
  const [selection, setSelection] = useState<Selection>(null);
  const [roleOf, setRoleOf] = useState<{ userId: string; role: TeamRouteRole } | null>(null);
  const [hoursOf, setHoursOf] = useState<{ userId: string; hours: string } | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  const members = roster.data ?? [];
  const eqrMember = members.find((m) => SEAT[m.role] === "eqr");
  const eqrCandidates = useEqrCandidates(
    engagementId,
    eqrMember !== undefined || eqrPick !== null,
  );
  const added = new Set(approval.data?.added_since ?? []);
  const day = (iso: string | null | undefined): string =>
    iso == null ? "" : date(iso, { now, tz });
  const nameOf = (id: string | null): string =>
    members.find((m) => m.user_id === id)?.display_name ??
    candidates.data?.find((c) => c.user_id === id)?.display_name ??
    "";

  const can = (action: string): boolean => allows(record, action);
  const g2 = gateOf(record, "G2") !== undefined;
  const engagementName = record.client_entity_name;
  const hasEp = members.some((m) => SEAT[m.role] === "ep");

  const q = query.trim().toLowerCase();
  const shown =
    q === ""
      ? members
      : members.filter((m) =>
          [m.display_name, COPY.roles[m.role] ?? m.role].some((v) => v.toLowerCase().includes(q)),
        );

  let state: ViewState;
  if (roster.isError) {
    state = notFound(roster.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void roster.refetch() };
  } else if (roster.data === undefined) state = { kind: "loading" };
  else if (members.length === 0) state = { kind: "empty" };
  else if (shown.length === 0) {
    state = {
      kind: "filtered-empty",
      title: COPY.filtered(query.trim()),
      clear: () => {
        setQuery("");
      },
    };
  } else state = { kind: "ready" };

  const fail = (): void => {
    toast.show({ kind: "error", text: COPY.toast.failed });
  };
  const run = async (work: () => Promise<unknown>, done?: string): Promise<boolean> => {
    try {
      await work();
      if (done !== undefined) toast.show({ kind: "success", text: done });
      return true;
    } catch {
      fail();
      return false;
    }
  };

  const roleWord = (m: Member): string => {
    const word = COPY.roles[m.role] ?? m.role;
    return added.has(m.user_id) ? COPY.proposed(word) : word;
  };

  // ---- "+ Add person" ----------------------------------------------------------------------
  const addRole: TeamRouteRole = hasEp ? ROLE_ON_ADD.team : ROLE_ON_ADD.lead;
  const pick = (userId: string): void => {
    setAddOpen(false);
    if (g2) {
      setBlocked(userId);
      return;
    }
    void run(() => writes.add(userId, addRole), COPY.toast.sent([nameOf(userId)]));
  };
  const addItems: MenuItem[][] = [
    (candidates.data ?? []).length === 0
      ? [{ label: COPY.header.addNone, disabled: true, onSelect: () => undefined }]
      : (candidates.data ?? []).map((c) => ({
          label: c.display_name,
          onSelect: () => {
            pick(c.user_id);
          },
        })),
  ];
  const addMenu = (trigger: ReactNode): JSX.Element => (
    <Menu
      label={hasEp ? COPY.header.addTitle : COPY.header.addPartner}
      align="end"
      open={addOpen}
      onOpenChange={setAddOpen}
      sections={addItems}
      trigger={trigger}
    />
  );

  // ---- columns ------------------------------------------------------------------------------
  const ink = (m: Member): string => (pending(m) ? "text-ink-3" : "text-ink");
  const menuFor = (m: Member): MenuItem[][] => {
    const routeRole = ROUTE_ROLES.find((r) => r === m.role);
    return [
      [
        {
          label: COPY.row.menu.changeRole,
          opensDialog: true,
          disabled: !can("engagement.member_add") || routeRole === undefined,
          onSelect: () => {
            setRoleOf({ userId: m.user_id, role: routeRole ?? ROLE_ON_ADD.team });
          },
        },
        {
          label: COPY.row.menu.editHours,
          opensDialog: true,
          disabled: !can("engagement.member_add"),
          onSelect: () => {
            setHoursOf({ userId: m.user_id, hours: m.budget_hours ?? "" });
          },
        },
      ],
      [
        {
          label: COPY.row.menu.remove,
          opensDialog: true,
          danger: true,
          disabled: !can("engagement.member_remove"),
          onSelect: () => {
            setRemoving(m.user_id);
          },
        },
      ],
    ];
  };

  const remind = async (m: Member): Promise<void> => {
    const ok = await run(() => writes.remind([m.user_id]), COPY.toast.reminded(m.display_name));
    if (ok) setReminded((s) => new Set([...s, m.user_id]));
  };

  const columns: IndexColumn<Member>[] = [
    {
      key: "person",
      header: COPY.columns.person,
      cell: (m) => (
        <span className="flex min-w-0 items-center gap-[10px]">
          <PersonAvatar name={m.display_name} size={22} decorative />
          <span className="flex min-w-0 flex-col">
            <span data-name="" className={`truncate ${ink(m)}`}>
              {m.display_name}
            </span>
            {added.has(m.user_id) && m.proposed_at != null && (
              <span className="truncate text-meta text-ink-3">
                {COPY.added(day(m.proposed_at))}
              </span>
            )}
          </span>
        </span>
      ),
    },
    {
      key: "role",
      header: COPY.columns.role,
      width: 170,
      cell: (m) => <span className={pending(m) ? "text-ink-3" : "text-ink"}>{roleWord(m)}</span>,
    },
    {
      key: "budget",
      header: COPY.columns.budget,
      width: 80,
      align: "right",
      cell: (m) => {
        const t = tenthsOf(m.budget_hours);
        return t === null ? (
          <span className="text-ink-4">{COPY.row.none}</span>
        ) : (
          <span className={`tabular-nums ${ink(m)}`} data-budget="">
            {hoursText(t)}
          </span>
        );
      },
    },
    {
      key: "actual",
      header: COPY.columns.actual,
      width: 80,
      align: "right",
      cell: () => <span className="text-ink-4">{COPY.row.none}</span>,
    },
    {
      key: "independence",
      header: COPY.columns.independence,
      width: 190,
      cell: (m) =>
        confirmed(m) ? (
          <Pill variant="green" size="sm" check>
            {COPY.row.confirmed}
          </Pill>
        ) : m.independence === "declined" ? (
          <Pill variant="red-tint" size="sm">
            {COPY.row.declined}
          </Pill>
        ) : m.independence === "requested" ? (
          <Pill variant="muted" size="sm">
            {m.proposed_at == null ? COPY.row.pending : COPY.row.pendingSince(day(m.proposed_at))}
          </Pill>
        ) : (
          <span className="text-ink-4">{COPY.row.none}</span>
        ),
    },
    {
      key: "portal",
      header: COPY.columns.portal,
      width: 150,
      cell: (m) => (
        <span className="flex items-center gap-[10px]">
          <Toggle
            size="small"
            label={COPY.row.portalOn(m.display_name)}
            checked={m.shown_on_portal === true}
            disabled={!confirmed(m) || !can("engagement.update")}
            onChange={(on) => {
              void run(
                () => writes.showOnPortal(m.user_id, on),
                on ? COPY.toast.shown(m.display_name) : COPY.toast.hidden(m.display_name),
              );
            }}
          />
          {pending(m) && can("independence.remind") && (
            <Button
              variant="ghost"
              size="xs"
              disabled={reminded.has(m.user_id)}
              onClick={(e) => {
                e.stopPropagation();
                void remind(m);
              }}
            >
              {reminded.has(m.user_id) ? COPY.row.reminded : COPY.row.remind}
            </Button>
          )}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      width: 44,
      align: "right",
      cell: (m) => (
        <Menu
          label={COPY.row.menuLabel(m.display_name)}
          align="end"
          sections={menuFor(m)}
          trigger={
            <button
              type="button"
              aria-label={COPY.row.menuLabel(m.display_name)}
              onClick={(e) => {
                e.stopPropagation();
              }}
              className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
            >
              <Icon name="ellipsis" size={14} />
            </button>
          }
        />
      ),
    },
  ];

  // ---- banner, totals, agent row, approval footer --------------------------------------------
  const pendingPeople = members.filter(pending);
  const confirmedCount = members.filter(confirmed).length;
  const banner =
    pendingPeople.length > 0 && q === "" ? (
      <div
        role="status"
        data-banner="g2"
        className="flex h-full items-center gap-[8px] bg-amber-tint px-[14px] text-dense text-amber-ink"
      >
        <Icon name="triangle-alert" size={14} />
        <span>
          {COPY.banner.text(
            confirmedCount,
            pendingPeople.map((m) => m.display_name),
          )}
        </span>
      </div>
    ) : undefined;

  const budget = hoursTotal(members.map((m) => m.budget_hours));
  const shownCount = members.filter((m) => m.shown_on_portal === true).length;
  const approved = approval.data;
  const changes = members
    .filter((m) => added.has(m.user_id))
    .map((m) => COPY.footer.change(m.display_name, day(m.proposed_at)));
  const footNote =
    approved === undefined || members.length === 0
      ? null
      : approved.approved_at != null && approved.approved_by_name != null
        ? COPY.footer.approved(
            approved.approved_by_name,
            date(approved.approved_at, { now, tz, withYear: true }),
            changes,
          )
        : COPY.footer.notApproved(members.map((m) => m.display_name));
  const agentOn = selection?.kind === "agent";

  const footer = (
    <div className="flex flex-col">
      <div
        data-totals=""
        className="flex min-h-[44px] items-center gap-[10px] px-[14px] text-body font-medium hairline-t"
      >
        <span className="min-w-0 flex-1 pl-[32px]">{COPY.totals.people(members.length)}</span>
        <span className="w-[170px]" />
        <span data-total="budget" className="w-[80px] text-right tabular-nums">
          {budget === null ? COPY.row.none : hoursText(budget)}
        </span>
        <span data-total="actual" className="w-[80px] text-right text-ink-4">
          {COPY.row.none}
        </span>
        <span className="w-[190px] pl-[10px]">
          {COPY.totals.confirmed(confirmedCount, members.length)}
        </span>
        <span className="w-[194px]">{COPY.totals.shown(shownCount)}</span>
      </div>
      <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-body font-medium hairline-t">
        {COPY.agents.band}
      </h3>
      <button
        type="button"
        data-agent-row=""
        aria-pressed={agentOn}
        onClick={() => {
          setSelection({ kind: "agent" });
        }}
        className={`flex min-h-[44px] items-center gap-[10px] px-[14px] py-[6px] text-left text-body hairline-t ${
          agentOn ? "bg-nav-fill" : "bg-card hover:bg-shell"
        }`}
      >
        <span className="flex min-w-0 flex-1 items-center gap-[10px]">
          <AgentAvatar />
          <span className="flex min-w-0 flex-col">
            <span>{COPY.agents.name}</span>
            <span className="truncate text-meta text-ink-3">{COPY.agents.sub}</span>
          </span>
        </span>
        <span className="w-[170px]">{COPY.agents.role}</span>
        <span className="w-[80px] text-right text-ink-4">{COPY.row.none}</span>
        <span className="w-[80px] text-right text-ink-4">{COPY.row.none}</span>
        <span className="w-[190px] pl-[10px]">
          <Pill variant="tag" size="sm">
            {COPY.agents.independence}
          </Pill>
        </span>
        <span className="w-[194px] text-ink-4">{COPY.row.none}</span>
      </button>
      {footNote !== null && (
        <p data-footer="approval" className="px-[14px] py-[10px] text-meta text-ink-3 hairline-t">
          {footNote}
        </p>
      )}
    </div>
  );

  // ---- the inspector ---------------------------------------------------------------------------
  const selectedMember =
    selection?.kind === "member"
      ? members.find((m) => m.user_id === selection.userId)
      : selection === null
        ? eqrMember
        : undefined;
  const currentEqr = (eqrCandidates.data ?? []).find(
    (c) => c.user_id === eqrMember?.user_id || c.current === true,
  );

  let inspectorTitle: string = COPY.inspector.eqr;
  let inspector: ReactNode = (
    <p className="px-[12px] py-[16px] text-body text-ink-3">{COPY.inspector.none}</p>
  );
  if (agentOn) {
    inspectorTitle = COPY.inspector.agent;
    inspector = (
      <>
        <div className="mb-[10px] flex items-center gap-[10px] rounded-nested bg-card p-[12px] shadow-e1">
          <AgentAvatar />
          <span className="flex min-w-0 flex-col">
            <span className="text-tab font-medium">{COPY.agents.name}</span>
            <span className="text-meta text-ink-3">{COPY.inspector.agentSub}</span>
          </span>
        </div>
        <Fieldset title={COPY.inspector.onEngagement} flush>
          <Kv k={COPY.inspector.permissions}>{COPY.inspector.permissionsValue}</Kv>
          <Kv k={COPY.inspector.signOff}>{COPY.inspector.signOffValue}</Kv>
        </Fieldset>
      </>
    );
  } else if (selectedMember !== undefined && SEAT[selectedMember.role] === "eqr") {
    const eligible = currentEqr?.eligibility !== "not_eligible";
    inspector = (
      <>
        <div className="mb-[10px] flex items-start gap-[10px] rounded-nested bg-card p-[12px] shadow-e1">
          <PersonAvatar name={selectedMember.display_name} size={22} decorative />
          <span className="flex min-w-0 flex-col items-start gap-[6px]">
            <span className="text-tab font-medium">{selectedMember.display_name}</span>
            <Pill variant={eligible ? "green-tint" : "red-tint"} size="sm">
              {eligible ? COPY.inspector.eligible : COPY.eqr.notEligibleOther}
            </Pill>
          </span>
        </div>
        {currentEqr !== undefined && (
          <Fieldset title={COPY.inspector.checks} flush>
            <ul aria-label={COPY.inspector.checks} className="flex flex-col">
              {currentEqr.checks.map((c) => (
                <li
                  key={c.code}
                  data-check={c.code}
                  className="flex min-h-[34px] items-center gap-[8px] px-[12px] py-[6px] text-body hairline-t first:shadow-none"
                >
                  <StatusDisc state={discOf(c)} size={15} />
                  <span>{COPY.check(c, shortClient(engagementName))}</span>
                </li>
              ))}
            </ul>
          </Fieldset>
        )}
        <Fieldset title={COPY.inspector.approval}>
          <p className="text-meta text-ink-3">{COPY.inspector.approvalHelp}</p>
        </Fieldset>
        {can("eqr.assign") && (
          <Button
            variant="secondary"
            size="sm"
            opensDialog
            className="w-full"
            onClick={() => {
              setEqrPick(selectedMember.user_id);
            }}
          >
            {COPY.inspector.replace}
          </Button>
        )}
      </>
    );
  } else if (selectedMember !== undefined) {
    inspectorTitle = COPY.inspector.member;
    const t = tenthsOf(selectedMember.budget_hours);
    inspector = (
      <>
        <div className="mb-[10px] flex items-start gap-[10px] rounded-nested bg-card p-[12px] shadow-e1">
          <PersonAvatar name={selectedMember.display_name} size={22} decorative />
          <span className="flex min-w-0 flex-col items-start gap-[6px]">
            <span className="text-tab font-medium">{selectedMember.display_name}</span>
            {confirmed(selectedMember) ? (
              <Pill variant="green" size="sm" check>
                {COPY.row.confirmed}
              </Pill>
            ) : (
              <Pill variant="muted" size="sm">
                {selectedMember.proposed_at == null
                  ? COPY.row.pending
                  : COPY.row.pendingSince(day(selectedMember.proposed_at))}
              </Pill>
            )}
          </span>
        </div>
        <Fieldset title={COPY.inspector.onEngagement} flush>
          <Kv k={COPY.inspector.role}>{roleWord(selectedMember)}</Kv>
          <Kv k={COPY.inspector.budget}>
            {t === null ? COPY.row.none : COPY.inspector.hours(hoursText(t))}
          </Kv>
          <Kv k={COPY.inspector.actual}>{COPY.row.none}</Kv>
          <Kv k={COPY.inspector.shown}>
            {selectedMember.shown_on_portal === true ? COPY.inspector.yes : COPY.inspector.no}
          </Kv>
        </Fieldset>
      </>
    );
  }

  // ---- overlays -------------------------------------------------------------------------------
  const blockedName = nameOf(blocked);
  const sendBlocked = async (): Promise<void> => {
    if (blocked === null) return;
    const ok = await run(() => writes.add(blocked, addRole), COPY.toast.sent([blockedName]));
    if (ok) setBlocked(null);
  };

  const eqrRows = eqrCandidates.data ?? [];
  const picked = eqrRows.find((c) => c.user_id === eqrPick);
  const assignable = picked !== undefined && picked.eligibility === "eligible" && !picked.current;
  const hint =
    picked === undefined
      ? ""
      : picked.eligibility !== "eligible"
        ? COPY.eqr.hintCooling
        : picked.current === true
          ? COPY.eqr.hintCurrent(picked.display_name)
          : COPY.eqr.hintOk;
  const assign = async (): Promise<void> => {
    if (picked === undefined || !assignable) return;
    const ok = await run(
      () => writes.replaceEqr(picked.user_id),
      COPY.toast.eqr(picked.display_name),
    );
    if (ok) setEqrPick(null);
  };

  const ticked = pendingPeople.filter((m) => !unticked.has(m.user_id));
  const sendSheet = async (): Promise<void> => {
    if (ticked.length === 0) return;
    const ok = await run(
      () => writes.remind(ticked.map((m) => m.user_id)),
      COPY.toast.sent(ticked.map((m) => m.display_name)),
    );
    if (ok) {
      setReminded((s) => new Set([...s, ...ticked.map((m) => m.user_id)]));
      setSheet(false);
    }
  };

  const addButton = can("engagement.member_add")
    ? addMenu(
        <Button variant="primary" size="sm" icon="plus">
          {COPY.header.add}
        </Button>,
      )
    : null;

  return (
    <div
      data-screen="ENG-05"
      className="flex min-h-0 min-w-0 flex-1 items-stretch gap-(--gutter-pane)"
    >
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <IndexList<Member>
          title={COPY.pane.title}
          noun={COPY.noun}
          state={state}
          envelope={
            roster.data === undefined
              ? undefined
              : { items: shown, next_cursor: null, total: shown.length, counts: {} }
          }
          columns={columns}
          rowKey={(m) => m.user_id}
          twoLine={() => true}
          selected={selectedMember?.user_id ?? null}
          onSelect={(m) => {
            setSelection({ kind: "member", userId: m.user_id });
          }}
          query={query}
          searchPlaceholder={COPY.search.placeholder}
          onQuery={setQuery}
          countText=""
          {...(banner === undefined ? {} : { banner })}
          actions={
            <span className="flex items-center gap-[8px]">
              {can("independence.remind") && members.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  opensDialog
                  disabled={pendingPeople.length === 0}
                  title={
                    pendingPeople.length === 0 ? COPY.header.requestNone : COPY.header.requestHint
                  }
                  onClick={() => {
                    setUnticked(new Set());
                    setSheet(true);
                  }}
                >
                  {COPY.header.request}
                </Button>
              )}
              {members.length > 0 && addButton}
            </span>
          }
          footer={footer}
          empty={{
            icon: "users",
            title: COPY.empty.title,
            ...(can("engagement.member_add")
              ? {
                  action: addMenu(
                    <Button variant="primary" size="sm">
                      {COPY.empty.action}
                    </Button>,
                  ),
                }
              : {}),
          }}
        />
      </div>
      <Pane width={330} title={inspectorTitle} well scrollLabel={inspectorTitle}>
        <div data-inspector="" className="flex flex-col p-[10px]">
          {inspector}
        </div>
      </Pane>

      <Dialog
        open={blocked !== null}
        onOpenChange={(open) => {
          if (!open) setBlocked(null);
        }}
        title={COPY.blocked.title}
      >
        <div className="flex flex-col gap-[12px]">
          <p className="text-para text-ink-2">{COPY.blocked.body(blockedName, engagementName)}</p>
          <div className="overflow-hidden rounded-nested bg-card shadow-e1">
            <Kv k={COPY.blocked.person}>{blockedName}</Kv>
            <Kv k={COPY.blocked.role}>{COPY.proposed(COPY.roles[addRole] ?? addRole)}</Kv>
          </div>
          <div className="flex justify-end gap-[8px]">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setBlocked(null);
              }}
            >
              {COPY.blocked.cancel}
            </Button>
            <Button
              variant="primary"
              size="sm"
              data-human-only=""
              loading={writes.pending}
              onClick={() => {
                void sendBlocked();
              }}
            >
              {COPY.blocked.send}
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={eqrPick !== null}
        onOpenChange={(open) => {
          if (!open) setEqrPick(null);
        }}
        title={COPY.eqr.title}
        description={`${record.name} · ${engagementName}`}
      >
        <div className="flex flex-col gap-[12px]">
          <div
            role="radiogroup"
            aria-label={COPY.eqr.title}
            className="overflow-hidden rounded-nested bg-card shadow-e1"
          >
            {eqrRows.map((c) => {
              const year = coolingYear(c);
              const ok = c.eligibility === "eligible";
              return (
                <div
                  key={c.user_id}
                  data-candidate={c.display_name}
                  className="flex min-h-[48px] items-center gap-[10px] px-[12px] py-[8px] hairline-t first:shadow-none"
                >
                  <Radio
                    checked={eqrPick === c.user_id}
                    label={c.display_name}
                    onSelect={() => {
                      setEqrPick(c.user_id);
                    }}
                  />
                  <PersonAvatar name={c.display_name} size={22} decorative />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-body">{c.display_name}</span>
                    {c.current === true && (
                      <span className="text-meta text-ink-3">{COPY.eqr.current}</span>
                    )}
                  </span>
                  <Pill variant={ok ? "green-tint" : "red-tint"} size="sm">
                    {ok
                      ? COPY.eqr.eligible
                      : year === null
                        ? COPY.eqr.notEligibleOther
                        : COPY.eqr.notEligible(year)}
                  </Pill>
                </div>
              );
            })}
          </div>
          {hint !== "" && <p className="text-meta text-ink-3">{hint}</p>}
          <div className="flex justify-end gap-[8px]">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setEqrPick(null);
              }}
            >
              {COPY.eqr.cancel}
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!assignable}
              onClick={() => {
                void assign();
              }}
            >
              {COPY.eqr.assign}
            </Button>
          </div>
        </div>
      </Dialog>

      <SheetModal
        open={sheet && pendingPeople.length > 0}
        onOpenChange={setSheet}
        title={COPY.sheet.title}
        action={
          <Button
            variant="primary"
            size="sm"
            disabled={ticked.length === 0}
            onClick={() => {
              void sendSheet();
            }}
          >
            {COPY.sheet.send}
          </Button>
        }
      >
        <div className="flex flex-col gap-[12px]">
          <Fieldset title={`${COPY.sheet.pending} · ${String(pendingPeople.length)}`} flush>
            {pendingPeople.map((m) => (
              <div
                key={m.user_id}
                className="flex min-h-[44px] items-center gap-[10px] px-[12px] py-[6px] hairline-t first:shadow-none"
              >
                <Checkbox
                  label={m.display_name}
                  checked={!unticked.has(m.user_id)}
                  onChange={(on) => {
                    setUnticked((s) => {
                      const next = new Set(s);
                      if (on) next.delete(m.user_id);
                      else next.add(m.user_id);
                      return next;
                    });
                  }}
                />
                <span className="flex min-w-0 flex-col">
                  <span className="text-body">{m.display_name}</span>
                  <span className="text-meta text-ink-3">
                    {COPY.sheet.sub(roleWord(m), day(m.proposed_at))}
                  </span>
                </span>
              </div>
            ))}
          </Fieldset>
          <p className="text-meta text-ink-3">{COPY.sheet.note(engagementName)}</p>
        </div>
      </SheetModal>

      <Dialog
        open={roleOf !== null}
        onOpenChange={(open) => {
          if (!open) setRoleOf(null);
        }}
        title={COPY.dialogs.roleTitle(nameOf(roleOf?.userId ?? null))}
        action={
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              if (roleOf === null) return;
              void run(() => writes.changeRole(roleOf.userId, roleOf.role)).then((ok) => {
                if (ok) setRoleOf(null);
              });
            }}
          >
            {COPY.dialogs.save}
          </Button>
        }
      >
        <div className="overflow-hidden rounded-nested bg-card shadow-e1">
          <ValueRow
            kind="select"
            label={COPY.columns.role}
            options={ROUTE_ROLES.map((r) => ({ value: r, label: COPY.roles[r] ?? r }))}
            value={roleOf?.role ?? ROLE_ON_ADD.team}
            onChange={(v) => {
              const next = ROUTE_ROLES.find((r) => r === v);
              if (roleOf !== null && next !== undefined) setRoleOf({ ...roleOf, role: next });
            }}
          />
        </div>
      </Dialog>

      <Dialog
        open={hoursOf !== null}
        onOpenChange={(open) => {
          if (!open) setHoursOf(null);
        }}
        title={COPY.dialogs.hoursTitle(nameOf(hoursOf?.userId ?? null))}
        action={
          <Button
            variant="primary"
            size="sm"
            disabled={hoursOf === null || tenthsOf(hoursOf.hours) === null}
            onClick={() => {
              if (hoursOf === null) return;
              void run(() => writes.editHours(hoursOf.userId, hoursOf.hours)).then((ok) => {
                if (ok) setHoursOf(null);
              });
            }}
          >
            {COPY.dialogs.save}
          </Button>
        }
      >
        <div className="overflow-hidden rounded-nested bg-card shadow-e1">
          <ValueRow
            kind="text"
            label={COPY.columns.budget}
            value={hoursOf?.hours ?? ""}
            onChange={(v) => {
              if (hoursOf !== null) setHoursOf({ ...hoursOf, hours: v });
            }}
          />
        </div>
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => {
          if (!open) setRemoving(null);
        }}
        title={COPY.dialogs.removeTitle(nameOf(removing))}
        confirmLabel={COPY.dialogs.removeConfirm}
        onConfirm={() => {
          if (removing !== null) void run(() => writes.remove(removing));
        }}
      />
    </div>
  );
}
