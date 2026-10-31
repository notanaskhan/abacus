import type {
  IssueCreateIn,
  IssueDetailOut,
  IssueExplanationOut,
  IssueItemOut,
  IssueLinkOut,
} from "@abacus/api-client";
import { clientContactsOptions } from "@abacus/api-client/query";
import {
  AgentMonogram,
  AgentText,
  Button,
  Checkbox,
  Icon,
  Picker,
  RadioGroup,
  Segmented,
  SheetModal,
  cn,
  time,
  toast,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useId, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import type { OverlayRef } from "../../app-core/overlays";
import { useSession } from "../../app-core/session";
import { useEngagementTeam } from "../../domain/engagements";
import {
  type FixScope,
  type IssueKind,
  useIssue,
  useIssueWrites,
  useIssues,
  useProposal,
  useRecordIssues,
} from "../../domain/review";
import { COPY } from "./copy";

// SHL-15 · Issue composer & fix instructions (P-04-T54; P-04 §3 F7; the handoff's SHL-15 folder):
// the O3 sheet where a person creates an issue or tells the agent exactly how to fix one, and the
// T9 detail block of one issue that a host (TAX-06, TXP-10, AUD-15) mounts. Overlay refs:
//
//   ?ov=issue:<issueId>                               a   Fix instructions
//   ?ov=issue:new:<recordType>:<recordId>[:<engId>]   b c New issue
//   ?ov=issue:bulk:<recordType>:<recordId>:<id,id>    e   Instructions for n issues
//
// Frames: a (Kevin Osei) the issue card, the agent's suggestion with "Use suggestion", the
// instructions, the scope ("This issue only" / "All 2 Missing information issues on this return");
// DF-13 removes the propose-only checkbox: every fix ends in a proposal a person accepts (DEC-53).
// With no fix runner the API answers 409 `fix_runner_unavailable` and the sheet shows the
// agents-off state. b (Ana Cruz) a Waiting on client issue with an internal note and separate
// client wording; "Create & send to client" creates the issue and sends only the client wording
// (one POR-04 request, Idempotency-Key). c (Samuel Ito) a field flag's Review point; the record's
// Issues count moves 4 → 5. e one shared instruction for the picked issues, scope locked. The T9
// detail (`IssueFixDetail`): a′ "In progress — agent fixing" with the run row, a″ the proposed
// values as ghosts with Accept (SHL-10), d the agent's explanation with its citations. Agent text
// renders through AgentText and carries no control; nothing here resolves, approves or edits a
// value (INV-1).

const SHL10 = (ref: string): OverlayRef => ({ key: "approve", args: [ref] });

const kindWord = (kind: string): string => COPY.kinds[kind] ?? kind;
const first = (name: string): string => name.split(" ")[0] ?? name;

// ---- Shared pieces --------------------------------------------------------------------------

function Flag({ priority }: { priority: string }): JSX.Element {
  return (
    <Icon
      name="flag"
      size={14}
      className={cn("flex-none", priority === "high" ? "text-red" : "text-amber")}
    />
  );
}

function Kv({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[33px] items-center justify-between gap-[12px] px-[14px] py-[6px] hairline-b last:shadow-none">
      <dt className="flex-none text-body text-ink-2">{label}</dt>
      <dd className="flex min-w-0 flex-wrap items-center justify-end gap-[6px] text-right text-body">
        {children}
      </dd>
    </div>
  );
}

function Assignee({ issue }: { issue: IssueItemOut }): JSX.Element {
  return issue.assignee_agent ? (
    <span className="flex items-center gap-[6px]" data-actor="agent">
      <AgentMonogram size={16} label={COPY.agent} />
      {COPY.agent}
    </span>
  ) : (
    <span>{issue.assignee_name ?? ""}</span>
  );
}

/** A linked chip; a file chip is lit in the match purple (its target lights in the underlay). */
function Chip({ label, kind }: { label: string; kind: IssueLinkOut["kind"] }): JSX.Element {
  const file = kind === "file";
  return (
    <span
      data-link={kind}
      className={cn(
        "inline-flex h-[26px] items-center gap-[6px] rounded-pill px-[10px] text-dense",
        file ? "bg-match-bg text-match-ink ring-1 ring-match-line" : "bg-card shadow-e1",
      )}
    >
      <Icon name={file ? "file" : "table"} size={13} />
      {label}
    </span>
  );
}

function Card({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label?: string;
}): JSX.Element {
  return (
    <section
      {...(label === undefined ? {} : { "aria-label": label })}
      className={cn("overflow-hidden rounded-pane bg-card shadow-e1", className)}
    >
      {children}
    </section>
  );
}

function Band({ children }: { children: ReactNode }): JSX.Element {
  return (
    <p className="flex h-[40px] items-center px-[14px] text-section font-medium hairline-b">
      {children}
    </p>
  );
}

function Loading({ failed }: { failed: boolean }): JSX.Element {
  return <p className="p-[12px] text-meta text-ink-3">{failed ? COPY.missing : COPY.loading}</p>;
}

function IssueCard({ detail }: { detail: IssueDetailOut }): JSX.Element {
  const issue = detail.issue;
  return (
    <Card label={detail.title}>
      <h3 className="flex items-start gap-[8px] px-[14px] py-[12px] text-section leading-[1.3] font-medium hairline-b">
        <Flag priority={issue.priority} />
        {detail.title}
      </h3>
      <dl>
        <Kv label={COPY.kv.class}>
          <span className="text-ink-2">{kindWord(issue.kind)}</span>
        </Kv>
        <Kv label={COPY.kv.priority}>{COPY.priorities[issue.priority] ?? issue.priority}</Kv>
        <Kv label={COPY.kv.assignedTo}>
          <Assignee issue={issue} />
        </Kv>
        {detail.links.length > 0 && (
          <Kv label={COPY.kv.linked}>
            {detail.links.map((l) => (
              <Chip key={`${l.kind}:${l.label}`} label={l.label} kind={l.kind} />
            ))}
          </Kv>
        )}
      </dl>
    </Card>
  );
}

// ---- a: Fix instructions ----------------------------------------------------------------------

export interface FixInstructionsSheetProps {
  issueId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FixInstructionsSheet({
  issueId,
  open,
  onOpenChange,
}: FixInstructionsSheetProps): JSX.Element {
  const query = useIssue(issueId);
  const detail = query.data;
  const list = useRecordIssues(
    detail === undefined ? null : { type: detail.issue.record.type, id: detail.issue.record.id },
  );
  const items = list.data?.items ?? [];
  const at = items.findIndex((i) => i.id === issueId);
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.fixTitle}
      {...(at < 0
        ? {}
        : {
            meta: (
              <span className="text-meta text-ink-3">
                {COPY.position(at + 1, list.data?.total ?? items.length)}
              </span>
            ),
          })}
    >
      {detail === undefined ? (
        <Loading failed={query.isError} />
      ) : (
        <FixBody
          key={`${detail.issue.id}:${String(detail.issue.version)}`}
          detail={detail}
          classCount={items.filter((i) => i.kind === detail.issue.kind).length}
          onDone={() => {
            onOpenChange(false);
          }}
        />
      )}
    </SheetModal>
  );
}

function FixBody({
  detail,
  classCount,
  onDone,
}: {
  detail: IssueDetailOut;
  classCount: number;
  onDone: () => void;
}): JSX.Element {
  const ids = useId();
  const writes = useIssueWrites();
  const issue = detail.issue;
  const suggestion = detail.suggestion;
  const [text, setText] = useState(detail.fix_instructions?.text ?? "");
  const [scope, setScope] = useState<FixScope>(detail.fix_instructions?.scope ?? "this_issue");
  const [busy, setBusy] = useState(false);
  const [agentsOff, setAgentsOff] = useState(false);
  const [failed, setFailed] = useState(false);
  const allowed = issue.allowed_actions.includes("fix_instruction.set");
  const submit = async (): Promise<void> => {
    setBusy(true);
    setFailed(false);
    try {
      await writes.setFix(issue, text.trim(), scope);
      toast.show({ kind: "success", text: COPY.fixSet });
      onDone();
    } catch (error) {
      if ((error as { detail?: unknown }).detail === "fix_runner_unavailable") setAgentsOff(true);
      else setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-shl15="fix" className="flex flex-col gap-[12px] p-[12px]">
      <IssueCard detail={detail} />
      {agentsOff && (
        <p
          role="status"
          data-shl15="agents-off"
          className="flex gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[10px] text-dense text-amber-ink"
        >
          <Icon name="triangle-alert" size={14} className="mt-[1px] flex-none" />
          {COPY.agentsOff}
        </p>
      )}
      {suggestion !== null && (
        <section
          aria-label={COPY.suggested}
          className="flex flex-col gap-[6px] rounded-nested bg-card px-[12px] py-[10px] inset-shadow-hair"
        >
          <p className="flex items-center gap-[6px] text-dense font-medium text-ink-2">
            <Icon name="sparkles" size={13} />
            {COPY.suggested}
          </p>
          <AgentText text={suggestion.text} className="text-para text-ink" />
          {/* "Use suggestion" belongs to the person's editor, not to the agent's text. */}
          <span className="flex justify-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setText(suggestion.text);
              }}
            >
              {COPY.useSuggestion}
            </Button>
          </span>
        </section>
      )}
      <label htmlFor={`${ids}-text`} className="sr-only">
        {COPY.instructions}
      </label>
      <textarea
        id={`${ids}-text`}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
        }}
        className="min-h-[140px] w-full resize-y rounded-nested bg-card px-[12px] py-[10px] text-body leading-[1.5] shadow-e1"
      />
      <Card label={COPY.applyTo}>
        <Band>{COPY.applyTo}</Band>
        <div className="px-[14px] py-[8px]">
          <RadioGroup
            label={COPY.applyTo}
            value={scope}
            onChange={(v) => {
              setScope(v as FixScope);
            }}
            options={[
              { value: "this_issue", label: COPY.thisIssue },
              {
                value: "all_of_class",
                label: COPY.allOfClass(classCount, kindWord(issue.kind)),
                ...(classCount > 1 ? {} : { disabled: true }),
              },
            ]}
          />
        </div>
      </Card>
      {failed && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.failed}
        </p>
      )}
      <div className="sticky bottom-0 -mx-[12px] -mb-[12px] flex justify-between gap-[8px] bg-shell px-[12px] py-[10px] shadow-[0_-0.5px_0_var(--color-hair)]">
        <Button variant="secondary" onClick={onDone}>
          {COPY.cancel}
        </Button>
        <Button
          variant="primary"
          icon="wrench"
          disabled={!allowed || agentsOff || text.trim() === "" || busy}
          loading={busy}
          onClick={() => {
            void submit();
          }}
        >
          {COPY.setFix}
        </Button>
      </div>
    </div>
  );
}

// ---- b, c: New issue --------------------------------------------------------------------------

/** What the composer opens with: a host's prefill (a field flag, a grid selection). */
export interface IssueDraftIn {
  create: IssueCreateIn;
  chips: readonly { label: string; kind: IssueLinkOut["kind"] }[];
}

export interface NewIssueSheetProps {
  record: { type: string; id: string };
  /** The record's engagement: its team are the assignees, its client's contacts the recipients. */
  engagementId?: string | null;
  draft?: IssueDraftIn;
  /** The header's right: "EBP-04 · Northwind". */
  meta?: string;
  /** The record's short name in the Issues count line ("Feld"). */
  context?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const AGENT = "agent";

export function NewIssueSheet({
  record,
  engagementId = null,
  draft,
  meta,
  context = "",
  open,
  onOpenChange,
}: NewIssueSheetProps): JSX.Element {
  const session = useSession();
  const ids = useId();
  const writes = useIssueWrites();
  const team = useEngagementTeam(engagementId ?? "", engagementId !== null);
  const contacts = useQuery({
    ...clientContactsOptions({ path: { engagement_id: engagementId ?? "" } }),
    enabled: engagementId !== null,
  });
  const issues = useRecordIssues(record);
  const start = draft?.create;
  const [title, setTitle] = useState(start?.title ?? "");
  const [kind, setKind] = useState<IssueKind>(start?.kind ?? "review_point");
  const [priority, setPriority] = useState<string>(start?.priority ?? "medium");
  const [assignee, setAssignee] = useState<string>(
    start?.assignee_agent === true ? AGENT : (start?.assignee_user_id ?? session.user?.id ?? ""),
  );
  const [contact, setContact] = useState<string>(start?.client_contact_id ?? "");
  const [note, setNote] = useState(start?.internal_note ?? "");
  const [wording, setWording] = useState(start?.client_wording ?? "");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const toClient = kind === "waiting_on_client";
  const people = team.data ?? [];
  const recipients = contacts.data ?? [];
  const recipient = recipients.find((c) => c.id === contact);
  const recipientName = recipient?.display_name ?? "";
  const before = issues.data?.total ?? 0;
  const dirty = title !== (start?.title ?? "") || note !== (start?.internal_note ?? "");

  const body = (): IssueCreateIn => ({
    record_type: record.type,
    record_id: record.id,
    kind,
    priority: priority as IssueCreateIn["priority"] & string,
    title: title.trim(),
    ...(note.trim() === "" ? {} : { internal_note: note.trim() }),
    ...(toClient && wording.trim() !== "" ? { client_wording: wording.trim() } : {}),
    ...(toClient && contact !== "" ? { client_contact_id: contact } : {}),
    assignee_agent: assignee === AGENT,
    ...(assignee === AGENT || assignee === "" ? {} : { assignee_user_id: assignee }),
    links: [...(start?.links ?? [])],
  });
  const create = async (send: boolean): Promise<void> => {
    setBusy(true);
    setFailed(false);
    try {
      const made = await writes.create(body());
      if (send) {
        await writes.sendToClient(made, wording.trim(), contact);
        toast.show({ kind: "success", text: COPY.sent(first(recipientName)) });
      } else {
        toast.show({ kind: "success", text: COPY.created });
      }
      onOpenChange(false);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  const ready = title.trim() !== "" && !busy;
  const sendReady = ready && toClient && wording.trim() !== "" && contact !== "";

  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.newTitle}
      dirty={dirty}
      {...(meta === undefined
        ? {}
        : { meta: <span className="text-meta text-ink-3">{meta}</span> })}
    >
      <div data-shl15="new" className="flex flex-col gap-[12px] p-[12px]">
        <Card label={COPY.issue}>
          <Band>{COPY.issue}</Band>
          <dl>
            <div className="flex gap-[12px] px-[14px] py-[10px] hairline-b">
              <dt>
                <label htmlFor={`${ids}-title`} className="text-body text-ink-2">
                  {COPY.kv.title}
                </label>
              </dt>
              <dd className="flex-1">
                <textarea
                  id={`${ids}-title`}
                  rows={2}
                  value={title}
                  onChange={(e) => {
                    setTitle(e.target.value);
                  }}
                  className="w-full resize-none bg-transparent text-body font-medium outline-none"
                />
              </dd>
            </div>
            <div className="flex flex-col gap-[8px] px-[14px] py-[10px] hairline-b">
              <dt className="text-body text-ink-2">{COPY.kv.class}</dt>
              <dd>
                <Segmented
                  size="small"
                  label={COPY.kv.class}
                  options={COPY.pickable.map(kindWord)}
                  active={kindWord(kind)}
                  onChange={(label) => {
                    const next = COPY.pickable.find((k) => kindWord(k) === label);
                    if (next !== undefined) setKind(next);
                  }}
                />
              </dd>
            </div>
            <Kv label={COPY.kv.priority}>
              <Picker
                label={COPY.kv.priority}
                variant="fill"
                value={priority}
                onChange={setPriority}
                options={Object.entries(COPY.priorities).map(([value, label]) => ({
                  value,
                  label,
                }))}
              />
            </Kv>
            <Kv label={COPY.kv.assignee}>
              <Picker
                label={COPY.kv.assignee}
                variant="fill"
                value={assignee}
                onChange={setAssignee}
                menuWidth={240}
                options={[
                  { value: AGENT, label: COPY.agent },
                  ...people.map((p) => ({
                    value: p.user_id,
                    label:
                      p.user_id === session.user?.id ? COPY.you(p.display_name) : p.display_name,
                  })),
                ]}
              />
            </Kv>
            {toClient && (
              <Kv label={COPY.kv.clientContact}>
                <Picker
                  label={COPY.kv.clientContact}
                  variant="fill"
                  value={contact}
                  onChange={setContact}
                  options={recipients.map((c) => ({
                    value: c.id,
                    label: `${c.display_name ?? c.email ?? ""} · ${c.role}`,
                  }))}
                />
              </Kv>
            )}
          </dl>
        </Card>
        {(draft?.chips.length ?? 0) > 0 && (
          <Card label={COPY.kv.linked}>
            <Band>{COPY.kv.linked}</Band>
            <p className="flex flex-wrap gap-[8px] px-[14px] py-[10px]">
              {draft?.chips.map((c) => (
                <Chip key={c.label} label={c.label} kind={c.kind} />
              ))}
            </p>
          </Card>
        )}
        <Card label={COPY.internalNote}>
          <Band>
            <label htmlFor={`${ids}-note`}>{COPY.internalNote}</label>
          </Band>
          <textarea
            id={`${ids}-note`}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
            }}
            className="min-h-[120px] w-full resize-y bg-card px-[14px] py-[10px] text-dense leading-[1.55] outline-none"
          />
        </Card>
        {toClient && (
          <section
            aria-label={COPY.clientWording(first(recipientName))}
            data-shl15="client-wording"
            className="flex flex-col gap-[6px] rounded-pane bg-shell px-[14px] py-[10px] inset-shadow-hair"
          >
            <label htmlFor={`${ids}-wording`} className="text-meta text-ink-3">
              {COPY.clientWording(first(recipientName))}
            </label>
            <textarea
              id={`${ids}-wording`}
              value={wording}
              onChange={(e) => {
                setWording(e.target.value);
              }}
              className="min-h-[72px] w-full resize-y bg-transparent text-body leading-[1.55] outline-none"
            />
          </section>
        )}
        {failed && (
          <p role="alert" className="text-dense text-red-ink">
            {COPY.failed}
          </p>
        )}
        <div className="sticky bottom-0 -mx-[12px] -mb-[12px] flex flex-col gap-[6px] bg-shell px-[12px] py-[10px] shadow-[0_-0.5px_0_var(--color-hair)]">
          <div className="flex items-center justify-between gap-[8px]">
            <Button
              variant="secondary"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              {COPY.cancel}
            </Button>
            <span className="flex gap-[8px]">
              <Button
                variant={toClient ? "secondary" : "primary"}
                disabled={!ready}
                loading={busy && !toClient}
                onClick={() => {
                  void create(false);
                }}
              >
                {COPY.createIssue}
              </Button>
              {toClient && (
                <Button
                  variant="primary"
                  data-human-verb="Send"
                  disabled={!sendReady}
                  loading={busy}
                  onClick={() => {
                    void create(true);
                  }}
                >
                  {COPY.createAndSend}
                </Button>
              )}
            </span>
          </div>
          <p className="text-meta text-ink-3">
            {toClient
              ? COPY.sendsAs(first(recipientName))
              : issues.data === undefined
                ? null
                : COPY.issuesCount(context, before, before + 1)}
          </p>
        </div>
      </div>
    </SheetModal>
  );
}

// ---- e: Instructions for n issues ---------------------------------------------------------------

export interface BulkInstructionsSheetProps {
  issueIds: readonly string[];
  initialText?: string;
  meta?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BulkInstructionsSheet({
  issueIds,
  initialText = "",
  meta,
  open,
  onOpenChange,
}: BulkInstructionsSheetProps): JSX.Element {
  const ids = useId();
  const writes = useIssueWrites();
  const reads = useIssues(issueIds);
  const details = reads.flatMap((r) => (r.data === undefined ? [] : [r.data]));
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set(issueIds));
  const [text, setText] = useState(initialText);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const chosen = details.filter((d) => picked.has(d.issue.id)).map((d) => d.issue);
  const submit = async (): Promise<void> => {
    setBusy(true);
    setFailed(false);
    try {
      await writes.setFixBulk(chosen, text.trim());
      toast.show({ kind: "success", text: COPY.fixSet });
      onOpenChange(false);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.bulkTitle(issueIds.length)}
      {...(meta === undefined
        ? {}
        : { meta: <span className="text-meta text-ink-3">{meta}</span> })}
    >
      <div data-shl15="bulk" className="flex flex-col gap-[12px] p-[12px]">
        <Card label={COPY.issues}>
          <Band>{COPY.issues}</Band>
          <ul>
            {details.map((d) => (
              <li
                key={d.issue.id}
                className="flex items-start gap-[10px] px-[14px] py-[8px] hairline-b last:shadow-none"
              >
                <Checkbox
                  label={d.title}
                  checked={picked.has(d.issue.id)}
                  onChange={(checked) => {
                    setPicked((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(d.issue.id);
                      else next.delete(d.issue.id);
                      return next;
                    });
                  }}
                />
                <Flag priority={d.issue.priority} />
                <span className="flex flex-col gap-[2px]">
                  <span className="text-body">{d.title}</span>
                  <span className="text-meta text-ink-3">{kindWord(d.issue.kind)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
        <label htmlFor={`${ids}-text`} className="sr-only">
          {COPY.instructions}
        </label>
        <textarea
          id={`${ids}-text`}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
          className="min-h-[200px] w-full resize-y rounded-nested bg-card px-[12px] py-[10px] text-body leading-[1.5] shadow-e1"
        />
        <p className="flex items-center gap-[8px] rounded-pane bg-card px-[14px] py-[10px] text-body shadow-e1">
          <Icon name="lock" size={14} className="text-ink-3" />
          {COPY.scopeLocked(chosen.length)}
        </p>
        {failed && (
          <p role="alert" className="text-dense text-red-ink">
            {COPY.failed}
          </p>
        )}
        <div className="sticky bottom-0 -mx-[12px] -mb-[12px] flex justify-between gap-[8px] bg-shell px-[12px] py-[10px] shadow-[0_-0.5px_0_var(--color-hair)]">
          <Button
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            {COPY.cancel}
          </Button>
          <Button
            variant="primary"
            icon="wrench"
            disabled={chosen.length === 0 || text.trim() === "" || busy}
            loading={busy}
            onClick={() => {
              void submit();
            }}
          >
            {COPY.setFixFor(chosen.length)}
          </Button>
        </div>
      </div>
    </SheetModal>
  );
}

// ---- a′, a″, d: the issue's T9 detail block ---------------------------------------------------

/** One explanation (d): read-only agent text with its citation chips (Sparkles, never a check). */
export function IssueExplanation({
  explanation,
}: {
  explanation: IssueExplanationOut;
}): JSX.Element {
  return (
    <section
      aria-label={COPY.explanation}
      data-shl15="explanation"
      className="flex flex-col gap-[6px] rounded-nested bg-shell px-[12px] py-[10px] inset-shadow-hair"
    >
      <p className="flex items-center gap-[6px]">
        <Icon name="sparkles" size={13} className="text-ink-2" />
        <span className="text-dense font-medium">{COPY.explanation}</span>
        <span className="text-meta text-ink-3">
          {COPY.explainedBy(time(explanation.explained_at))}
        </span>
      </p>
      <AgentText text={explanation.text} className="text-para text-ink-2" />
      <p className="flex flex-wrap gap-[6px]">
        {explanation.citations.map((c) => (
          <span
            key={c.citation_id}
            data-citation={c.citation_id}
            className="inline-flex h-[22px] items-center rounded-pill bg-match-bg px-[8px] text-pill-sm text-match-ink"
          >
            {c.label}
          </span>
        ))}
      </p>
    </section>
  );
}

function Proposed({ proposalId }: { proposalId: string }): JSX.Element | null {
  const openOverlay = useOpenOverlay();
  const query = useProposal(proposalId);
  const proposal = query.data;
  if (proposal === undefined) return null;
  const rows = proposal.rows.filter((r) => r.after !== null);
  return (
    <section data-shl15="proposed" className="flex flex-col">
      <p className="flex items-center gap-[8px] rounded-t-nested bg-card px-[14px] py-[10px] text-body shadow-e1">
        <span
          aria-hidden
          className="flex size-[16px] items-center justify-center rounded-full bg-green text-card"
        >
          <Icon name="check" size={12} />
        </span>
        <span className="flex-1">{COPY.proposedChanges(rows.length)}</span>
        <span className="text-meta text-ink-3">{time(proposal.proposed_at)}</span>
      </p>
      <ul className="mt-[12px] overflow-hidden rounded-nested bg-card shadow-e1">
        {rows.map((r) => (
          <li
            key={r.n}
            className="flex min-h-[52px] items-center justify-between gap-[12px] px-[16px] hairline-b"
          >
            <span className="text-body">{r.label}</span>
            {/* The proposed value as a ghost: not a value until a person accepts it (SHL-10). */}
            <span
              data-ghost=""
              className="rounded-[6px] border border-dashed border-match-line bg-match-bg px-[8px] py-[2px] text-body text-match-ink tabular-nums"
            >
              {r.after}
            </span>
          </li>
        ))}
        <li className="flex min-h-[52px] items-center justify-between gap-[12px] px-[16px]">
          <span className="text-meta text-ink-3">{COPY.proposedBy}</span>
          <Button
            variant="ghost"
            aria-haspopup="dialog"
            onClick={() => {
              openOverlay(SHL10(proposal.ref));
            }}
          >
            {COPY.accept}
          </Button>
        </li>
      </ul>
    </section>
  );
}

/** The issue's run, its proposal and its explanations, under the detail (a′, a″, d). */
export function IssueFixDetail({ issueId }: { issueId: string }): JSX.Element {
  const query = useIssue(issueId);
  const detail = query.data;
  if (detail === undefined) return <Loading failed={query.isError} />;
  const run = detail.fix_run;
  const running = run !== null && !["succeeded", "failed", "cancelled"].includes(run.status);
  return (
    <div data-shl15="detail" className="flex flex-col gap-[12px]">
      <IssueCard detail={detail} />
      {running && (
        <>
          <p className="text-meta text-ink-3">{COPY.inProgress}</p>
          <p
            data-shl15="run"
            className="flex items-center gap-[8px] rounded-nested bg-card px-[14px] py-[10px] text-body shadow-e1"
          >
            <AgentMonogram size={16} label={COPY.agent} />
            <span className="flex-1">{run.label}</span>
            <span className="text-meta text-ink-3">{COPY.running}</span>
          </p>
        </>
      )}
      {run?.status === "succeeded" && run.proposal_id !== null && (
        <Proposed proposalId={run.proposal_id} />
      )}
      {detail.explanations.map((e) => (
        <IssueExplanation key={e.id} explanation={e} />
      ))}
    </div>
  );
}

// ---- The overlay --------------------------------------------------------------------------------

export interface IssueSheetProps {
  args: readonly string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** `?ov=issue:…` (sheets-host): the composer the ref names. */
export function IssueSheet({ args, open, onOpenChange }: IssueSheetProps): JSX.Element | null {
  const [head, type, id, rest] = args;
  if (head === undefined) return null;
  if (head === "new" && type !== undefined && id !== undefined) {
    return (
      <NewIssueSheet
        record={{ type, id }}
        engagementId={rest ?? null}
        open={open}
        onOpenChange={onOpenChange}
      />
    );
  }
  if (head === "bulk" && rest !== undefined) {
    return (
      <BulkInstructionsSheet
        issueIds={rest.split(",").filter((s) => s !== "")}
        open={open}
        onOpenChange={onOpenChange}
      />
    );
  }
  return <FixInstructionsSheet issueId={head} open={open} onOpenChange={onOpenChange} />;
}
