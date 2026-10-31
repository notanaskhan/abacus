// SHL-15's reads and writes over the generated client (P-04-T54; docs/contracts/review-grammar.md
// §issues): one issue's detail, the open issues on a record (for "Issue 3 of 4", the class counts
// and the Issues count), and the person's writes: create, send to the client (only the client
// wording, with an Idempotency-Key, P-06 through the issues service), set fix instructions on one
// issue or several, and ask for an explanation. Nothing here resolves, approves or edits a value:
// every fix ends in a proposal a person accepts in SHL-10 (DF-13, INV-1).

import type {
  BulkFixInstructionsOut,
  FixInstructionsAcceptedOut,
  IssueCreateIn,
  IssueDetailOut,
  IssueItemOut,
} from "@abacus/api-client";
import {
  fixInstructionsBulkMutation,
  fixInstructionsMutation,
  issueCreateMutation,
  issueExplainMutation,
  issueListOptions,
  issueListQueryKey,
  issueOptions,
  issueQueryKey,
  issueSendToClientMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

export type IssueKind = IssueItemOut["kind"];
export type FixScope = "this_issue" | "all_of_class";

export function useIssue(issueId: string, enabled = true) {
  return useQuery({ ...issueOptions({ path: { issue_id: issueId } }), enabled });
}

/** Several issues' details, in order (SHL-15 e lists the picked issues by title). */
export function useIssues(issueIds: readonly string[]) {
  return useQueries({
    queries: issueIds.map((issueId) => issueOptions({ path: { issue_id: issueId } })),
  });
}

/** The open issues on a record, in the queue's order. */
export function useRecordIssues(record: { type: string; id: string } | null) {
  return useQuery({
    ...issueListOptions({
      query: { record_type: record?.type ?? "", record_id: record?.id ?? "", status: "open" },
    }),
    enabled: record !== null,
  });
}

export interface IssueWrites {
  create: (body: IssueCreateIn) => Promise<IssueDetailOut>;
  /** Only the client wording and the contact go to the client (INV-4); one request per call. */
  sendToClient: (
    issue: IssueDetailOut,
    wording: string,
    contactId: string,
  ) => Promise<IssueDetailOut>;
  setFix: (
    issue: IssueItemOut,
    text: string,
    scope: FixScope,
  ) => Promise<FixInstructionsAcceptedOut>;
  setFixBulk: (issues: readonly IssueItemOut[], text: string) => Promise<BulkFixInstructionsOut>;
  explain: (issue: IssueItemOut) => Promise<unknown>;
}

export function useIssueWrites(): IssueWrites {
  const queryClient = useQueryClient();
  const refresh = (issueId?: string): void => {
    void queryClient.invalidateQueries({ queryKey: issueListQueryKey() });
    if (issueId !== undefined) {
      void queryClient.invalidateQueries({
        queryKey: issueQueryKey({ path: { issue_id: issueId } }),
      });
    }
  };
  const create = useMutation({ ...issueCreateMutation() });
  const send = useMutation({ ...issueSendToClientMutation() });
  const fix = useMutation({ ...fixInstructionsMutation() });
  const bulk = useMutation({ ...fixInstructionsBulkMutation() });
  const explain = useMutation({ ...issueExplainMutation() });
  return {
    create: async (body) => {
      const out = await create.mutateAsync({ body });
      refresh();
      return out;
    },
    sendToClient: async (issue, wording, contactId) => {
      const out = await send.mutateAsync({
        path: { issue_id: issue.issue.id },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          seen_version: issue.issue.version,
          client_wording: wording,
          contact_id: contactId,
        },
      });
      refresh(issue.issue.id);
      return out;
    },
    setFix: async (issue, text, scope) => {
      const out = await fix.mutateAsync({
        path: { issue_id: issue.id },
        body: { seen_version: issue.version, text, scope },
      });
      refresh(issue.id);
      return out;
    },
    setFixBulk: async (issues, text) => {
      const out = await bulk.mutateAsync({
        body: { issues: issues.map((i) => ({ issue_id: i.id, seen_version: i.version })), text },
      });
      refresh();
      return out;
    },
    explain: async (issue) => {
      const out = await explain.mutateAsync({ path: { issue_id: issue.id } });
      refresh(issue.id);
      return out;
    },
  };
}
