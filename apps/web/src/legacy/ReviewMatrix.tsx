import type { MatrixRowOut } from "@abacus/api-client";
import { meOptions, reviewMatrixOptions, teamOptions } from "@abacus/api-client/query";
import { Alert, EmptyState, Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { ReviewableNotes } from "./ReviewableNotes";
import { SignOffSquares } from "./Workpapers";

// SPEC-313 (TASK-331): the sign-off matrix. Every working paper and trial balance with its five
// levels, open notes and status, and the review gate (G5): met only when every one has L1 and
// L2 signed on its current content and no open notes. Computed by the server.

const STATUS: Record<
  MatrixRowOut["status"],
  { label: string; tone: "success" | "warning" | "danger" | "neutral" }
> = {
  not_started: { label: "Not started", tone: "neutral" },
  needs_sign_off: { label: "Needs sign-off", tone: "warning" },
  changed_after_signoff: { label: "Changed after sign-off", tone: "warning" },
  open_notes: { label: "Open notes", tone: "danger" },
  complete: { label: "Complete", tone: "success" },
};

/** "unsigned:C-100:L2" → "C-100 needs L2"; fixed templates only. */
export function blockerWord(blocker: string): string {
  const [kind, code = "", extra = ""] = blocker.split(":");
  if (kind === "nothing_to_review") return "Nothing to review yet";
  if (kind === "open_notes")
    return `${code} has ${extra} open ${extra === "1" ? "note" : "notes"}`;
  if (kind === "changed_after_signoff") return `${code} changed after sign-off`;
  if (kind === "unsigned") return `${code} needs ${extra}`;
  return "Review isn't available";
}

export function ReviewMatrix({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const matrix = useQuery({ ...reviewMatrixOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? "";
  if (matrix.isPending) return <Skeleton className="h-64" />;
  if (matrix.isError) {
    return <Alert title="Sign-offs aren't available">{errorMessage(matrix.error)}</Alert>;
  }
  const m = matrix.data;
  return (
    <div className="flex flex-col gap-3">
      <section
        aria-labelledby="matrix-heading"
        className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
          <h2 id="matrix-heading" className="text-[15px] font-medium tracking-[-0.012em]">
            Sign-offs
          </h2>
          <span className="flex-1" />
          {m.gate_met ? (
            <StatusPill tone="success">Review complete</StatusPill>
          ) : (
            <StatusPill tone="warning">{`Review open · ${String(m.blockers.length)}`}</StatusPill>
          )}
        </div>
        {!m.gate_met && m.blockers.length > 0 && (
          <ul
            aria-label="What's left"
            className="flex flex-wrap gap-x-4 gap-y-1 border-b-[0.5px] border-hair px-4 py-2 text-[12.5px] text-ink-2"
          >
            {m.blockers.slice(0, 12).map((b) => (
              <li key={b}>{blockerWord(b)}</li>
            ))}
            {m.blockers.length > 12 && (
              <li className="text-ink-3">{`and ${String(m.blockers.length - 12)} more`}</li>
            )}
          </ul>
        )}
        {m.rows.length === 0 ? (
          <EmptyState title="Nothing to sign yet">
            Working papers and the trial balance appear here once they exist.
          </EmptyState>
        ) : (
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="bg-band-hd text-ink-3">
              <tr>
                <th scope="col" className="px-4 py-1.5 text-left font-medium">
                  Ref
                </th>
                <th scope="col" className="px-2 py-1.5 text-left font-medium">
                  Title
                </th>
                <th scope="col" className="px-2 py-1.5 text-left font-medium">
                  Sign-offs
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">
                  Open notes
                </th>
                <th scope="col" className="px-4 py-1.5 text-left font-medium">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {m.rows.map((r) => (
                <tr key={r.target_id} className="border-t-[0.5px] border-hair">
                  <td className="px-4 py-1.5 font-medium tabular-nums">
                    {r.target_type === "workpaper" ? (
                      <Link
                        to="/engagements/$engagementId/workpapers/$workpaperId"
                        params={{ engagementId, workpaperId: r.target_id }}
                        className="hover:underline"
                      >
                        {r.code}
                      </Link>
                    ) : (
                      <Link
                        to="/engagements/$engagementId/trial-balance"
                        params={{ engagementId }}
                        className="hover:underline"
                      >
                        {r.code}
                      </Link>
                    )}
                  </td>
                  <td className="px-2 py-1.5">{r.title}</td>
                  <td className="px-2 py-1.5">
                    <SignOffSquares levels={r.levels} />
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{r.open_notes || ""}</td>
                  <td className="px-4 py-1.5">
                    <StatusPill tone={STATUS[r.status].tone}>{STATUS[r.status].label}</StatusPill>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section aria-labelledby="notes-heading" className="rounded-pane bg-card p-4 shadow-e2">
        <h2 id="notes-heading" className="mb-2 text-[15px] font-medium tracking-[-0.012em]">
          Review notes
        </h2>
        <ReviewableNotes engagementId={engagementId} role={role} />
      </section>
    </div>
  );
}
