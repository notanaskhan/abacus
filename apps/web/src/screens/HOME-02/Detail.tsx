import type {
  AgentProposalOut,
  CitationV2Out,
  EligibilityCheckOut,
  HumanGateOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import {
  humanGateCountsQueryKey,
  humanGateListQueryKey,
  listCitationsOptions,
} from "@abacus/api-client/query";
import {
  type Actor,
  AgentMonogram,
  AgentText,
  Button,
  HumanAction,
  Icon,
  Pill,
  RadioGroup,
  Tag,
  date as formatDate,
  time,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useId } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import type { OverlayRef } from "../../app-core/overlays";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { useEngagementTeam } from "../../domain/engagements";
import {
  levelOf,
  useDecisionCard,
  useDecisionWrites,
  useGate,
  useProposal,
  useSignOffEligibility,
  useSignOffLadder,
} from "../../domain/review";
import { ov } from "../../routes/to";
import { COPY } from "./copy";

// HOME-02's detail pane per gate class (I-01-T17; docs/screens/HOME-02.md; the handoff's a–d and
// g frames), on the owners' C3 reads (P-04): the class decides the body, the owner's projection
// fills it, and every verb is a HumanAction for the signed-in person.
//
//   decision          the SHL-11 card inline (a): title band, Reserved to · Work item · Due ·
//                     Proposed by, "Why This Was Surfaced", the options with the agent's
//                     recommendation as a tag (never a choice made), the evidence sources, the
//                     rationale; ✓ Decide waits for an option and a rationale (DV-1, AC7.1) and is
//                     the reserved person's only (INV-1); Request more analysis… opens SHL-11;
//                     decided (b): the decided pill, the chosen option and the owner's note
//   sign_off_request  Workpaper · Level · Prepared · Reviewed; blocked (c): the banner from the
//                     failing check, Sign off… disabled and Open proposal (SHL-10); ready (d):
//                     Sign off… opens SHL-12 at the gate's level
//   proposal          the bento grammar (g): Work item · Proposed by · Level, the Reasoning card,
//                     the Source rows; Approve adjustments and Reject… open SHL-10
//   final_approval    SHL-12's final approval for a return; send → SIG-01 (planned)
//   anything else     the generic detail: the resolver's facts and nothing hidden (AC7.8)
//
// No control is drawn on an agent-owned element: the agent's text renders through AgentText and
// carries no verb. Reassign… and Snooze until… are T19's (drawn where the gate allows them). The
// body and the footer are separate components over the same queries (React Query shares them);
// the decision draft is the screen's, so both halves read one choice.

const SHL10 = (ref: string): OverlayRef => ({ key: "approve", args: [ref] });

/** The reserved person's choice while they decide, held by the screen so the body (radios,
 * rationale) and the pinned footer (Decide) read the same draft. */
export interface DecisionDraft {
  option?: string;
  /** The rationale as typed (the person's words, never model text). */
  words: string;
}

export interface DetailProps {
  gate: HumanGateOut;
  /** The gate's host as an href (an approval or send without an overlay). */
  href: string | undefined;
  draft: DecisionDraft;
  onDraft: (draft: DecisionDraft) => void;
}

type GateClass = "decision" | "sign_off" | "proposal" | "approval";

/** The gate's class (DF-25 kinds): a decision card, a sign-off, an agent output, or the rest. */
export function classOf(gate: HumanGateOut): GateClass {
  if (
    gate.kind === "decision" &&
    (gate.overlay === "decision_card" || gate.subject.type === "decision_card")
  ) {
    return "decision";
  }
  if (gate.kind === "sign_off_request") return "sign_off";
  if (gate.kind === "proposal") return "proposal";
  return "approval";
}

/** The person whose act this is: the session's, never the agent (HumanAction draws nothing else). */
function useActor(): Actor {
  const session = useSession();
  return session.user === null
    ? { kind: "system" }
    : { kind: "human", name: session.user.displayName };
}

/** Names from the engagement's team (C1); an id the roster does not hold reads as nothing. */
function useNames(engagementId: string | null): (userId: string | null | undefined) => string {
  const team = useEngagementTeam(engagementId ?? "", engagementId !== null);
  const roster: readonly TeamRosterMemberOut[] = team.data ?? [];
  return (userId) =>
    userId == null ? "" : (roster.find((m) => m.user_id === userId)?.display_name ?? "");
}

// ---- Shared pieces --------------------------------------------------------------------------

function TitleBand({ title, pill }: { title: string; pill?: ReactNode }): JSX.Element {
  return (
    <div className="flex items-start gap-[10px] bg-shell px-[14px] py-[12px] hairline-b">
      <h3 className="flex-1 text-record leading-[1.3] font-medium">{title}</h3>
      {pill}
    </div>
  );
}

function Kv({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[44px] items-center justify-between gap-[12px] px-[14px] py-[8px] hairline-b">
      <dt className="flex-none text-body text-ink-2">{label}</dt>
      <dd className="flex min-w-0 items-center gap-[6px] text-right text-body">{children}</dd>
    </div>
  );
}

function Band({ children, icon }: { children: ReactNode; icon?: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[31px] items-center gap-[8px] bg-band-hd px-[14px] text-section font-medium hairline-b">
      {icon}
      {children}
    </div>
  );
}

/** "Proposed by": the agent's monogram and the person who ran it (attribution, not a control). */
function ProposedBy({ by, on }: { by: string; on: string }): JSX.Element {
  return (
    <span className="flex items-center gap-[6px]" data-actor="agent">
      <AgentMonogram size={16} label={COPY.detailPane.agent} />
      {COPY.detailPane.run(by, on)}
    </span>
  );
}

function SourceRow({ title, n }: { title: string; n: number }): JSX.Element {
  return (
    <li
      data-home02="source"
      className="flex min-h-[46px] items-center gap-[10px] px-[14px] py-[8px] hairline-b"
    >
      <Icon name="file" size={15} className="flex-none text-ink-3" />
      <span className="min-w-0 flex-1 truncate">
        <span className="text-nav font-medium">{title}</span>
        <span className="text-meta text-ink-3"> · {COPY.detailPane.citations(n)}</span>
      </span>
    </li>
  );
}

function Loading({ failed }: { failed: boolean }): JSX.Element {
  return (
    <p aria-busy={failed ? undefined : true} className="px-[14px] py-[12px] text-meta text-ink-3">
      {failed ? COPY.detailPane.missing : COPY.detailPane.loading}
    </p>
  );
}

/** The footer's stacked full-width buttons over an optional ink-3 line (HOME-02 acceptance). */
function Footer({ children, line }: { children: ReactNode; line?: string }): JSX.Element {
  return (
    <div data-home02="footer" className="flex w-full flex-col gap-[8px]">
      {children}
      {line !== undefined && <p className="text-center text-meta text-ink-3">{line}</p>}
    </div>
  );
}

const roleOf = (role: string): { line: string; value: string } =>
  COPY.roles[role] ?? { line: role, value: role };

// ---- Decision -------------------------------------------------------------------------------

/** The card's citations grouped by source document, in first-cited order. */
function groupSources(citations: readonly CitationV2Out[]): { title: string; n: number }[] {
  const groups = new Map<string, { title: string; n: number }>();
  for (const c of citations) {
    const key = c.source.evidence_version_id ?? c.source.id;
    const found = groups.get(key);
    if (found === undefined) groups.set(key, { title: c.title, n: 1 });
    else found.n += 1;
  }
  return [...groups.values()];
}

function DecisionBody({ gate, draft, onDraft }: DetailProps): JSX.Element {
  const ids = useId();
  const now = useNow();
  const name = useNames(gate.engagement_id);
  const cardId = gate.subject.id;
  const query = useDecisionCard(cardId);
  const citations = useQuery(
    listCitationsOptions({ query: { anchor_type: "decision_card", anchor_id: cardId } }),
  );
  const card = query.data;
  if (card === undefined) return <Loading failed={query.isError} />;

  const head = card.card;
  const decided = card.decision;
  const reservedHere = head.allowed_actions.includes("decision.decide");
  const open = reservedHere && decided === null;
  const role = roleOf(head.reserved_role);
  const proposed = card.history.find((h) => h.event === "proposed");
  const ranBy = name(gate.proposed_by?.initiator_user_id);
  const proposedOn = gate.proposed_by?.at ?? proposed?.at;
  const why = card.recommendation?.reasons.join("\n\n") ?? "";
  const recommended = card.recommendation?.option_key ?? null;
  const shown =
    decided === null ? card.options : card.options.filter((o) => o.key === decided.option_key);
  const chosen = decided?.option_key ?? draft.option;
  const sources = groupSources(citations.data?.items ?? []);

  return (
    <div data-home02-detail="decision" data-status={head.status} className="flex flex-col">
      <TitleBand
        title={card.question}
        {...(decided === null
          ? {}
          : {
              pill: (
                <Pill variant="green-tint" size="sm">
                  {COPY.detailPane.decided(decided.decided_by_name, time(decided.decided_at))}
                </Pill>
              ),
            })}
      />
      <dl>
        <Kv label={COPY.detailPane.reservedTo}>
          <Icon name="circle-user-round" size={14} className="text-ink-3" />
          {COPY.detailPane.reservedValue(head.reserved_user_name ?? "", role.value)}
        </Kv>
        {card.context.map((c) => (
          <Kv key={c.key} label={c.label}>
            {c.value}
          </Kv>
        ))}
        <Kv label={COPY.detailPane.proposedBy}>
          <ProposedBy
            by={ranBy}
            on={proposedOn === undefined ? "" : formatDate(proposedOn, { now })}
          />
        </Kv>
      </dl>
      {why !== "" && (
        <>
          <Band>{COPY.detailPane.why}</Band>
          <div className="flex gap-[10px] px-[14px] py-[12px] hairline-b">
            <span
              aria-hidden
              className="mt-[2px] flex size-[15px] flex-none items-center justify-center rounded-full bg-green text-card"
            >
              <Icon name="check" size={12} />
            </span>
            <AgentText text={why} className="text-para text-ink-2" />
          </div>
        </>
      )}
      <div className="px-[14px] py-[10px] hairline-b" data-home02="options">
        <RadioGroup
          label={card.question}
          options={shown.map((o) => ({
            value: o.key,
            label: o.label,
            ...(open ? {} : { disabled: true }),
          }))}
          {...(chosen === undefined ? {} : { value: chosen })}
          onChange={(v) => {
            if (open) onDraft({ ...draft, option: v });
          }}
        />
        <ul className="mt-[6px] flex flex-col gap-[8px]">
          {shown.map((o) => (
            <li key={o.key} data-option={o.key} className="flex flex-col gap-[4px] pl-[26px]">
              {o.key === recommended && (
                <Tag className="self-start">{COPY.detailPane.recommendation}</Tag>
              )}
              {o.detail !== null && (
                <span className="text-dense leading-[1.4] text-ink-2">{o.detail}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
      {sources.length > 0 && (
        <>
          <Band>{COPY.detailPane.evidence}</Band>
          <ul aria-label={COPY.detailPane.evidence}>
            {sources.map((s) => (
              <SourceRow key={s.title} title={s.title} n={s.n} />
            ))}
          </ul>
        </>
      )}
      {open && (
        <div className="flex flex-col gap-[6px] px-[14px] py-[12px]">
          <label htmlFor={`${ids}-why`} className="text-dense text-ink-2">
            {COPY.detailPane.rationaleLabel}
          </label>
          <textarea
            id={`${ids}-why`}
            required
            value={draft.words}
            placeholder={COPY.detailPane.rationalePlaceholder}
            onChange={(event) => {
              onDraft({ ...draft, words: event.target.value });
            }}
            className="h-[64px] w-full resize-none rounded-nested bg-nested p-[10px] text-body text-ink placeholder:text-ink-3"
          />
        </div>
      )}
    </div>
  );
}

function DecisionFooter({ gate, draft, onDraft }: DetailProps): JSX.Element | null {
  const actor = useActor();
  const openOverlay = useOpenOverlay();
  const queryClient = useQueryClient();
  const query = useDecisionCard(gate.subject.id);
  const card = query.data;
  const writes = useDecisionWrites(card);
  const decide = useGate({
    command: () => writes.decide(draft.option ?? "", [], draft.words.trim()),
    doneText: () => COPY.detailPane.decisionRecorded,
    failedText: COPY.detailPane.decideFailed,
    onDone: () => {
      onDraft({ words: "" });
      void queryClient.invalidateQueries({ queryKey: humanGateListQueryKey() });
      void queryClient.invalidateQueries({ queryKey: humanGateCountsQueryKey() });
    },
  });
  if (card === undefined) return null;
  const head = card.card;
  if (card.decision !== null) {
    return card.note === null ? null : (
      <p data-home02="decided-note" className="text-dense text-ink-2">
        {card.note}
      </p>
    );
  }
  const reservedHere = head.allowed_actions.includes("decision.decide");
  // DV-1 (AC7.1): an option and a rationale, whichever option is chosen.
  const ready = draft.option !== undefined && draft.words.trim() !== "" && decide.phase !== "busy";
  const allowed = gate.allowed_actions ?? [];
  return (
    <Footer line={COPY.detailPane.reservedLine(roleOf(head.reserved_role).line)}>
      {decide.blocked !== null && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.detailPane.decideFailed}
        </p>
      )}
      {reservedHere && (
        <HumanAction
          verb="Decide"
          actor={actor}
          variant="primary"
          icon="check"
          className="w-full"
          disabled={!ready}
          loading={decide.phase === "busy"}
          onClick={() => {
            void decide.run();
          }}
        />
      )}
      {head.allowed_actions.includes("decision.request_analysis") && (
        <Button
          variant="secondary"
          className="w-full"
          opensDialog
          aria-haspopup="dialog"
          onClick={() => {
            openOverlay(ov.SHL11(head.id));
          }}
        >
          {COPY.detailPane.requestMore}
        </Button>
      )}
      {PLANNED_VISIBLE &&
        (allowed.includes("human_gate.reassign") || allowed.includes("human_gate.snooze")) && (
          // I-01-T19 wires the person picker and the snooze menu.
          <span className="flex justify-center gap-[16px]">
            {allowed.includes("human_gate.reassign") && (
              <Button variant="ghost" size="sm" opensDialog disabled>
                {COPY.detailPane.reassign}
              </Button>
            )}
            {allowed.includes("human_gate.snooze") && (
              <Button variant="ghost" size="sm" opensDialog disabled>
                {COPY.detailPane.snooze}
              </Button>
            )}
          </span>
        )}
    </Footer>
  );
}

// ---- Sign-off -------------------------------------------------------------------------------

const str = (facts: EligibilityCheckOut["facts"], key: string): string => {
  const v = (facts as Record<string, unknown>)[key];
  return typeof v === "string" || typeof v === "number" ? String(v) : "";
};

/** The banner's words from the failing check (c's M-2 fix), or a plain line for anything else. */
function blockedText(check: EligibilityCheckOut): string {
  const off = str(check.facts, "off");
  return off === ""
    ? COPY.detailPane.blockedOther
    : COPY.detailPane.blocked(
        str(check.facts, "check"),
        off,
        str(check.facts, "fix"),
        str(check.facts, "awaits"),
      );
}

/** Where the blocking check points: an agent proposal opens SHL-10, a decision card SHL-11. */
function blockerOverlay(check: EligibilityCheckOut | undefined): OverlayRef | undefined {
  const ref = check?.refs[0];
  if (ref === undefined) return undefined;
  if (ref.type === "agent_proposal" || ref.type === "proposal") return SHL10(ref.id);
  if (ref.type === "decision_card") return ov.SHL11(ref.id);
  return undefined;
}

function useSignOff(gate: HumanGateOut) {
  const level = levelOf(gate.role ?? undefined) ?? "L4_partner";
  const ladder = useSignOffLadder(gate.subject);
  const eligibility = useSignOffEligibility(gate.subject, level);
  return { level, ladder, eligibility };
}

function SignOffBody({ gate }: DetailProps): JSX.Element {
  const { level, ladder, eligibility } = useSignOff(gate);
  const data = eligibility.data;
  if (data === undefined || ladder.data === undefined) {
    return <Loading failed={eligibility.isError || ladder.isError} />;
  }
  const levels = ladder.data.levels;
  const initials = (l: string): string =>
    levels.find((x) => x.level === l)?.latest?.initials ?? "";
  const failing = data.checks.find((c) => c.result === "fail");
  const t = data.target;
  return (
    <div
      data-home02-detail="sign_off"
      data-blocked={failing !== undefined}
      className="flex flex-col"
    >
      <TitleBand title={COPY.detailPane.title(t.label, t.context_label)} />
      <dl>
        <Kv label={COPY.detailPane.workpaper}>{COPY.detailPane.version(t.label, t.version_no)}</Kv>
        <Kv label={COPY.detailPane.level}>{COPY.levels[level] ?? level}</Kv>
        {initials("L1_preparer") !== "" && (
          <Kv label={COPY.detailPane.prepared}>
            {COPY.detailPane.signed(COPY.detailPane.prepared, initials("L1_preparer"))}
          </Kv>
        )}
        {initials("L2_reviewer") !== "" && (
          <Kv label={COPY.detailPane.reviewed}>
            {COPY.detailPane.signed(COPY.detailPane.reviewed, initials("L2_reviewer"))}
          </Kv>
        )}
      </dl>
      {failing !== undefined && (
        <div
          role="status"
          data-home02="blocked"
          className="mx-[14px] my-[12px] flex gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[10px] text-dense text-amber-ink"
        >
          <Icon name="triangle-alert" size={14} className="mt-[1px] flex-none" />
          {blockedText(failing)}
        </div>
      )}
    </div>
  );
}

function SignOffFooter({ gate }: DetailProps): JSX.Element | null {
  const actor = useActor();
  const openOverlay = useOpenOverlay();
  const { level, eligibility } = useSignOff(gate);
  const data = eligibility.data;
  if (data === undefined) return null;
  const failing = data.checks.find((c) => c.result === "fail");
  const blocker = blockerOverlay(failing);
  const levelLabel = COPY.levels[level] ?? level;
  return (
    <Footer {...(failing === undefined ? { line: COPY.detailPane.signsAt(levelLabel) } : {})}>
      <HumanAction
        verb="Sign off"
        actor={actor}
        opensDialog
        variant="primary"
        className="w-full"
        aria-haspopup="dialog"
        disabled={!data.eligible}
        onClick={() => {
          openOverlay(ov.SHL12(gate.subject.type, gate.subject.id, level));
        }}
      />
      {blocker !== undefined && (
        <Button
          variant="secondary"
          className="w-full"
          aria-haspopup="dialog"
          onClick={() => {
            openOverlay(blocker);
          }}
        >
          {COPY.detailPane.openProposal}
        </Button>
      )}
    </Footer>
  );
}

// ---- Agent output ---------------------------------------------------------------------------

function ProposalBody({ gate }: DetailProps): JSX.Element {
  const now = useNow();
  const name = useNames(gate.engagement_id);
  const query = useProposal(gate.subject.id);
  const proposal: AgentProposalOut | undefined = query.data;
  if (proposal === undefined) return <Loading failed={query.isError} />;
  const level = gate.role == null ? undefined : COPY.levels[gate.role];
  const by = name(gate.proposed_by?.initiator_user_id);
  const on = gate.proposed_by?.at;
  return (
    <div data-home02-detail="proposal" className="flex flex-col">
      <TitleBand title={proposal.title} />
      <dl>
        <Kv label={COPY.detailPane.workItem}>{proposal.context_label}</Kv>
        <Kv label={COPY.detailPane.proposedBy}>
          {/* g draws the run's person without a date. */}
          <ProposedBy by={by} on={on === undefined || by !== "" ? "" : formatDate(on, { now })} />
        </Kv>
        {level !== undefined && <Kv label={COPY.detailPane.level}>{level}</Kv>}
      </dl>
      <section
        aria-label={COPY.detailPane.reasoning}
        className="m-[14px] flex flex-col gap-[6px] rounded-nested bg-card px-[16px] py-[12px] shadow-e1"
      >
        <h4 className="text-section font-medium">{COPY.detailPane.reasoning}</h4>
        <AgentText text={proposal.reasoning} className="text-para text-ink-2" />
      </section>
      {proposal.evidence.length > 0 && (
        <>
          <Band>{COPY.detailPane.source}</Band>
          <ul aria-label={COPY.detailPane.source}>
            {proposal.evidence.map((e) => (
              <SourceRow key={e.evidence_version_id} title={e.label} n={e.citation_count} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function ProposalFooter({ gate }: DetailProps): JSX.Element | null {
  const actor = useActor();
  const openOverlay = useOpenOverlay();
  const query = useProposal(gate.subject.id);
  const proposal = query.data;
  if (proposal === undefined) return null;
  const allowed = proposal.allowed_actions;
  const open = (): void => {
    openOverlay(SHL10(proposal.ref));
  };
  return (
    <Footer line={COPY.detailPane.agentCannotApprove}>
      {allowed.includes("proposal.approve") && (
        <HumanAction
          verb="Approve"
          actor={actor}
          label={COPY.detailPane.approveAdjustments}
          icon="check"
          variant="primary"
          className="w-full"
          aria-haspopup="dialog"
          onClick={open}
        />
      )}
      {allowed.includes("proposal.reject") && (
        <Button
          variant="secondary"
          className="w-full"
          opensDialog
          aria-haspopup="dialog"
          onClick={open}
        >
          {COPY.detailPane.reject}
        </Button>
      )}
    </Footer>
  );
}

// ---- Approvals & sends, and the generic fallback ---------------------------------------------

function ApprovalBody({ gate }: DetailProps): JSX.Element {
  const now = useNow();
  return (
    <div data-home02-detail="generic" data-subkind={gate.subkind} className="flex flex-col">
      <TitleBand title={gate.title ?? gate.subkind} />
      <dl>
        {gate.due_on !== null && (
          <Kv label={COPY.detailPane.due}>{formatDate(gate.due_on, { now })}</Kv>
        )}
      </dl>
      {gate.context != null && gate.context !== "" && (
        <p className="px-[14px] py-[10px] text-dense leading-[1.55] text-ink-2">{gate.context}</p>
      )}
    </div>
  );
}

function ApprovalFooter({ gate, href }: DetailProps): JSX.Element | null {
  const actor = useActor();
  const openOverlay = useOpenOverlay();
  if (gate.kind === "final_approval" && gate.subject.type === "tax_return") {
    return (
      <Footer>
        <HumanAction
          verb="Approve"
          actor={actor}
          label={COPY.detailPane.finalApproval}
          opensDialog
          variant="primary"
          className="w-full"
          aria-haspopup="dialog"
          onClick={() => {
            openOverlay(ov.SHL12(gate.subject.type, gate.subject.id, "L4_partner"));
          }}
        />
      </Footer>
    );
  }
  if (gate.kind === "send" && PLANNED_VISIBLE) {
    // SIG-01 "To send" is planned (N-02): the verb shows, disabled, until its host is routed.
    return (
      <Footer>
        <HumanAction
          verb="Send"
          actor={actor}
          label={COPY.detailPane.send}
          opensDialog
          variant="primary"
          className="w-full"
          disabled
        />
      </Footer>
    );
  }
  if (href === undefined) return null;
  return (
    <Footer>
      <Button variant="secondary" className="w-full" asChild>
        <a href={href}>{COPY.open}</a>
      </Button>
    </Footer>
  );
}

// ---- Dispatch -------------------------------------------------------------------------------

const BODY = {
  decision: DecisionBody,
  sign_off: SignOffBody,
  proposal: ProposalBody,
  approval: ApprovalBody,
} as const;
const FOOTER = {
  decision: DecisionFooter,
  sign_off: SignOffFooter,
  proposal: ProposalFooter,
  approval: ApprovalFooter,
} as const;

/** The detail's body for the gate's class. */
export function GateDetailBody(props: DetailProps): JSX.Element {
  const Body = BODY[classOf(props.gate)];
  return <Body {...props} />;
}

/** The detail's pinned footer for the gate's class: its verbs and the reserved-role line. */
export function GateDetailFooter(props: DetailProps): JSX.Element {
  const Foot = FOOTER[classOf(props.gate)];
  return <Foot {...props} />;
}
