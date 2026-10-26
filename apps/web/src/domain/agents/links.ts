// The WB-09 overlay key and its shareable link (P-09-T10: Copy link).

export const RUN_TRACE_OVERLAY = "run-trace";

/** This page with the run's trace open as its drawer. */
export function traceLink(runId: string, href: string): string {
  const url = new URL(href);
  url.searchParams.delete("ov");
  url.searchParams.append("ov", `${RUN_TRACE_OVERLAY}:${runId}`);
  return url.toString();
}
