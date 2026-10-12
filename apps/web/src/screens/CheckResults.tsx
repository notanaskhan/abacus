import type { CheckOut } from "@abacus/api-client";
import { uploadChecksOptions } from "@abacus/api-client/query";
import { Alert, Badge, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { isForbidden } from "../shell/mfa";
import { checkName, crossCheckMessage, notCheckedReason, problemMessage } from "./checkMessages";

const POLL_MS = 3000;
const POLL_FOR_MS = 30_000;

type Ids = { engagementId: string; itemId: string; versionId: string };

function useChecks({ engagementId, itemId, versionId }: Ids, uploadedAt?: string) {
  const recent =
    uploadedAt !== undefined && Date.now() - new Date(uploadedAt).getTime() < POLL_FOR_MS;
  return useQuery({
    ...uploadChecksOptions({
      path: { engagement_id: engagementId, item_id: itemId, version_id: versionId },
    }),
    retry: false,
    // An empty list means "not checked yet": ask again while the upload is fresh.
    refetchInterval: (query) =>
      (query.state.data?.length ?? 0) === 0 && (recent || uploadedAt === undefined)
        ? POLL_MS
        : false,
  });
}

/** SPEC-029 AC-10 (TASK-057): a client's upload, checked within seconds, problems in plain
 * words; `replace` is the request's file picker (a new version, ADR-004). */
export function ClientUploadChecks({
  ids,
  uploadedAt,
  replace,
}: {
  ids: Ids;
  uploadedAt: string;
  replace: JSX.Element | null;
}): JSX.Element | null {
  const checks = useChecks(ids, uploadedAt);
  if (checks.isPending) return <span className="text-xs text-muted">Checking…</span>;
  if (checks.isError) return null; // the upload itself is listed; checks are a bonus here
  if (checks.data.length === 0) {
    const fresh = Date.now() - new Date(uploadedAt).getTime() < POLL_FOR_MS;
    return fresh ? <span className="text-xs text-muted">Checking…</span> : null;
  }
  const problems = checks.data
    .map((c) => problemMessage(c))
    .filter((m): m is string => m !== null);
  if (problems.length === 0) {
    return <span className="text-xs text-ok">No problems found</span>;
  }
  return (
    <div className="flex w-full flex-col gap-1">
      <ul aria-label="Problems found" className="flex flex-col gap-1">
        {problems.map((message) => (
          <li key={message} role="alert" className="text-xs text-danger">
            {message}
          </li>
        ))}
      </ul>
      {replace}
    </div>
  );
}

function outcomeBadge(check: CheckOut): JSX.Element {
  if (check.outcome === "passed") return <Badge tone="success">Passed</Badge>;
  if (check.outcome === "problem") return <Badge tone="warning">Problem</Badge>;
  return <Badge>Not checked</Badge>;
}

function detail(check: CheckOut): string {
  if (check.code === "ledger_cross_check") return crossCheckMessage(check);
  if (check.outcome === "problem") return problemMessage(check) ?? "";
  if (check.outcome === "not_applicable") return notCheckedReason(check.reason);
  return "";
}

/** SPEC-029 AC-11 (TASK-057): every check and cross-check of the version, for the firm. */
export function FirmChecksPanel({ ids }: { ids: Ids }): JSX.Element {
  const checks = useChecks(ids);
  if (checks.isPending) return <Skeleton className="h-24" />;
  if (checks.isError) {
    return isForbidden(checks.error) ? (
      <p className="text-sm text-muted">You can&apos;t see this file&apos;s checks.</p>
    ) : (
      <Alert title="Couldn't load the checks">Try again in a moment.</Alert>
    );
  }
  if (checks.data.length === 0) {
    return <p className="text-sm text-muted">Not checked yet.</p>;
  }
  return (
    <ul aria-label="Checks" className="flex flex-col gap-2 text-sm">
      {checks.data.map((check) => (
        <li key={check.code} className="flex flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-2">
            {outcomeBadge(check)}
            <span className="font-medium">{checkName(check.code)}</span>
            {check.audience === "firm" && <span className="text-xs text-muted">firm only</span>}
          </span>
          {detail(check) !== "" && <span className="text-muted">{detail(check)}</span>}
        </li>
      ))}
    </ul>
  );
}
