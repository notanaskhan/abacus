// T-04-T29 (TASK-6828): TAX-06 Issues on a live build. The return's issues (C3's
// `GET /v1/issues?record_type=tax_return&record_id=…`, every status), each one's detail
// (`GET /v1/issues/{id}`: title, links, fix instructions, the fix run and its explanations), and
// the person's moves: Mark as Resolved with a note (`POST …/resolve` with the version seen),
// Set Fix Instructions (SHL-15 over the route), Explain… (`POST …/explanations`) and a ghost
// value's proposal (SHL-10, which approves at once with DEC-24's Undo for 10 s). The agent never
// resolves; a system-only issue (the Draft K-1) says so; every refusal shows its words.
import { issueListOptions, issueOptions, issueResolveMutation } from "@abacus/api-client/query";
import type { IssueItemOut } from "@abacus/api-client";
import { AgentText, Button, EmptyState, Pill } from "@abacus/ui";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { useIssueWrites } from "../../domain/review";
import { ov } from "../../routes/to";
import { blockerWords, RETURN_LIVE_KEYS, useReturnLive } from "../TAX-04/live-core";
import { COPY } from "./copy";

const OPEN: ReadonlySet<IssueItemOut["status"]> = new Set(["open", "in_progress", "reopened"]);
const KIND: Record<IssueItemOut["kind"], string> = {
  missing_information: "Missing information",
  action_required: "Action required",
  review_point: "Review point",
  waiting_on_client: "Waiting on client",
  exception: "Exception",
  engine_diagnostic: "Engine diagnostic",
};

export const ISSUES_LIVE_COPY = {
  loading: COPY.loading,
  open: "Open",
  resolved: "Resolved",
  proposal: "Review the proposal…",
  setFix: "Set Fix Instructions", // TAX-06 a (handoff): the detail's primary
  fixRunning: (label: string) => `◌ ${label}`,
} as const;

export interface IssuesLiveProps {
  returnId: string;
  engagementId: string | undefined;
}

function Detail({
  issue,
  onRefresh,
}: {
  issue: IssueItemOut;
  onRefresh: () => void;
}): JSX.Element {
  const detail = useQuery(issueOptions({ path: { issue_id: issue.id } }));
  const open = useOpenOverlay();
  const writes = useIssueWrites();
  const resolve = useMutation({ ...issueResolveMutation(), onSettled: onRefresh });
  const [note, setNote] = useState("");
  const [words, setWords] = useState<string[]>([]);
  const d = detail.data;
  if (d === undefined) {
    return <p className="p-[14px] text-ink-3">{COPY.loading}</p>;
  }
  const canResolve = issue.allowed_actions.includes("issue.resolve") && OPEN.has(issue.status);
  // C3's row actions carry update, resolve, verify and reopen; Set Fix Instructions
  // (`fix_instruction.set`) and Explain… (`issue.explain`) go to the same firm roles, and the
  // server authorises each write, so a refusal reads as its words.
  const canEdit = issue.allowed_actions.includes("issue.update") && OPEN.has(issue.status);
  const onResolve = async (): Promise<void> => {
    setWords([]);
    try {
      await resolve.mutateAsync({
        path: { issue_id: issue.id },
        body: { seen_version: issue.version, note: note.trim() },
      });
      setNote("");
    } catch (error) {
      setWords(blockerWords(error));
    }
  };
  const onExplain = async (): Promise<void> => {
    setWords([]);
    try {
      await writes.explain(issue);
    } catch (error) {
      setWords(blockerWords(error));
    }
  };
  return (
    <div data-issue-detail={issue.id} className="flex flex-col gap-[8px] p-[14px]">
      <div className="flex items-center gap-[6px] text-[15px] font-medium leading-[1.3]">
        {d.title}
        {issue.status === "in_progress" ? (
          <Pill variant="amber" size="state">
            {COPY.inProgress}
          </Pill>
        ) : null}
      </div>
      {d.fix_run !== null ? (
        <p data-run-row className="text-[12.5px] text-ink-2">
          {ISSUES_LIVE_COPY.fixRunning(d.fix_run.label)}
        </p>
      ) : null}
      <dl className="flex flex-col">
        {[
          ["Assigned to", issue.assignee_name ?? (issue.assignee_agent ? "Accrued Agent" : "—")],
          [
            "Priority",
            issue.priority === "high" ? "High" : issue.priority === "medium" ? "Medium" : "Low",
          ],
          ["Kind", KIND[issue.kind]],
        ].map(([k, v]) => (
          <div key={k} className="flex h-[35px] items-center justify-between">
            <dt className="text-ink-2">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      {d.links.length > 0 ? (
        <>
          <div className="flex h-[31px] items-center bg-band-hd px-[2px] text-[13.5px] font-medium">
            {COPY.linkedEntities}
          </div>
          <ul className="flex flex-wrap gap-[6px]">
            {d.links.map((l) => (
              <li
                key={`${l.kind}:${l.label}`}
                className="rounded-[6px] bg-nested px-[8px] py-[4px] text-[12.5px]"
              >
                {l.label}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {d.fix_instructions !== null ? (
        <p className="text-[12.5px] text-ink-2" data-fix-instructions>
          {d.fix_instructions.text}
        </p>
      ) : null}
      {/* The analyst's explanation is agent text (constitution FE-2): only through AgentText. */}
      {d.explanations.map((e) => (
        <div key={e.id} className="text-[12.5px] text-ink-2" data-explanation>
          <AgentText text={e.text} />
        </div>
      ))}
      <div className="flex flex-col gap-[8px]">
        {d.fix_run?.proposal_id != null ? (
          <Button
            variant="primary"
            onClick={() => {
              open(ov.SHL10(d.fix_run?.proposal_id as string));
            }}
          >
            {ISSUES_LIVE_COPY.proposal}
          </Button>
        ) : canEdit ? (
          <Button
            variant="primary"
            onClick={() => {
              open(ov.SHL15(issue.id));
            }}
          >
            {ISSUES_LIVE_COPY.setFix}
          </Button>
        ) : null}
        {canEdit ? (
          <Button variant="tonal" onClick={() => void onExplain()}>
            {COPY.explain}
          </Button>
        ) : null}
        {canResolve ? (
          <>
            <input
              aria-label="Resolution note"
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
              }}
              className="rounded-[6px] border border-hairline px-[6px] text-[12.5px]"
            />
            <Button
              variant="tonal"
              disabled={note.trim() === "" || resolve.isPending}
              title={note.trim() === "" ? COPY.resolveNoteRequired : undefined}
              onClick={() => void onResolve()}
            >
              ✓ {COPY.resolve}
            </Button>
          </>
        ) : null}
        {words.map((w) => (
          <p key={w} role="alert" className="text-[12.5px] text-red-ink">
            {w}
          </p>
        ))}
      </div>
    </div>
  );
}

export function IssuesLive({ returnId, engagementId }: IssuesLiveProps): JSX.Element {
  const interval = useReturnLive(engagementId);
  const queryClient = useQueryClient();
  const list = useQuery({
    ...issueListOptions({ query: { record_type: "tax_return", record_id: returnId, limit: 200 } }),
    refetchInterval: interval,
  });
  const items = list.data?.items ?? [];
  // The queue's titles are the details' (C3's list rows carry ids and enums only).
  const details = useQueries({
    queries: items.map((i) => issueOptions({ path: { issue_id: i.id } })),
  });
  const [selected, setSelected] = useState<string | null>(null);
  const refresh = (): void => {
    for (const queryKey of RETURN_LIVE_KEYS) void queryClient.invalidateQueries({ queryKey });
  };
  if (list.isPending) {
    return (
      <div data-screen="TAX-06" data-live aria-busy="true" className="p-[16px] text-ink-3">
        {COPY.loading}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div data-screen="TAX-06" data-live>
        <EmptyState title={COPY.emptyTitle}>{COPY.emptyBody}</EmptyState>
      </div>
    );
  }
  const current = items.find((i) => i.id === selected) ?? items.find((i) => OPEN.has(i.status));
  const title = (id: string): string =>
    details[items.findIndex((i) => i.id === id)]?.data?.title ?? "";
  const groups: [string, IssueItemOut[]][] = [
    [ISSUES_LIVE_COPY.open, items.filter((i) => OPEN.has(i.status))],
    [ISSUES_LIVE_COPY.resolved, items.filter((i) => !OPEN.has(i.status))],
  ];
  return (
    <div data-screen="TAX-06" data-live className="flex gap-[8px] p-[8px]">
      <div
        role="listbox"
        aria-label={COPY.queueHead}
        className="flex w-[262px] shrink-0 flex-col rounded-[10px] bg-card shadow-e1"
      >
        {groups.map(([group, rows]) =>
          rows.length === 0 ? null : (
            <div key={group}>
              <div className="flex h-[31px] items-center px-[12px] text-[13.5px] font-medium">
                {group}
              </div>
              {rows.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  role="option"
                  data-issue={r.id}
                  aria-selected={current?.id === r.id}
                  onClick={() => {
                    setSelected(r.id);
                  }}
                  className={`flex w-full items-start gap-[6px] py-[8px] pl-[20px] pr-[10px] text-left ${current?.id === r.id ? "bg-nested font-medium" : ""}`}
                >
                  <span aria-hidden className={r.priority === "high" ? "text-red" : "text-amber"}>
                    ⚑
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="line-clamp-2 text-[12.5px] leading-[1.32]">
                      {title(r.id)}
                    </span>
                    <span className="text-[11.5px] text-ink-3">{KIND[r.kind]}</span>
                  </span>
                  {OPEN.has(r.status) ? null : (
                    <Pill variant="green-tint" size="state">
                      {COPY.resolvedPill}
                    </Pill>
                  )}
                </button>
              ))}
            </div>
          ),
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col rounded-[10px] bg-card shadow-e1">
        {current === undefined ? null : (
          <Detail key={current.id} issue={current} onRefresh={refresh} />
        )}
      </div>
    </div>
  );
}
