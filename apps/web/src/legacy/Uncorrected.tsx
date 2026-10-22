import type { UncorrectedOut } from "@abacus/api-client";
import { uncorrectedOptions } from "@abacus/api-client/query";
import { Skeleton, StatusPill } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { amount } from "./amounts";

// SPEC-311 (TASK-322): the summary of uncorrected misstatements. The passed entries, their
// aggregate and where it falls against materiality are computed by the server; whether the
// aggregate is material stays the partner's judgement, so this card states, it never concludes.

export const BAND: Record<
  NonNullable<UncorrectedOut["band"]>,
  { label: string; tone: "success" | "warning" | "danger" | "neutral" }
> = {
  clearly_trivial: { label: "Clearly trivial", tone: "neutral" },
  below_performance: { label: "Below performance materiality", tone: "success" },
  below_overall: { label: "Above performance materiality", tone: "warning" },
  above_overall: { label: "At or above overall materiality", tone: "danger" },
};

export function UncorrectedSummary({ engagementId }: { engagementId: string }): JSX.Element {
  const sum = useQuery({
    ...uncorrectedOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  if (sum.isPending) return <Skeleton className="h-28" />;
  if (sum.isError) return <></>;
  const s = sum.data;
  return (
    <section
      aria-labelledby="sum-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="sum-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Uncorrected misstatements
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">{s.entries.length}</span>
        <span className="flex-1" />
        {s.band != null && <StatusPill tone={BAND[s.band].tone}>{BAND[s.band].label}</StatusPill>}
      </div>
      {s.entries.length === 0 ? (
        <p className="px-4 py-3 text-[13px] text-ink-3">
          No passed entries. An entry the client declines is listed here.
        </p>
      ) : (
        <table className="w-full border-collapse text-[12.5px]">
          <tbody>
            {s.entries.map((e) => (
              <tr key={e.id} className="border-t-[0.5px] border-hair first:border-t-0">
                <td className="px-4 py-1.5 font-medium tabular-nums">{e.ref}</td>
                <td className="px-2 py-1.5">{e.description}</td>
                <td className="px-2 py-1.5 text-ink-3 tabular-nums">{e.accounts.join(", ")}</td>
                <td className="px-4 py-1.5 text-right tabular-nums">{amount(e.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-[0.5px] border-hair font-medium">
              <td className="px-4 py-1.5" colSpan={3}>
                Aggregate
              </td>
              <td className="px-4 py-1.5 text-right tabular-nums">{amount(s.aggregate)}</td>
            </tr>
          </tfoot>
        </table>
      )}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 border-t-[0.5px] border-hair px-4 py-2.5 text-[12.5px] sm:grid-cols-4">
        {s.overall == null ? (
          <div className="col-span-full text-ink-3">
            Materiality isn't set yet; the aggregate is compared once it is.
          </div>
        ) : (
          <>
            <div>
              <dt className="text-ink-3">
                {s.materiality_decided ? "Overall materiality" : "Overall (proposed)"}
              </dt>
              <dd className="tabular-nums">{amount(s.overall)}</dd>
            </div>
            <div>
              <dt className="text-ink-3">Performance</dt>
              <dd className="tabular-nums">{amount(s.performance)}</dd>
            </div>
            <div>
              <dt className="text-ink-3">Clearly trivial</dt>
              <dd className="tabular-nums">{amount(s.trivial)}</dd>
            </div>
            <div>
              <dt className="text-ink-3">Headroom to overall</dt>
              <dd className="tabular-nums">{amount(s.headroom)}</dd>
            </div>
          </>
        )}
      </dl>
    </section>
  );
}
