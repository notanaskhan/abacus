import type {
  AcceptanceFlagOut,
  AcceptanceRecordOut,
  AcceptanceSectionOut,
  EngagementRecordOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import {
  Button,
  Checkbox,
  DEFAULT_TZ,
  Dialog,
  type DiscState,
  Icon,
  type Phase,
  Picker,
  Pill,
  RecordCockpit,
  RecordRail,
  type RegistryCode,
  StatusDisc,
  StatusPill,
  type ToolbarProps,
  type ViewState,
  cn,
  date,
  status,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useId, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  type AcceptanceOption,
  CONCLUSION,
  DecisionDock,
  DecisionDockFooter,
  type FlagSeverity,
  answerText,
  fieldOf,
  isClear,
  isLocked,
  mayOn,
  needsStepUp,
  openChecks,
  refusalOf,
  unanswered,
  useAcceptance,
  useAcceptanceWrites,
  useEngagementRecord,
  useEngagementTeam,
  useReviewCandidates,
} from "../../domain/engagements";
import { currentRoute, signIn } from "../../app-core/auth";
import { COPY } from "./copy";

// CLI-07 · Acceptance & continuance (P-07-T46; docs/screens/CLI-07.md). T2 with the decision dock
// in SHL-11 grammar (the local DecisionDock) over `GET /v1/engagements/{id}/acceptance` (live since
// P-07-T35), the engagement record and its team. Each artboard is its data
// (fixtures/scenarios/CLI-07.ts):
//
//   a  Awaiting partner (the engagement partner decides)   b  Draft with a manual check open
//   c  Pre-screening (fixture only, DEC-64)                d  Accepted with conditions, locked
//   e  Declined, locked                                     f  a continuance awaiting the partner
//   g  a continuance in Draft with the responsiveness flag (fixture until I-03)
//
// Production flags are human-prepared, so there is no agent recommendation or reasoning block and
// a rationale is always required (SPEC-332 AC-7). Only a viewer whose record `allowed_actions`
// hold `acceptance.decide` gets an enabled Decide; everyone else sees "Partner decision", disabled.
// A walled or unknown engagement answers 404 and reads as restricted (INV-3). Planned targets
// (ENG-04, CLI-08, SHL-08) are hidden in production and disabled with their hint elsewhere.

/** Where a CLI-07 control goes: the route navigates (the link is wired in routes/firm). */
export type Cli07Target = { screen: "CLI-02"; clientId: string };

export interface CLI07Props {
  clientId: string;
  engagementId: string;
  onNavigate?: (target: Cli07Target) => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
  /** g's note in progress (the gallery passes it; the route never does). */
  note?: string | undefined;
}

const DISC: Record<AcceptanceSectionOut["answer_state"], DiscState> = {
  complete: "done",
  flag: "warn",
  manual_check_open: "half",
  manual_check_done: "done",
  pending: "todo",
};

const PREPARERS = new Set(["engagement_partner", "manager", "client_service"]);
/** The team row whose person decides (the record names no partner; the team does). */
const EP_ROLE: TeamRosterMemberOut["role"] = "engagement_partner";

const TEXT_INPUT =
  "h-[30px] w-full rounded-tile bg-nested px-[10px] text-body text-ink inset-shadow-hair placeholder:text-ink-3 focus:bg-card";

function notFound(error: unknown): boolean {
  const detail = refusalOf(error);
  return detail !== null && detail.replace(" ", "_") === "not_found";
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .toUpperCase();
}

function Planned({ children }: { children: ReactNode }): JSX.Element | null {
  return PLANNED_VISIBLE ? <>{children}</> : null;
}

function Card({
  children,
  className,
  label,
  id,
}: {
  children: ReactNode;
  className?: string;
  label?: string;
  id?: string;
}): JSX.Element {
  return (
    <section
      {...(label === undefined ? {} : { "aria-label": label })}
      {...(id === undefined ? {} : { id })}
      className={cn("overflow-hidden rounded-pane bg-card shadow-e1", className)}
    >
      {children}
    </section>
  );
}

const ROW = "flex min-h-[40px] items-center gap-[10px] px-[14px] py-[8px] hairline-t";

// ---- the record bar ----------------------------------------------------------------------------

function Bar({
  engagement,
  record,
  names,
  now,
  tz,
  onBack,
}: {
  engagement: EngagementRecordOut | undefined;
  record: AcceptanceRecordOut | undefined;
  names: ReadonlyMap<string, string>;
  now: Date;
  tz: string;
  onBack?: () => void;
}): JSX.Element {
  const client = engagement?.client_name ?? "";
  const word =
    engagement === undefined
      ? null
      : status("engagement", engagement.status as RegistryCode<"engagement">);
  const preparer = record === undefined ? undefined : names.get(record.prepared_by);
  const at =
    record?.sent_to_partner_at ??
    (record?.flags ?? [])
      .map((f) => f.authored_at)
      .sort()
      .at(-1) ??
    null;
  return (
    <div
      data-shell="record-header"
      data-variant="acceptance"
      className="relative flex h-(--subbar-h) flex-none items-center gap-[8px] px-(--edge-app)"
    >
      {engagement !== undefined && (
        <Button variant="secondary" size="sm" title={COPY.backHint(client)} onClick={onBack}>
          {COPY.back(client)}
        </Button>
      )}
      {engagement !== undefined && record !== undefined && (
        <h1 className="absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-[8px] text-title whitespace-nowrap">
          <span className="font-medium tracking-[-0.012em]">
            {record.kind === "continuance"
              ? COPY.bar.continuance(engagement.name)
              : COPY.bar.acceptance(engagement.name)}
          </span>
          <span className="text-ink-2">{client}</span>
          {word !== null && (
            <StatusPill variant={word.variant ?? "neutral"}>{word.label}</StatusPill>
          )}
        </h1>
      )}
      {record !== undefined && (
        <div className="ml-auto flex items-center gap-[8px]">
          {preparer !== undefined && (
            <span data-meta="prepared" className="text-body text-ink-3">
              {at === null
                ? COPY.bar.preparedBy(preparer)
                : COPY.bar.prepared(preparer, date(at, { now, tz }))}
            </span>
          )}
          <span className="rounded-pill bg-card px-[11px] py-[5px] text-meta text-ink shadow-e1">
            {COPY.bar.questionnaire(record.template_name)}
          </span>
        </div>
      )}
    </div>
  );
}

// ---- the rail ----------------------------------------------------------------------------------

function decidedWord(record: AcceptanceRecordOut): string | null {
  return record.decision == null ? null : COPY.dock.decided[record.decision.option];
}

function phaseOf(
  s: AcceptanceSectionOut,
  record: AcceptanceRecordOut,
  names: ReadonlyMap<string, string>,
): Phase {
  const screening = record.status === "pre_screening";
  if (s.code === CONCLUSION) {
    const word = decidedWord(record);
    if (word !== null && record.decision != null) {
      const who = names.get(record.decision.decided_by) ?? "";
      return {
        id: s.code,
        title: s.title,
        disc: "done",
        live: { text: COPY.rail.conclusion(word, initials(who)) },
      };
    }
    return {
      id: s.code,
      title: s.title,
      disc: screening ? "run" : "todo",
      live: { text: answerText(s, "summary") ?? COPY.rail.awaiting },
    };
  }
  const summary = answerText(s, "summary");
  const disc = screening && s.answer_state === "pending" ? "run" : DISC[s.answer_state];
  return {
    id: s.code,
    title: s.title,
    disc,
    live: {
      text: summary ?? COPY.rail.notStarted,
      ...(s.answer_state === "flag" ? { tone: "amber" as const } : {}),
    },
  };
}

function cardState(record: AcceptanceRecordOut): string {
  const word = decidedWord(record);
  if (word !== null) return word;
  return status("acceptance_record", record.status as RegistryCode<"acceptance_record">, {
    context: "rail_card",
  }).label;
}

function Rail({
  record,
  names,
  selected,
  onOpen,
}: {
  record: AcceptanceRecordOut;
  names: ReadonlyMap<string, string>;
  selected: string | undefined;
  onOpen: (code: string) => void;
}): JSX.Element {
  const sections = record.sections ?? [];
  return (
    <RecordRail
      title={COPY.rail.title}
      card={{
        icon: "shield-check",
        title: record.kind === "continuance" ? COPY.rail.continuance : COPY.rail.acceptance,
        sub: COPY.rail.sub(names.get(record.prepared_by) ?? "", sections.length),
        state: cardState(record),
      }}
      sections={[
        {
          id: "sections",
          title: COPY.rail.band,
          collapsible: false,
          phases: sections.map((s) => phaseOf(s, record, names)),
        },
      ]}
      {...(selected === undefined ? {} : { selected })}
      onOpen={(item) => {
        onOpen(item.id);
      }}
      onMenu={(item, phase) => {
        if (item === "Open") onOpen(phase.id);
      }}
    />
  );
}

// ---- the canvas --------------------------------------------------------------------------------

function RiskCard({
  record,
  engagement,
  names,
}: {
  record: AcceptanceRecordOut;
  engagement: EngagementRecordOut;
  names: ReadonlyMap<string, string>;
}): JSX.Element {
  const sections = (record.sections ?? []).filter((s) => s.code !== CONCLUSION);
  const clear = sections.filter(isClear);
  const byCheck = clear.filter((s) => s.answer_state === "manual_check_done").length;
  const open = openChecks(record).length;
  const flags = record.flags ?? [];
  const rating = record.risk_rating == null ? null : COPY.risk.rating[record.risk_rating];
  const word = decidedWord(record);
  const review = record.risk_partner_review;
  const parts = [
    COPY.risk.clear(clear.length, byCheck),
    COPY.risk.flags(flags.length),
    ...(open > 0 ? [COPY.risk.open(open)] : []),
    word !== null && record.decision != null
      ? COPY.risk.concluded(word, names.get(record.decision.decided_by) ?? "")
      : COPY.risk.awaiting,
    ...(review != null
      ? [
          review.completed_at == null
            ? COPY.risk.requested(names.get(review.partner_id) ?? "")
            : COPY.risk.completed(names.get(review.partner_id) ?? ""),
        ]
      : rating === null
        ? []
        : [
            record.risk_rating === "high"
              ? COPY.risk.required(rating)
              : COPY.risk.notRequired(rating),
          ]),
  ];
  return (
    <Card label={COPY.risk.label} className="flex items-start gap-[18px] px-[14px] py-[12px]">
      <div className="flex flex-none flex-col gap-[4px]">
        <span className="text-outline-hd text-ink-3 uppercase">{COPY.risk.label}</span>
        <span className="flex items-center gap-[8px]">
          <span data-risk="" className="text-title">
            {rating ?? "—"}
          </span>
          {flags.length > 0 && <Pill variant="amber">{COPY.risk.flags(flags.length)}</Pill>}
        </span>
      </div>
      <div className="flex min-w-0 flex-col gap-[4px]">
        <p data-risk-summary="" className="text-dense leading-[1.5] text-ink-2">
          {parts.join(" · ")}
        </p>
        {record.kind === "continuance" && (
          <Planned>
            <span>
              <Button
                variant="link"
                size="sm"
                disabled
                title={COPY.risk.nasHint(engagement.client_name)}
              >
                {COPY.risk.nas}
              </Button>
            </span>
          </Planned>
        )}
      </div>
    </Card>
  );
}

function FlagCard({ flag, footer }: { flag: AcceptanceFlagOut; footer: ReactNode }): JSX.Element {
  return (
    <Card label={flag.title}>
      <div data-flag={flag.id} className="flex h-[40px] items-center gap-[10px] px-[14px]">
        <Icon name="flag" size={12} className="flex-none text-amber" />
        <h3 className="min-w-0 flex-1 truncate text-section font-medium">{flag.title}</h3>
        <Pill variant="amber">{COPY.severity[flag.severity]}</Pill>
      </div>
      <p className="px-[14px] pb-[12px] text-dense leading-[1.55] whitespace-pre-line text-ink-2">
        {flag.body}
      </p>
      {(flag.sources ?? []).map((s) => (
        <div key={s.id} data-source={s.kind} title={COPY.flag.sourceHint} className={ROW}>
          <Icon name="file-text" size={13} className="flex-none text-ink-3" />
          <span className="text-body font-medium">{COPY.flag.source[s.kind]}</span>
        </div>
      ))}
      {footer !== null && <div className={cn(ROW, "text-dense")}>{footer}</div>}
    </Card>
  );
}

function ClearSections({ sections }: { sections: readonly AcceptanceSectionOut[] }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className="flex h-[44px] w-full items-center gap-[10px] px-[14px] text-left"
      >
        <Icon name="check" size={13} className="flex-none text-green" />
        <span className="flex-1 text-section font-medium">{COPY.clear(sections.length)}</span>
        <Icon
          name="chevron-down"
          size={12}
          className={cn("text-ink-3 transition-transform", !open && "-rotate-90")}
        />
      </button>
      {open && (
        <ul className="flex flex-col">
          {sections.map((s) => (
            <li
              key={s.code}
              id={`cli07-${s.code}`}
              className="px-[14px] py-[8px] text-dense leading-[1.5] text-ink-2 hairline-t"
            >
              {s.title}: {answerText(s, "detail") ?? answerText(s, "summary") ?? ""}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Running({ record }: { record: AcceptanceRecordOut }): JSX.Element {
  const sections = record.sections ?? [];
  const done = sections.filter((s) => s.answer_state !== "pending").length;
  return (
    <Card className="flex flex-col gap-[10px] px-[14px] py-[12px]">
      <p data-running="" className="flex items-center gap-[8px] text-section font-medium">
        <Pill variant="neutral" spin>
          {status("acceptance_record", "pre_screening").label}
        </Pill>
        {COPY.canvas.running(done, sections.length)}
      </p>
      {[62, 38, 74].map((w) => (
        <span
          key={w}
          aria-hidden="true"
          className="h-[9px] rounded-pill bg-nested"
          style={{ width: `${String(w)}%` }}
        />
      ))}
    </Card>
  );
}

// ---- dialogs -----------------------------------------------------------------------------------

function TextArea({
  label,
  value,
  onChange,
  disabled = false,
  invalid,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  invalid?: string | undefined;
  rows?: number;
}): JSX.Element {
  const id = useId();
  return (
    <div className="flex flex-col gap-[6px]">
      <label htmlFor={id} className="text-body text-ink-2">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        rows={rows}
        disabled={disabled}
        {...(invalid === undefined ? {} : { "aria-invalid": true })}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        className="w-full resize-none rounded-nested bg-nested p-[10px] text-body text-ink inset-shadow-hair disabled:text-ink-3"
      />
      {invalid !== undefined && (
        <span role="alert" className="text-meta text-red-ink">
          {invalid}
        </span>
      )}
    </div>
  );
}

function sayRefusal(error: unknown): void {
  const code = refusalOf(error);
  const text =
    code === "stale_version"
      ? COPY.errors.stale
      : code === "decision_locked"
        ? COPY.errors.locked
        : code === "acceptance_not_ready"
          ? COPY.errors.notReady
          : code === "review_required"
            ? COPY.errors.review
            : code === "invalid"
              ? COPY.errors.invalid
              : COPY.errors.failed;
  toast.show({ kind: "error", text });
}

// ---- the screen --------------------------------------------------------------------------------

interface DraftCondition {
  key: number;
  text: string;
}

export function CLI07({
  clientId,
  engagementId,
  onNavigate,
  toolbar,
  frame = false,
  note,
}: CLI07Props): JSX.Element {
  const now = useNow();
  const session = useSession();
  const tz = session.tz ?? DEFAULT_TZ;
  const me = session.user?.id;
  const acceptance = useAcceptance(engagementId);
  const engagementQuery = useEngagementRecord(engagementId);
  const roster = useEngagementTeam(engagementId);
  const writes = useAcceptanceWrites(engagementId);
  // The risk partner is rarely on the team: their name comes from the people the picker offers.
  const reviewers = useReviewCandidates(
    engagementId,
    mayOn(acceptance.data, "acceptance.request_review"),
  );

  const [selected, setSelected] = useState<string | undefined>(undefined);
  const [option, setOption] = useState<AcceptanceOption | null>(null);
  const [rationale, setRationale] = useState(note ?? "");
  const [conditions, setConditions] = useState<DraftCondition[]>([]);
  const keys = useRef(0);
  const [errors, setErrors] = useState<
    Partial<Record<"option" | "reason" | "conditions", string>>
  >({});
  const [stepUp, setStepUp] = useState(false);
  const [dialog, setDialog] = useState<
    null | "request" | "flag" | "review" | { complete: AcceptanceSectionOut }
  >(null);

  const record = acceptance.data;
  const engagement = engagementQuery.data;
  const team = roster.data ?? [];
  const names = new Map(
    [...(reviewers.data ?? []), ...team].map((m) => [m.user_id, m.display_name]),
  );
  const partner = team.find((m) => m.role === EP_ROLE)?.display_name ?? "";
  const client = engagement?.client_name ?? "";
  const back = (): void => {
    onNavigate?.({ screen: "CLI-02", clientId });
  };
  const when = (at: string): string => `${date(at, { now, tz })}, ${time(at, { tz })}`;

  let state: ViewState;
  if (acceptance.isError) {
    state = notFound(acceptance.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void acceptance.refetch() };
  } else if (record === undefined || engagement === undefined) {
    state = engagementQuery.isError
      ? { kind: "error", retry: () => void engagementQuery.refetch() }
      : { kind: "loading" };
  } else state = { kind: "ready" };

  const bar = (
    <Bar engagement={engagement} record={record} names={names} now={now} tz={tz} onBack={back} />
  );

  if (record === undefined || engagement === undefined) {
    return (
      <div data-screen="CLI-07" className="flex min-h-0 flex-1 flex-col">
        <RecordCockpit
          {...(toolbar === undefined ? {} : { toolbar })}
          frame={frame}
          {...(frame ? { height: 860 } : {})}
          header={bar}
          rail={
            <section aria-label={COPY.rail.title} className="pane flex min-h-0 flex-1 flex-col">
              <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
                <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail.title}</h2>
              </div>
            </section>
          }
          canvas={{ title: COPY.canvas.title, well: true, state }}
        />
      </div>
    );
  }

  const locked = isLocked(record);
  const screening = record.status === "pre_screening";
  const isPartner = mayOn(record, "acceptance.decide");
  const canPrepare = mayOn(record, "acceptance.prepare");
  const canDecide = isPartner && record.status === "awaiting_partner";
  const open = openChecks(record);
  const pendingSections = unanswered(record);
  const continuance = record.kind === "continuance";
  const period = engagement.period_label ?? "";
  const options = continuance ? COPY.dock.continuance(period) : COPY.dock.accept;
  const chosen = locked ? (record.decision?.option ?? null) : option;
  const decidedAt = record.decision?.decided_at;

  const choose = (value: string): void => {
    setOption(value as AcceptanceOption);
    setErrors({});
  };
  const makeCondition = (flag: AcceptanceFlagOut): void => {
    setOption("accept_with_conditions");
    keys.current += 1;
    const key = keys.current;
    setConditions((was) => [...was, { key, text: flag.title }]);
    setErrors({});
  };

  const decide = (): void => {
    const filled = conditions.filter((c) => c.text.trim() !== "");
    const found: typeof errors = {};
    if (option === null) found.option = COPY.errors.option;
    if (rationale.trim() === "") found.reason = COPY.errors.rationaleRequired;
    if (option === "accept_with_conditions" && filled.length === 0) {
      found.conditions = COPY.errors.conditions;
    }
    setErrors(found);
    if (option === null || Object.keys(found).length > 0) return;
    writes
      .decide(
        option,
        rationale.trim(),
        option === "accept_with_conditions"
          ? filled.map((c) => ({ text: c.text.trim(), assigneeUserId: record.prepared_by }))
          : [],
        record.version,
      )
      .then(
        () => {
          toast.show({ kind: "success", text: COPY.toast.decided });
          setOption(null);
          setRationale("");
          setConditions([]);
        },
        (error: unknown) => {
          if (needsStepUp(error)) {
            setStepUp(true);
            return;
          }
          if (refusalOf(error) === "rationale_required") {
            setErrors(
              fieldOf(error) === "conditions"
                ? { conditions: COPY.errors.conditions }
                : { reason: COPY.errors.rationaleRequired },
            );
            return;
          }
          sayRefusal(error);
        },
      );
  };

  // ---- canvas ----
  const flagFooter = (flag: AcceptanceFlagOut): ReactNode => {
    if (locked || screening) return null;
    if (isPartner) {
      return (
        <button
          type="button"
          className="font-medium text-ink"
          onClick={() => {
            makeCondition(flag);
          }}
        >
          {COPY.flag.makeCondition} <span className="text-ink-3">{COPY.flag.arrow}</span>
        </button>
      );
    }
    return <span className="text-ink-3">{COPY.flag.partnerCan(partner)}</span>;
  };

  const actions: ReactNode[] = [];
  if (!locked && !screening) {
    if (canPrepare && record.status === "draft") {
      actions.push(
        <Button
          key="check"
          variant="secondary"
          size="sm"
          opensDialog
          onClick={() => {
            setDialog("request");
          }}
        >
          {COPY.canvas.requestCheck}
        </Button>,
      );
    }
    if (canPrepare) {
      actions.push(
        <Button
          key="flag"
          variant="secondary"
          size="sm"
          opensDialog
          onClick={() => {
            setDialog("flag");
          }}
        >
          {COPY.canvas.addFlag}
        </Button>,
      );
    }
    if (mayOn(record, "acceptance.request_review") && record.risk_partner_review == null) {
      actions.push(
        <Button
          key="review"
          variant="secondary"
          size="sm"
          opensDialog
          onClick={() => {
            setDialog("review");
          }}
        >
          {COPY.canvas.review}
        </Button>,
      );
    }
    if (
      mayOn(record, "acceptance.complete_review") &&
      record.risk_partner_review?.completed_at == null
    ) {
      actions.push(
        <Button
          key="complete-review"
          variant="secondary"
          size="sm"
          onClick={() => {
            writes.completeReview().catch((error: unknown) => {
              if (needsStepUp(error)) setStepUp(true);
              else sayRefusal(error);
            });
          }}
        >
          {COPY.canvas.completeReview}
        </Button>,
      );
    }
  }

  const clear = (record.sections ?? []).filter((s) => s.code !== CONCLUSION && isClear(s));
  const canvasBody = screening ? (
    <div className="flex flex-col gap-[10px] p-[10px]">
      <Running record={record} />
    </div>
  ) : (
    <div className="flex flex-col gap-[10px] p-[10px]">
      {!locked &&
        open.map((s) => {
          const check = s.manual_check;
          const mine = check != null && check.requested_of === me;
          return (
            <Card key={s.code} id={`cli07-${s.code}`} label={COPY.check.open(s.title)}>
              <div data-check={s.code} className="flex items-start gap-[10px] px-[14px] py-[12px]">
                <StatusDisc state="half" className="mt-[2px]" />
                <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <h3 className="text-section font-medium">{COPY.check.open(s.title)}</h3>
                  <p className="text-dense leading-[1.5] text-ink-2">
                    {answerText(s, "detail") ?? answerText(s, "summary") ?? ""}
                  </p>
                </div>
                {mine ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    opensDialog
                    onClick={() => {
                      setDialog({ complete: s });
                    }}
                  >
                    {COPY.check.complete}
                  </Button>
                ) : (
                  check != null && (
                    <span className="flex-none text-body text-ink-3">
                      {COPY.check.askedOf(
                        names.get(check.requested_of) ?? "",
                        date(check.requested_at, { now, tz }),
                      )}
                    </span>
                  )
                )}
              </div>
            </Card>
          );
        })}
      <RiskCard record={record} engagement={engagement} names={names} />
      {(record.flags ?? []).map((flag) => (
        <FlagCard key={flag.id} flag={flag} footer={flagFooter(flag)} />
      ))}
      {clear.length > 0 && <ClearSections sections={clear} />}
    </div>
  );

  // ---- dock ----
  const banner = locked
    ? undefined
    : record.status === "draft" || screening
      ? pendingSections.length > 0 || screening
        ? COPY.dock.notReadyQuestionnaire
        : open.length > 0
          ? COPY.dock.notReady(open.length)
          : undefined
      : undefined;
  const decision = record.decision;
  const decided =
    locked && decision != null && decidedAt !== undefined
      ? {
          pill: COPY.dock.decided[decision.option],
          variant: decision.option === "decline" ? ("neutral" as const) : ("green-tint" as const),
          line: COPY.dock.decidedLine(names.get(decision.decided_by) ?? "", when(decidedAt)),
        }
      : undefined;

  const rationaleLabel =
    chosen === "decline"
      ? COPY.dock.reasons
      : continuance && record.status === "draft"
        ? COPY.dock.continuanceNote
        : COPY.dock.rationaleLabel;

  const conditionRows = locked ? (
    (record.conditions ?? []).length > 0 && (
      <div data-conditions="" className="flex flex-col">
        <div className="flex h-[31px] items-center bg-band-hd px-[12px] text-body font-medium hairline-b">
          <span className="flex-1">{COPY.dock.conditions}</span>
          <span className="text-meta font-normal text-ink-3">
            {COPY.dock.conditionsDone(
              (record.conditions ?? []).filter((c) => c.completed_at != null).length,
              (record.conditions ?? []).length,
            )}
          </span>
        </div>
        {(record.conditions ?? []).map((c) => {
          const done = c.completed_at != null;
          return (
            <div
              key={c.id}
              data-condition={c.id}
              className="flex items-start gap-[10px] px-[12px] py-[8px] hairline-b"
            >
              <Checkbox
                checked={done}
                label={COPY.dock.complete(c.text)}
                disabled={done || !canPrepare}
                className="mt-[2px]"
                onChange={() => {
                  writes.completeCondition(c.id).catch(sayRefusal);
                }}
              />
              <span className="flex min-w-0 flex-col gap-[2px]">
                <span className="text-body text-ink">{c.text}</span>
                <span className="text-meta text-ink-3">
                  {COPY.dock.owner(
                    names.get(c.assignee_user_id) ?? "",
                    done ? COPY.dock.done : COPY.dock.open,
                  )}
                </span>
              </span>
            </div>
          );
        })}
      </div>
    )
  ) : chosen === "accept_with_conditions" && canDecide ? (
    <div data-conditions="" className="flex flex-col gap-[6px] px-[12px] py-[10px] hairline-b">
      <span className="text-body font-medium">{COPY.dock.conditions}</span>
      {conditions.map((c, i) => (
        <div key={c.key} className="flex items-center gap-[6px]">
          <input
            className={TEXT_INPUT}
            aria-label={COPY.dock.condition(i + 1)}
            value={c.text}
            onChange={(event) => {
              const text = event.target.value;
              setConditions((was) => was.map((x) => (x.key === c.key ? { ...x, text } : x)));
            }}
          />
          <Button
            variant="ghost"
            size="xs"
            aria-label={COPY.dock.removeCondition(i + 1)}
            onClick={() => {
              setConditions((was) => was.filter((x) => x.key !== c.key));
            }}
          >
            ×
          </Button>
        </div>
      ))}
      <span>
        <Button
          variant="secondary"
          size="xs"
          onClick={() => {
            keys.current += 1;
            const key = keys.current;
            setConditions((was) => [...was, { key, text: "" }]);
          }}
        >
          {COPY.dock.addCondition}
        </Button>
      </span>
      {errors.conditions !== undefined && (
        <span role="alert" className="text-meta text-red-ink">
          {errors.conditions}
        </span>
      )}
    </div>
  ) : null;

  // The recorded rationale is the partner's own words (a human-only decision: `actor_kind`
  // 'human' at the database, SPEC-332 AC-6), never model text.
  const recordedWords = decision?.rationale ?? "";
  const recordedLabel =
    decision?.option === "decline" ? COPY.dock.reasons : COPY.dock.rationaleLabel;
  const rationaleField = locked ? (
    decision != null && (
      <div className="flex flex-col gap-[6px] px-[12px] py-[10px]">
        <span className="text-body text-ink-2">{recordedLabel}</span>
        <p
          data-rationale=""
          className="rounded-nested bg-nested p-[10px] text-body leading-[1.5] text-ink"
        >
          {recordedWords}
        </p>
      </div>
    )
  ) : (
    <div className="px-[12px] py-[10px]">
      <TextArea
        label={rationaleLabel}
        value={rationale}
        disabled={!isPartner}
        invalid={errors.reason}
        onChange={(value) => {
          setRationale(value);
          if (errors.reason !== undefined) {
            setErrors(errors.option === undefined ? {} : { option: errors.option });
          }
        }}
      />
    </div>
  );

  let action: ReactNode;
  if (locked && decision != null) {
    action =
      decision.option === "decline" ? (
        <Button
          variant="secondary"
          size="xl"
          className="w-full"
          title={COPY.backHint(client)}
          onClick={back}
        >
          {COPY.dock.openClient(client)}
        </Button>
      ) : (
        <Planned>
          <Button
            variant="primary"
            size="xl"
            className="w-full"
            disabled
            title={COPY.dock.letterHint(client)}
          >
            {COPY.dock.letter}
          </Button>
        </Planned>
      );
  } else if (record.status === "draft" && canPrepare) {
    action = (
      <Button
        variant="primary"
        size="xl"
        className="w-full"
        disabled={open.length > 0 || pendingSections.length > 0 || writes.pending}
        onClick={() => {
          writes.send(record.version).catch(sayRefusal);
        }}
      >
        {COPY.dock.send}
      </Button>
    );
  } else if (canDecide) {
    action = (
      <Button
        variant="primary"
        size="xl"
        icon="check"
        className="w-full"
        loading={writes.pending}
        onClick={decide}
      >
        {COPY.dock.decide}
      </Button>
    );
  } else {
    action = (
      <Button
        variant="primary"
        size="xl"
        className="w-full"
        disabled
        title={COPY.dock.reserved(partner)}
      >
        {isPartner ? COPY.dock.decide : COPY.dock.partnerOnly}
      </Button>
    );
  }

  const footNote =
    locked && decidedAt !== undefined
      ? decision?.option === "decline"
        ? COPY.dock.recordedDecline(when(decidedAt))
        : COPY.dock.recordedAccept(when(decidedAt))
      : COPY.dock.reserved(partner);

  const question = continuance
    ? COPY.dock.continueQuestion(client, period)
    : COPY.dock.question(client);

  return (
    <div data-screen="CLI-07" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={bar}
        rail={
          <Rail
            record={record}
            names={names}
            selected={selected}
            onOpen={(code) => {
              setSelected(code);
              const el = document.getElementById(`cli07-${code}`);
              // jsdom has no scrollIntoView.
              if (el !== null && "scrollIntoView" in el) el.scrollIntoView({ block: "nearest" });
            }}
          />
        }
        canvas={{
          title: COPY.canvas.title,
          well: true,
          state,
          ...(actions.length === 0
            ? {}
            : { actions: <span className="flex items-center gap-[8px]">{actions}</span> }),
          children: canvasBody,
        }}
        dock={{
          view: "Agent",
          views: ["Agent"],
          title: COPY.dock.title,
          composer: <DecisionDockFooter action={action} note={footNote} />,
          children: (
            <DecisionDock
              question={question}
              options={options}
              chosen={chosen}
              onChoose={choose}
              disabled={!canDecide}
              {...(banner === undefined ? {} : { banner })}
              {...(decided === undefined ? {} : { decided })}
            >
              {errors.option !== undefined && (
                <span role="alert" className="px-[12px] pt-[8px] text-meta text-red-ink">
                  {errors.option}
                </span>
              )}
              {conditionRows}
              {rationaleField}
            </DecisionDock>
          ),
        }}
      />
      <StepUp open={stepUp} onOpenChange={setStepUp} />
      {dialog === "request" && (
        <RequestCheckDialog
          record={record}
          team={team.filter((m) => PREPARERS.has(m.role))}
          onClose={() => {
            setDialog(null);
          }}
          onRequest={(code, userId) => writes.requestCheck(code, userId)}
        />
      )}
      {dialog === "flag" && (
        <AddFlagDialog
          onClose={() => {
            setDialog(null);
          }}
          onAdd={(title, severity, body) => writes.addFlag(title, severity, body)}
        />
      )}
      {dialog === "review" && (
        <ReviewDialog
          engagementId={engagementId}
          onClose={() => {
            setDialog(null);
          }}
          onRequest={(partnerId) => writes.requestReview(partnerId)}
        />
      )}
      {dialog !== null && typeof dialog === "object" && (
        <CompleteCheckDialog
          section={dialog.complete}
          onClose={() => {
            setDialog(null);
          }}
          onComplete={(text) => writes.completeCheck(dialog.complete.code, text)}
        />
      )}
    </div>
  );
}

function RequestCheckDialog({
  record,
  team,
  onClose,
  onRequest,
}: {
  record: AcceptanceRecordOut;
  team: readonly { user_id: string; display_name: string }[];
  onClose: () => void;
  onRequest: (code: string, userId: string) => Promise<unknown>;
}): JSX.Element {
  const sections = (record.sections ?? []).filter(
    (s) => s.code !== CONCLUSION && s.answer_state !== "manual_check_open",
  );
  const [code, setCode] = useState<string | undefined>(undefined);
  const [person, setPerson] = useState<string | undefined>(undefined);
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.check.requestTitle}
      action={
        <Button
          disabled={code === undefined || person === undefined}
          onClick={() => {
            if (code === undefined || person === undefined) return;
            onRequest(code, person).then(onClose, sayRefusal);
          }}
        >
          {COPY.check.request}
        </Button>
      }
    >
      <div className="flex flex-col gap-[10px]">
        <Picker
          label={COPY.check.section}
          placeholder={COPY.check.section}
          options={sections.map((s) => ({ value: s.code, label: s.title }))}
          {...(code === undefined ? {} : { value: code })}
          onChange={setCode}
        />
        <Picker
          label={COPY.check.person}
          placeholder={COPY.check.person}
          options={team.map((m) => ({ value: m.user_id, label: m.display_name }))}
          {...(person === undefined ? {} : { value: person })}
          onChange={setPerson}
        />
      </div>
    </Dialog>
  );
}

function CompleteCheckDialog({
  section,
  onClose,
  onComplete,
}: {
  section: AcceptanceSectionOut;
  onClose: () => void;
  onComplete: (note: string) => Promise<unknown>;
}): JSX.Element {
  const [text, setText] = useState("");
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.check.completeTitle(section.title)}
      action={
        <Button
          onClick={() => {
            onComplete(text).then(onClose, sayRefusal);
          }}
        >
          {COPY.check.markDone}
        </Button>
      }
    >
      <TextArea label={COPY.check.note} value={text} onChange={setText} />
    </Dialog>
  );
}

const SEVERITIES: readonly FlagSeverity[] = ["low", "medium", "high"];

function AddFlagDialog({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (title: string, severity: FlagSeverity, body: string) => Promise<unknown>;
}): JSX.Element {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<FlagSeverity>("medium");
  const [body, setBody] = useState("");
  const ready = title.trim() !== "" && body.trim() !== "";
  return (
    <Dialog
      open
      dirty={title !== "" || body !== ""}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.addFlag.title}
      action={
        <Button
          disabled={!ready}
          onClick={() => {
            onAdd(title.trim(), severity, body.trim()).then(onClose, sayRefusal);
          }}
        >
          {COPY.addFlag.add}
        </Button>
      }
    >
      <div className="flex flex-col gap-[10px]">
        <label className="flex flex-col gap-[6px] text-body text-ink-2">
          {COPY.addFlag.flagTitle}
          <input
            className={TEXT_INPUT}
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        </label>
        <Picker
          label={COPY.addFlag.severity}
          options={SEVERITIES.map((s) => ({ value: s, label: COPY.severity[s] }))}
          value={severity}
          onChange={(v) => {
            setSeverity(v as FlagSeverity);
          }}
        />
        <TextArea label={COPY.addFlag.body} value={body} onChange={setBody} rows={4} />
      </div>
    </Dialog>
  );
}

function ReviewDialog({
  engagementId,
  onClose,
  onRequest,
}: {
  engagementId: string;
  onClose: () => void;
  onRequest: (partnerId: string) => Promise<unknown>;
}): JSX.Element {
  const candidates = useReviewCandidates(engagementId, true);
  const [partner, setPartner] = useState<string | undefined>(undefined);
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.review.title}
      action={
        <Button
          disabled={partner === undefined}
          onClick={() => {
            if (partner === undefined) return;
            onRequest(partner).then(onClose, sayRefusal);
          }}
        >
          {COPY.review.request}
        </Button>
      }
    >
      <Picker
        label={COPY.review.partner}
        placeholder={COPY.review.partner}
        options={(candidates.data ?? []).map((c) => ({ value: c.user_id, label: c.display_name }))}
        {...(partner === undefined ? {} : { value: partner })}
        onChange={setPartner}
      />
    </Dialog>
  );
}

/** The step-up a stale MFA asks for (ADR-030), in the shell's ConfirmItsYou words. */
function StepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.stepUp.title}
      description={COPY.stepUp.body}
    >
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          {COPY.cancel}
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          {COPY.stepUp.signIn}
        </Button>
      </div>
    </Dialog>
  );
}

/** The screen as the route and the gallery mount it. */
export function AcceptancePage(props: CLI07Props): JSX.Element {
  return <CLI07 {...props} />;
}
