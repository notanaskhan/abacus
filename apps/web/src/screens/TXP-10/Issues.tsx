// TXP-10 on the live client (T-05-T58): the queue (`GET …/issues`), the selected issue's detail
// (`GET /v1/issues/{id}`), the assignee picker (`GET …/issue-assignees`), and the person's moves:
// assign (`PATCH /v1/issues/{id}`), SHL-15 fix instructions and SHL-10 on the fix's proposal (the
// host's overlays; approving starts the checkpoint and Run 3), Send to client (POR-04) and Send
// reminder, Resolve with a note. A cell opens TXP-11 on it.
import type { WorkbookIssueAssigneeOptionOut, WorkbookReturnIssueOut } from "@abacus/api-client";
import {
  entityIssueAssigneesOptions,
  entityIssueRemindMutation,
  entityIssueResolveMutation,
  entityIssueSendMutation,
  entityIssuesOptions,
  issueOptions,
  issueUpdateMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { TXP10 } from "./index";

export function Issues({
  returnId,
  onOpen,
}: {
  returnId: string;
  /** The path after `/tax-returns/$returnId` (TXP-11 with a cell selected). */
  onOpen: (suffix: string) => void;
}): JSX.Element {
  const path = { return_id: returnId };
  const client = useQueryClient();
  const open = useOpenOverlay();
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showResolved, setShowResolved] = useState(false);
  const queue = useQuery(
    entityIssuesOptions({ path, query: { show_resolved: showResolved, ...(query ? { q: query } : {}) } }),
  );
  const detail = useQuery({
    ...issueOptions({ path: { issue_id: selected ?? "" } }),
    enabled: selected !== null,
  });
  const assignees = useQuery(entityIssueAssigneesOptions({ path }));
  const refresh = () => {
    void client.invalidateQueries({ queryKey: entityIssuesOptions({ path }).queryKey.slice(0, 1) });
    if (selected !== null) {
      void client.invalidateQueries({
        queryKey: issueOptions({ path: { issue_id: selected } }).queryKey,
      });
    }
  };
  const assign = useMutation({ ...issueUpdateMutation(), onSuccess: refresh });
  const send = useMutation({ ...entityIssueSendMutation(), onSuccess: refresh });
  const remind = useMutation({ ...entityIssueRemindMutation(), onSuccess: refresh });
  const resolve = useMutation({ ...entityIssueResolveMutation(), onSuccess: refresh });
  const key = () => ({ "Idempotency-Key": crypto.randomUUID() });
  return (
    <TXP10
      queue={queue.data}
      selectedId={selected}
      detail={detail.data}
      assignees={assignees.data?.items ?? []}
      showResolved={showResolved}
      query={query}
      onQuery={setQuery}
      onShowResolved={setShowResolved}
      onSelect={setSelected}
      onOpenCell={(sheet, range) => {
        onOpen(`/workpaper?cell=${encodeURIComponent(`${sheet}!${range}`)}`);
      }}
      onReviewFix={(proposalId) => {
        open(ov.SHL10(proposalId));
      }}
      onInstruct={(issueId) => {
        open(ov.SHL15(issueId));
      }}
      onAssign={(issue: WorkbookReturnIssueOut, o: WorkbookIssueAssigneeOptionOut) => {
        assign.mutate({
          path: { issue_id: issue.id },
          body: {
            seen_version: issue.version ?? 0,
            ...(o.kind === "agent"
              ? { assignee_agent: true, assignee_user_id: null }
              : { assignee_agent: false, assignee_user_id: o.id ?? null }),
          },
          headers: key(),
        });
      }}
      onSendToClient={(issue) => {
        const contact = detail.data?.client_contact?.contact_id;
        if (contact === undefined) return;
        send.mutate({
          path: { ...path, issue_id: issue.id },
          body: { seen_version: issue.version ?? 0, contact_id: contact },
          headers: key(),
        });
      }}
      onRemind={(issue) => {
        remind.mutate({ path: { ...path, issue_id: issue.id }, headers: key() });
      }}
      onResolve={(issue, note) => {
        resolve.mutate({
          path: { ...path, issue_id: issue.id },
          body: { seen_version: issue.version ?? 0, ...(note ? { note } : {}) },
        });
      }}
    />
  );
}
