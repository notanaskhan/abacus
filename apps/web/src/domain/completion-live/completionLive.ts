// A-07-T47 (TASK-6737; A-07 F6, F7, F11): AUD-21 to AUD-25 on the server's data, over the generated
// client only. Reads of gate, clock and envelope state poll every 10 s; while a workflow the person
// started is running (the letter's compose, the release, the lock) the read polls every 2 s until
// the server shows it done. Every mutation invalidates the completion reads, so no screen shows a
// state the server has moved past. A refusal reads in words (`refusalWords`); a stale second
// factor (`mfa_required`) opens the shell's step-up instead.

import type { AuditArchiveStateOut, AuditReleaseOut } from "@abacus/api-client";
import {
  auditArchiveLockMutation,
  auditArchiveOptions,
  auditReleaseOptions,
  auditReleasePostMutation,
} from "@abacus/api-client/query";
import {
  type QueryClient,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";
import { errorCode, needsStepUp } from "../audits/exports";

/** Gate, clock and envelope state: someone else's act (Dana's signature, a teammate's sign-off)
 * shows within 10 s (A-07-T47 acceptance). */
export const LIVE_POLL_MS = 10_000;
/** A workflow the viewer started, read until the server reports it finished. */
export const RUN_POLL_MS = 2_000;

/** The completion reads a mutation can move: invalidated together. */
export const COMPLETION_QUERIES: ReadonlySet<string> = new Set([
  "auditCockpit",
  "auditCompletion",
  "eqrReview",
  "representationLetter",
  "representationLetterVersions",
  "governanceList",
  "governance",
  "auditReport",
  "auditReportVersions",
  "auditRelease",
  "auditFilings",
  "auditArchive",
  "auditArchiveAdditions",
  "auditArchiveManifest",
]);

export function invalidateCompletion(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({
    predicate: (q) => {
      const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
      return COMPLETION_QUERIES.has(id);
    },
  });
}

/** The refusals the A-07 routes answer (docs/contracts/audit-completion.md §Refusals), in words. A
 * code with no words reads as the generic problem; the server's code is never shown raw. */
export const REFUSAL_WORDS: Readonly<Record<string, string>> = {
  archived: "This engagement is archived. Add a document after lock instead.",
  gates_not_met: "Not every gate is met yet. The gates below show what is still open.",
  content_changed: "Something changed since you opened this. Review the latest and try again.",
  mfa_required: "Confirm it's you to continue.",
  checklist_incomplete: "The archive checklist isn't complete yet.",
  checklist_changed: "The checklist changed since you opened it. Review it and try again.",
  approval_required: "The engagement partner must approve this version first.",
  ep_only: "Only the engagement partner can do this.",
  archive_locked: "The archive is already locked.",
};
export const REFUSAL_PROBLEM = "That didn't go through. Try again, or ask your firm admin.";

export function refusalWords(error: unknown): string {
  const code = errorCode(error);
  return (code === null ? undefined : REFUSAL_WORDS[code]) ?? REFUSAL_PROBLEM;
}

/** A stale or missing second factor: the shell's step-up, not a refusal message. */
export function asksForStepUp(error: unknown): boolean {
  return needsStepUp(error) || errorCode(error) === "mfa_required";
}

/** The release is running: a grant was issued, nothing released yet. */
export function releaseRunning(running: boolean, data: AuditReleaseOut | undefined): boolean {
  return running && (data === undefined || data.released_at === null);
}

/** The lock is running: the server shows `locking` (or the viewer just asked and it hasn't). */
export function lockRunning(running: boolean, data: AuditArchiveStateOut | undefined): boolean {
  if (data?.status === "locking") return true;
  return running && data?.status !== "locked";
}

function newKey(): string {
  return globalThis.crypto.randomUUID();
}

export interface LiveAction {
  run: () => Promise<void>;
  running: boolean;
  problem: string | null;
  stepUp: boolean;
  setStepUp: (open: boolean) => void;
}

/** AUD-24: the release state, polled; "Release report…" posts once per attempt with its own
 * Idempotency-Key, then the read follows ReleaseWorkflow until it records G8. */
export function useLiveRelease(workItemId: string): {
  release: UseQueryResult<AuditReleaseOut, unknown>;
  action: LiveAction;
} {
  const queryClient = useQueryClient();
  const [started, setStarted] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState(false);
  const release = useQuery({
    ...auditReleaseOptions({ path: { work_item_id: workItemId } }),
    refetchInterval: (query) =>
      releaseRunning(started, query.state.data) ? RUN_POLL_MS : LIVE_POLL_MS,
  });
  const post = useMutation({
    ...auditReleasePostMutation(),
    onSettled: () => invalidateCompletion(queryClient),
  });
  const run = async (): Promise<void> => {
    const seen = release.data?.gate_hash;
    if (seen === undefined) return;
    setProblem(null);
    try {
      await post.mutateAsync({
        path: { work_item_id: workItemId },
        body: { authorize: true, seen_gate_hash: seen },
        headers: { "Idempotency-Key": newKey() },
      });
      setStarted(true);
    } catch (error: unknown) {
      if (asksForStepUp(error)) setStepUp(true);
      else setProblem(refusalWords(error));
    }
  };
  return {
    release,
    action: {
      run,
      running: post.isPending || releaseRunning(started, release.data),
      problem,
      stepUp,
      setStepUp,
    },
  };
}

/** AUD-25: the archive state, polled; "Lock archive…" posts the checklist the person saw, then
 * the read follows ArchiveLockWorkflow until the seal is recorded. */
export function useLiveArchive(workItemId: string): {
  archive: UseQueryResult<AuditArchiveStateOut, unknown>;
  action: LiveAction & { thenRollForward: boolean; setThenRollForward: (on: boolean) => void };
} {
  const queryClient = useQueryClient();
  const [started, setStarted] = useState(false);
  const [rollForward, setRollForward] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState(false);
  const archive = useQuery({
    ...auditArchiveOptions({ path: { work_item_id: workItemId } }),
    refetchInterval: (query) =>
      lockRunning(started, query.state.data) ? RUN_POLL_MS : LIVE_POLL_MS,
  });
  const lock = useMutation({
    ...auditArchiveLockMutation(),
    onSettled: () => invalidateCompletion(queryClient),
  });
  const run = async (): Promise<void> => {
    const seen = archive.data?.checklist_hash;
    if (seen === undefined) return;
    setProblem(null);
    try {
      await lock.mutateAsync({
        path: { work_item_id: workItemId },
        body: {
          assembly_complete: true,
          seen_checklist_hash: seen,
          then_roll_forward: rollForward,
        },
        headers: { "Idempotency-Key": newKey() },
      });
      setStarted(true);
    } catch (error: unknown) {
      if (asksForStepUp(error)) setStepUp(true);
      else setProblem(refusalWords(error));
    }
  };
  return {
    archive,
    action: {
      run,
      running: lock.isPending || lockRunning(started, archive.data),
      problem,
      stepUp,
      setStepUp,
      thenRollForward: rollForward,
      setThenRollForward: setRollForward,
    },
  };
}

/** DV-6 (DF-27): "2 of 3 required sent" — the required set is the server's, per engagement type
 * (`GET /v1/audits/{id}/governance`: `required_sent`, `required_total`). */
export function governanceWords(g: { sent: number; total: number }): string {
  return `Governance Communications · ${String(g.sent)} of ${String(g.total)} required sent`;
}
