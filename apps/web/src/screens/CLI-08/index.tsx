import type {
  ConflictResultOut,
  IndependenceConclusionStatus,
  IndependenceSummaryOut,
  MemberConfirmationOut,
  NasRowOut,
  RotationRowOut,
} from "@abacus/api-client";
import {
  Button,
  Checkbox,
  Dialog,
  Drawer,
  DrawerCard,
  Icon,
  type IndexColumn,
  IndexList,
  Pill,
  Segmented,
  SheetModal,
  StatusPill,
  ValueRow,
  type ViewState,
  date,
  status,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { nowMs } from "../../app-core/clock";
import { currentRoute, signIn } from "../../app-core/auth";
import { useSession } from "../../app-core/session";
import {
  DecisionDock,
  DecisionDockFooter,
  declinedMembers,
  mayConclude,
  needsStepUp,
  pendingMembers,
  useConflictCheck,
  useEngagementRecord,
  useIndependence,
  useIndependenceWrites,
  useNas,
  useRotation,
} from "../../domain/engagements";
import { COPY } from "./copy";

// CLI-08 · Independence & conflicts (P-07-T48; docs/screens/CLI-08.md). T1 inside the client
// record with four tabs over the live independence routes (P-07-T41): Team confirmations (each
// member's own confirmation; "Send reminder" sent by the person clicking), NAS matrix, Conflicts
// (the engagement's conflict check, `?check=`), Rotation. Each artboard is its data
// (fixtures/scenarios/CLI-08.ts): a team · b NAS · c conflicts · d rotation · e Ana Cruz's own
// sheet · f all confirmed, Margaret concludes · g breach · and the undesigned declined-note state
// (DF-06). "Conclude…" is enabled only when the server's `allowed_actions` hold
// `independence.conclude` (the engagement partner) and no blocker is left; for everyone else it
// is disabled with "Reserved to ‹partner›". Nobody confirms for anyone else (the routes refuse
// it) and the agent never concludes (INV-1). A walled engagement answers 404 (INV-3).

export type Cli08Tab = "conflicts" | "nas" | "team" | "rotation";

export interface CLI08Props {
  clientId: string;
  engagementId: string;
  tab?: Cli08Tab;
  onTab?: (tab: Cli08Tab) => void;
  /** The conflict check CLI-08 c reads (`?check=`). */
  checkId?: string | null;
  /** e: the self-confirmation sheet opens at once. */
  sheet?: boolean;
}

/** Northwind's three statements (docs/screens/CLI-08.md `e.statements`; the version is data). */
export const STATEMENTS = [
  {
    code: "no_financial_interest",
    text: "I have no financial interest in the Northwind Robotics 401(k) Plan or Northwind Robotics, Inc.",
  },
  {
    code: "no_family_key_position",
    text: "No immediate family member works in a key position at the plan sponsor or its service providers.",
  },
  { code: "not_a_participant", text: "I am not a participant in the plan." },
] as const;
export const STATEMENT_VERSION = "northwind-2025-v1";

/** Northwind's NAS services by code (the service names of spec.md b). */
const SERVICES: Readonly<Record<string, string>> = {
  fs_drafting: "Assistance drafting the plan financial statements and notes",
  form_5500: "Form 5500 and Schedule H preparation",
  payroll_recordkeeping: "Payroll and recordkeeping",
  corporate_tax: "Corporate tax returns — Northwind Robotics, Inc.",
};

/** Role codes the screen names people by (display only; permissions come from the server). */
const PARTNER = new Set(["engagement_partner"]);
const MANAGER = new Set(["manager"]);

const TAB_KEYS: readonly Cli08Tab[] = ["conflicts", "nas", "team", "rotation"];

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0] ?? "")
    .join("")
    .slice(0, 2);
}

function roleWord(role: string): string {
  return COPY.roles[role] ?? role;
}

function day(iso: string | null | undefined): string {
  return iso == null ? COPY.team.none : date(iso, { now: nowMs() });
}

function stateOf(
  query: { isError: boolean; error: unknown; data: unknown },
  retry: () => void,
): ViewState {
  if (query.isError) {
    const detail = (query.error as { detail?: unknown } | null)?.detail;
    return detail === "not_found"
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry };
  }
  return query.data === undefined ? { kind: "loading" } : { kind: "ready" };
}

function Banner({
  tone,
  children,
  end,
}: {
  tone: "amber" | "red";
  children: ReactNode;
  end?: ReactNode;
}): JSX.Element {
  return (
    <div
      role="status"
      data-cli08-banner={tone}
      className={
        tone === "amber"
          ? "flex min-h-[36px] items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] text-dense font-medium text-amber-ink"
          : "flex min-h-[36px] items-center gap-[8px] rounded-nested bg-red-tint px-[12px] text-dense font-medium text-red-ink"
      }
    >
      <Icon name="triangle-alert" size={14} />
      <span className="min-w-0 flex-1">{children}</span>
      {end}
    </div>
  );
}

function ConfirmationPill({ m }: { m: MemberConfirmationOut }): JSX.Element {
  if (m.confirmation === "confirmed") {
    return <Pill variant="green">{COPY.team.pill.confirmed}</Pill>;
  }
  if (m.confirmation === "declined") {
    return <Pill variant="red-tint">{COPY.team.pill.declined}</Pill>;
  }
  return <Pill variant="amber">{COPY.team.pill.pending}</Pill>;
}

function teamColumns(
  onPerson: (m: MemberConfirmationOut) => void,
): IndexColumn<MemberConfirmationOut>[] {
  return [
    {
      key: "person",
      header: COPY.team.columns.person,
      width: 240,
      cell: (m) => (
        <button
          type="button"
          className="flex items-center gap-[8px] text-left"
          onClick={() => {
            onPerson(m);
          }}
        >
          <span
            aria-hidden="true"
            className="inline-flex size-[22px] items-center justify-center rounded-full bg-nested text-meta text-ink-2"
          >
            {initials(m.display_name)}
          </span>
          <span className="text-body font-medium text-ink">{m.display_name}</span>
        </button>
      ),
    },
    { key: "role", header: COPY.team.columns.role, width: 170, cell: (m) => roleWord(m.role) },
    {
      key: "annual",
      header: COPY.team.columns.annual,
      width: 170,
      cell: (m) => (m.annual_confirmed === true ? "✓" : COPY.team.none),
    },
    {
      key: "engagement",
      header: COPY.team.columns.engagement,
      width: 200,
      cell: (m) => <ConfirmationPill m={m} />,
    },
    {
      key: "interests",
      header: COPY.team.columns.interests,
      width: 260,
      cell: (m) =>
        m.confirmation === "confirmed"
          ? COPY.team.interests
          : m.confirmation === "declined" && m.decline_note != null
            ? `${COPY.team.declinedNote}: ${m.decline_note}`
            : COPY.team.none,
    },
    {
      key: "confirmed",
      header: COPY.team.columns.confirmed,
      width: 140,
      align: "right",
      cell: (m) =>
        m.confirmation === "requested" ? (
          <span className="text-meta text-ink-3">
            {COPY.team.requested(m.reminder_count ?? 0)}
          </span>
        ) : (
          day(m.answered_at)
        ),
    },
  ];
}

const NAS_COLUMNS: IndexColumn<NasRowOut>[] = [
  {
    key: "service",
    header: COPY.nas.columns.service,
    width: 300,
    cell: (r) => SERVICES[r.service_code] ?? r.service_code,
  },
  {
    key: "provided",
    header: COPY.nas.columns.provided,
    width: 110,
    cell: (r) => (r.provided ? COPY.nas.provided : COPY.nas.notProvided),
  },
  {
    key: "evaluation",
    header: COPY.nas.columns.evaluation,
    width: 300,
    cell: (r) => r.evaluation ?? COPY.team.none,
  },
  {
    key: "ske",
    header: COPY.nas.columns.ske,
    width: 160,
    cell: (r) => (r.ske_contact_id == null ? COPY.team.none : "✓"),
  },
  {
    key: "safeguards",
    header: COPY.nas.columns.safeguards,
    cell: (r) => r.safeguards ?? COPY.team.none,
  },
  {
    key: "status",
    header: COPY.nas.columns.status,
    width: 120,
    cell: (r) => {
      const word = status("nas_evaluation", r.status);
      return <StatusPill variant={word.variant ?? "neutral"}>{word.label}</StatusPill>;
    },
  },
];

function conflictColumns(
  names: Readonly<Record<string, string>>,
): IndexColumn<ConflictResultOut>[] {
  return [
    {
      key: "match",
      header: COPY.conflicts.columns.match,
      width: 340,
      cell: (r) => (r.redacted ? COPY.conflicts.restricted : (r.matched_name ?? COPY.team.none)),
    },
    {
      key: "kind",
      header: COPY.conflicts.columns.kind,
      width: 200,
      cell: (r) => COPY.conflicts.kinds[r.match_kind],
    },
    {
      key: "assessment",
      header: COPY.conflicts.columns.assessment,
      width: 200,
      cell: (r) => {
        const word = status("conflict_assessment", r.assessment);
        return <StatusPill variant={word.variant ?? "neutral"}>{word.label}</StatusPill>;
      },
    },
    {
      key: "cleared",
      header: COPY.conflicts.columns.cleared,
      cell: (r) =>
        r.cleared_by == null
          ? COPY.team.none
          : `${names[r.cleared_by] ?? COPY.team.none} · ${day(r.cleared_at)}`,
    },
  ];
}

const ROTATION_COLUMNS = (years: number): IndexColumn<RotationRowOut>[] => [
  { key: "person", header: COPY.rotation.columns.person, width: 260, cell: (r) => r.display_name },
  { key: "role", header: COPY.rotation.columns.role, width: 200, cell: (r) => roleWord(r.role) },
  {
    key: "years",
    header: COPY.rotation.columns.years,
    width: 140,
    align: "right",
    cell: (r) => String(r.years_served),
  },
  {
    key: "threat",
    header: COPY.rotation.columns.threat,
    cell: (r) =>
      r.familiarity_flag || r.years_served >= years ? COPY.rotation.flagged : COPY.team.none,
  },
];

function StepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Confirm it's you"
      description="This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it."
    >
      <div className="flex justify-end gap-[8px]">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          Sign in again
        </Button>
      </div>
    </Dialog>
  );
}

function SelfSheet({
  engagement,
  open,
  onOpenChange,
  writes,
}: {
  engagement: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  writes: ReturnType<typeof useIndependenceWrites>;
}): JSX.Element {
  const [ticked, setTicked] = useState<ReadonlySet<string>>(new Set());
  const [declining, setDeclining] = useState(false);
  const [note, setNote] = useState("");
  const all = ticked.size === STATEMENTS.length;
  const confirm = async (): Promise<void> => {
    try {
      await writes.confirm(
        STATEMENT_VERSION,
        STATEMENTS.map((s) => s.code),
      );
      onOpenChange(false);
      const at = nowMs();
      toast.show({
        kind: "success",
        text: COPY.self.toast(`${date(at, { now: at })}, ${time(at)}`),
      });
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };
  const decline = async (): Promise<void> => {
    try {
      await writes.decline(note.trim());
      setDeclining(false);
      onOpenChange(false);
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };
  return (
    <>
      <SheetModal
        open={open && !declining}
        onOpenChange={onOpenChange}
        title={COPY.self.title(engagement)}
        footer={
          <div className="flex w-full items-center gap-[8px]">
            <Button
              variant="ghost"
              opensDialog
              onClick={() => {
                setDeclining(true);
              }}
            >
              {COPY.self.decline}
            </Button>
            <span className="ml-auto">
              <Button
                variant="primary"
                disabled={!all || writes.busy}
                onClick={() => void confirm()}
              >
                {COPY.self.confirm}
              </Button>
            </span>
          </div>
        }
      >
        <div data-cli08-statements="" className="flex flex-col gap-[10px]">
          {STATEMENTS.map((s) => (
            <Checkbox
              key={s.code}
              label={s.text}
              showLabel
              checked={ticked.has(s.code)}
              onChange={(on) => {
                const next = new Set(ticked);
                if (on) next.add(s.code);
                else next.delete(s.code);
                setTicked(next);
              }}
            />
          ))}
        </div>
      </SheetModal>
      <Dialog open={declining} onOpenChange={setDeclining} title={COPY.self.declineTitle}>
        <div className="flex flex-col gap-[12px]">
          <ValueRow
            kind="paragraph"
            label={COPY.self.declineNote}
            value={note}
            onChange={setNote}
          />
          <div className="flex justify-end gap-[8px]">
            <Button
              variant="secondary"
              onClick={() => {
                setDeclining(false);
              }}
            >
              {COPY.self.cancel}
            </Button>
            <Button variant="primary" disabled={note.trim() === ""} onClick={() => void decline()}>
              {COPY.self.declineSend}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}

function ConcludeDialog({
  open,
  onOpenChange,
  writes,
  onStepUp,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  writes: ReturnType<typeof useIndependenceWrites>;
  onStepUp: () => void;
}): JSX.Element {
  const [chosen, setChosen] = useState<IndependenceConclusionStatus | null>(null);
  const [safeguards, setSafeguards] = useState("");
  const options = (Object.keys(COPY.conclude.options) as IndependenceConclusionStatus[]).map(
    (value) => ({
      value,
      label: COPY.conclude.options[value],
      detail: COPY.conclude.detail[value],
    }),
  );
  const ready =
    chosen !== null && (chosen !== "independent_with_safeguards" || safeguards.trim() !== "");
  const submit = async (): Promise<void> => {
    if (chosen === null) return;
    try {
      await writes.conclude({
        option: chosen,
        ...(chosen === "independent_with_safeguards" ? { safeguards: safeguards.trim() } : {}),
      });
      onOpenChange(false);
    } catch (error) {
      if (needsStepUp(error)) onStepUp();
      else toast.show({ kind: "error", text: COPY.failed });
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={COPY.conclude.title}>
      <DecisionDock
        question={COPY.conclude.title}
        options={options}
        chosen={chosen}
        onChoose={(v) => {
          setChosen(v as IndependenceConclusionStatus);
        }}
      >
        {chosen === "independent_with_safeguards" && (
          <ValueRow
            kind="paragraph"
            label={COPY.conclude.safeguards}
            value={safeguards}
            onChange={setSafeguards}
          />
        )}
      </DecisionDock>
      <DecisionDockFooter
        action={
          <Button variant="primary" disabled={!ready || writes.busy} onClick={() => void submit()}>
            {COPY.conclude.confirm}
          </Button>
        }
        note={COPY.conclude.note}
      />
    </Dialog>
  );
}

function PersonDrawer({
  member,
  onClose,
}: {
  member: MemberConfirmationOut | null;
  onClose: () => void;
}): JSX.Element {
  return (
    <Drawer
      open={member !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={member?.display_name ?? ""}
    >
      {member !== null && (
        <DrawerCard>
          <ValueRow kind="info" label={COPY.team.columns.role}>
            {roleWord(member.role)}
          </ValueRow>
          <ValueRow kind="info" label={COPY.team.columns.annual}>
            {member.annual_confirmed === true ? "✓" : COPY.team.none}
          </ValueRow>
          <ValueRow kind="info" label={COPY.team.columns.engagement}>
            <ConfirmationPill m={member} />
          </ValueRow>
        </DrawerCard>
      )}
    </Drawer>
  );
}

export function CLI08({
  engagementId,
  tab: initialTab = "team",
  onTab,
  checkId = null,
  sheet: initialSheet = false,
}: CLI08Props): JSX.Element {
  const [tab, setTabState] = useState<Cli08Tab>(initialTab);
  const setTab = (next: Cli08Tab): void => {
    setTabState(next);
    onTab?.(next);
  };
  const [query, setQuery] = useState("");
  const [selfOpen, setSelfOpen] = useState(initialSheet);
  const [concluding, setConcluding] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const [person, setPerson] = useState<MemberConfirmationOut | null>(null);
  const summary = useIndependence(engagementId);
  const record = useEngagementRecord(engagementId);
  const nas = useNas(engagementId, tab === "nas");
  const rotation = useRotation(engagementId, tab === "rotation");
  const check = useConflictCheck(checkId, tab === "conflicts");
  const writes = useIndependenceWrites(engagementId);
  const s: IndependenceSummaryOut | undefined = summary.data;
  const engagementName = record.data?.name ?? "";
  const members = s?.members ?? [];
  const partner = members.find((m) => PARTNER.has(m.role))?.display_name ?? "";
  const pending = s === undefined ? [] : pendingMembers(s);
  const declined = s === undefined ? [] : declinedMembers(s);
  const breach = (s?.blockers ?? []).some((b) => b.reason_code === "breach_open");
  const actions = new Set(s?.allowed_actions ?? []);
  const viewer = useSession().user?.id ?? null;
  const mine = members.find((m) => m.user_id === viewer);
  // The viewer's own confirmation still to give (requested or declined): only they confirm it.
  const me = mine !== undefined && mine.confirmation !== "confirmed" ? mine : undefined;
  const canConclude =
    s !== undefined && mayConclude(s) && (s.blockers ?? []).length === 0 && s.conclusion == null;
  const allConfirmed = s !== undefined && s.confirmed === s.total;

  const remind = async (target: MemberConfirmationOut): Promise<void> => {
    try {
      await writes.remind([target.user_id]);
      toast.show({ kind: "success", text: COPY.reminder.sent(target.display_name) });
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };

  const tabs = (
    <Segmented
      label={COPY.tabs.label}
      active={COPY.tabs[tab]}
      options={[
        { label: COPY.tabs.conflicts },
        { label: COPY.tabs.nas, count: 4 },
        { label: COPY.tabs.team, count: members.length },
        { label: COPY.tabs.rotation },
      ].map((o) => (o.label === COPY.tabs.nas ? { ...o, count: nas.data?.rows?.length ?? 0 } : o))}
      onChange={(label) => {
        const next = TAB_KEYS.find((k) => COPY.tabs[k] === label);
        if (next !== undefined) setTab(next);
      }}
    />
  );

  const banner = ((): ReactNode => {
    if (s === undefined) return undefined;
    if (breach) return <Banner tone="red">{COPY.banner.breach}</Banner>;
    if (me?.confirmation === "requested") {
      return <Banner tone="amber">{COPY.banner.self(engagementName)}</Banner>;
    }
    const firstDeclined = declined[0];
    if (firstDeclined !== undefined) {
      return <Banner tone="amber">{COPY.banner.declined(firstDeclined.display_name)}</Banner>;
    }
    const first = pending[0];
    if (first === undefined) return undefined;
    return (
      <Banner
        tone="amber"
        end={
          actions.has("independence.remind") ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={writes.busy}
              onClick={() => void remind(first)}
            >
              {COPY.reminder.send}
            </Button>
          ) : undefined
        }
      >
        {COPY.banner.pending(first.display_name, engagementName)}
      </Banner>
    );
  })();

  const concluded =
    s?.conclusion == null
      ? null
      : COPY.conclude.concluded(
          members.find((m) => m.user_id === s.conclusion?.concluded_by)?.display_name ?? partner,
          day(s.conclusion.concluded_at),
        );

  const headerActions = (
    <span className="flex items-center gap-[8px]">
      {mine !== undefined && (
        <Button
          variant="secondary"
          size="sm"
          {...(me === undefined ? { icon: "check" as const } : {})}
          disabled={me === undefined}
          opensDialog={me !== undefined}
          onClick={() => {
            setSelfOpen(true);
          }}
        >
          {COPY.team.confirmMine}
        </Button>
      )}
      {concluded !== null ? (
        <Pill variant="green">{concluded}</Pill>
      ) : (
        <Button
          variant="primary"
          size="sm"
          disabled={!canConclude}
          opensDialog
          title={canConclude ? undefined : COPY.conclude.reserved(partner, pending.length)}
          onClick={() => {
            setConcluding(true);
          }}
        >
          {COPY.conclude.button}
        </Button>
      )}
    </span>
  );

  const header = (
    <div data-cli08-subbar="" className="flex items-center justify-center gap-[8px] py-[8px]">
      <h1 className="text-title font-medium text-ink">{COPY.title}</h1>
      <span className="text-title text-ink-2">{engagementName}</span>
      {s !== undefined && (
        <Pill variant={allConfirmed ? "green-tint" : "amber"}>
          {COPY.subbar.count(s.confirmed, s.total)}
        </Pill>
      )}
      <span className="ml-[12px] rounded-pill bg-card px-[10px] py-[4px] text-body text-ink shadow-e1">
        {COPY.standards}
      </span>
    </div>
  );

  let body: JSX.Element;
  if (tab === "nas") {
    const rows = nas.data?.rows ?? [];
    body = (
      <IndexList<NasRowOut>
        title={COPY.tabs.nas}
        noun="services"
        state={stateOf(nas, () => void nas.refetch())}
        envelope={{ items: rows, next_cursor: null, total: rows.length, counts: {} }}
        columns={NAS_COLUMNS}
        rowKey={(r) => r.service_code}
        tabs={tabs}
        {...(nas.data?.attest_client === false ? { countText: COPY.nas.nonAttest } : {})}
        footer={
          <div className="flex items-center gap-[8px] p-[12px] text-dense text-ink-2">
            <span>
              {COPY.nas.card(
                members.find((m) => MANAGER.has(m.role))?.display_name ?? "",
                partner,
              )}
            </span>
            {pending.length > 0 && <Pill variant="amber">{COPY.nas.pending(pending.length)}</Pill>}
          </div>
        }
        empty={{ icon: "list", title: COPY.nas.nonAttest }}
      />
    );
  } else if (tab === "conflicts") {
    const results = check.data?.results ?? [];
    const names = Object.fromEntries(members.map((m) => [m.user_id, m.display_name]));
    const related = results.filter((r) => r.assessment !== "conflict").length;
    const conflicts = results.some((r) => r.assessment === "conflict");
    body = (
      <IndexList<ConflictResultOut>
        title={COPY.tabs.conflicts}
        noun="matches"
        state={checkId === null ? { kind: "empty" } : stateOf(check, () => void check.refetch())}
        envelope={{ items: results, next_cursor: null, total: results.length, counts: {} }}
        columns={conflictColumns(names)}
        rowKey={(r) => r.id}
        tabs={tabs}
        {...(check.data === undefined
          ? {}
          : {
              countText: COPY.conflicts.line(
                check.data.names_count,
                `${date(check.data.run_at, { now: nowMs() })}, ${time(check.data.run_at)}`,
              ),
            })}
        {...(check.data === undefined || conflicts
          ? {}
          : {
              actions: (
                <Pill variant="green-tint">
                  {related > 0 ? COPY.conflicts.noted(related) : COPY.conflicts.clean}
                </Pill>
              ),
            })}
        empty={{ icon: "search", title: COPY.conflicts.none, body: COPY.conflicts.noneBody }}
      />
    );
  } else if (tab === "rotation") {
    const rows = rotation.data?.rows ?? [];
    const years = rotation.data?.review_years ?? 7;
    body = (
      <IndexList<RotationRowOut>
        title={COPY.tabs.rotation}
        noun="people"
        state={stateOf(rotation, () => void rotation.refetch())}
        envelope={{ items: rows, next_cursor: null, total: rows.length, counts: {} }}
        columns={ROTATION_COLUMNS(years)}
        rowKey={(r) => r.user_id}
        tabs={tabs}
        countText={COPY.rotation.note(years)}
        empty={{ icon: "users", title: COPY.tabs.rotation }}
      />
    );
  } else {
    const q = query.trim().toLowerCase();
    const shown = members.filter((m) => q === "" || m.display_name.toLowerCase().includes(q));
    body = (
      <IndexList<MemberConfirmationOut>
        title={COPY.tabs.team}
        noun="people"
        state={stateOf(summary, () => void summary.refetch())}
        envelope={{ items: shown, next_cursor: null, total: shown.length, counts: {} }}
        columns={teamColumns(setPerson)}
        rowKey={(m) => m.user_id}
        tabs={tabs}
        query={query}
        onQuery={setQuery}
        searchPlaceholder={COPY.team.search}
        actions={headerActions}
        {...(banner === undefined ? {} : { banner })}
        footer={<p className="p-[12px] text-meta text-ink-3">{COPY.team.footer}</p>}
        empty={{ icon: "users", title: COPY.tabs.team }}
      />
    );
  }

  return (
    <div data-screen="CLI-08" className="flex min-h-0 flex-1 flex-col">
      {header}
      {body}
      <SelfSheet
        engagement={engagementName}
        open={selfOpen && me !== undefined}
        onOpenChange={setSelfOpen}
        writes={writes}
      />
      <ConcludeDialog
        open={concluding}
        onOpenChange={setConcluding}
        writes={writes}
        onStepUp={() => {
          setConcluding(false);
          setStepUp(true);
        }}
      />
      <StepUp open={stepUp} onOpenChange={setStepUp} />
      <PersonDrawer
        member={person}
        onClose={() => {
          setPerson(null);
        }}
      />
    </div>
  );
}

/** The routed page and the gallery's artboard. */
export function IndependencePage(props: CLI08Props): JSX.Element {
  return <CLI08 {...props} />;
}
