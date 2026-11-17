// C-01-T42 (live swap 1): how a closes read becomes a C-20 view state. A 403 is the role's
// restricted notice (the matrix said no), a 404 is a closed record (outside the tenant or behind
// a wall: never revealed, INV-3), anything else is the error with Retry. A flag-off firm never
// reaches here: the shell answers it first.
import type { ViewState } from "@abacus/ui";

function statusOf(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const status = (error as { status?: unknown }).status;
  if (typeof status === "number") return status;
  const detail = (error as { detail?: unknown }).detail;
  if (detail === "not_found") return 404;
  if (detail === "forbidden") return 403;
  return null;
}

export function closeReadState(read: {
  isPending: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => unknown;
}): ViewState {
  if (read.isError) {
    const status = statusOf(read.error);
    if (status === 403) return { kind: "restricted", reason: "role" };
    if (status === 404) return { kind: "restricted", reason: "walled" };
    return {
      kind: "error",
      retry: () => {
        void read.refetch();
      },
    };
  }
  return read.isPending ? { kind: "loading" } : { kind: "ready" };
}

/** CLS-02's newest run is live while it runs or waits on a person: poll it (the SSE feed wakes it
 * sooner when `realtime.sse` is on), else stop. */
export const RUN_POLL_MS = 2_000;
export function runIsLive(status: string | undefined): boolean {
  return status === "running" || status === "needs_input" || status === "queued";
}
