import type { BeneficiariesOut } from "@abacus/api-client";
import { beneficiariesOptions } from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  ErrorState,
  Skeleton,
  count,
  pct as percent,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";

// TXT-03 live (S47, TASK-8352): GET /v1/tax/returns/{id}/beneficiaries, every figure the API's
// (code's allocation of the signed computation); the words are the handoff's TXT-03. Before a
// signed computation the empty state (e); Release K-1s… stays disabled with the server's reason
// until both 1041 steps are met; the host opens TXP-12 and the release confirm.

const HEAD = [
  "Beneficiary",
  "Distributions",
  "Share",
  "DNI carried out",
  "Box 1",
  "Box 2a",
  "Box 2b",
  "K-1 status",
] as const;
const STEP_WORDS: Record<string, string> = {
  final_approval: "Final approval",
  form_8879_f: "Form 8879-F signed by the trustee",
};

export interface Txt03LiveProps {
  returnId: string;
  onRelease?: () => void;
  onPackage?: () => void;
}

export function TXT03({ returnId, onRelease, onPackage }: Txt03LiveProps): JSX.Element {
  const query = useQuery(beneficiariesOptions({ path: { return_id: returnId } }));
  if (query.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void query.refetch();
        }}
      />
    );
  }
  if (query.data === undefined) return <Skeleton className="h-[320px]" />;
  return <Loaded data={query.data} onRelease={onRelease} onPackage={onPackage} />;
}

function Loaded({
  data,
  onRelease,
  onPackage,
}: {
  data: BeneficiariesOut;
  onRelease: (() => void) | undefined;
  onPackage: (() => void) | undefined;
}): JSX.Element {
  const fmt = useFormat();
  if (data.computation_id === null || data.rows.length === 0) {
    return (
      <div data-screen="TXT-03" data-live data-scenario="e">
        <EmptyState title="Run the trust calculation to allocate DNI to beneficiaries." />
      </div>
    );
  }
  const money = (v: string): string => count(v);
  const pct = (v: string): string => percent(v, { decimals: 1 });
  const released = data.rows.every((r) => r.package_status === "released");
  const enabled = data.release_reason === null;
  const card = data.election;
  return (
    <div data-screen="TXT-03" data-live className="flex bg-shell">
      <section aria-label="Beneficiary allocation and K-1s" className="w-[878px]">
        <header className="flex justify-between">
          <h2>Beneficiary allocation and K-1s</h2>
          <Button
            disabled={!enabled}
            {...(enabled ? {} : { title: STEP_WORDS[data.release_reason ?? ""] ?? undefined })}
            onClick={() => {
              onRelease?.();
            }}
          >
            {released ? "Resend…" : "Release K-1s…"}
          </Button>
        </header>
        <table>
          <thead>
            <tr>
              {HEAD.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.contact_id} data-beneficiary={r.name}>
                <td>{r.name}</td>
                <td>{money(r.distributions)}</td>
                <td>{pct(r.share)}</td>
                <td>{money(r.dni_allocated)}</td>
                <td>{money(r.box_1)}</td>
                <td>{money(r.box_2a)}</td>
                <td>{money(r.box_2b)}</td>
                <td data-k1-status>
                  {r.package_id === null ? (
                    "Draft K-1 · pre-release"
                  ) : (
                    <button type="button" onClick={() => onPackage?.()}>
                      {r.package_status === "released" ? "Released" : "Draft K-1 · pre-release"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {data.totals && (
              <tr>
                <td>Total</td>
                <td>{money(data.totals.distributions)}</td>
                <td>{pct(data.totals.share)}</td>
                <td>{money(data.totals.dni_allocated)}</td>
                <td>{money(data.totals.box_1)}</td>
                <td>{money(data.totals.box_2a)}</td>
                <td>{money(data.totals.box_2b)}</td>
                <td />
              </tr>
            )}
          </tbody>
        </table>
        {data.totals && (
          <p data-tie={data.totals.tie}>
            TIE-OUT: Σ DNI carried out = income distribution deduction (Form 1041 line 18) ·{" "}
            {money(data.totals.income_distribution_deduction)}
          </p>
        )}
      </section>
      <aside className="w-[488px]">
        <section aria-label="§663(b) 65-day election">
          <h3>§663(b) 65-day election</h3>
          <span data-pill>
            {card.status === "elected" && card.amount !== null && card.paid_on
              ? `Elected for TY${String(card.tax_year)} · ${money(card.amount)} paid ${fmt.date(card.paid_on)}`
              : "Not made"}
          </span>
          <p>
            Window {fmt.date(card.window_start)} – {fmt.date(card.window_end)}
            {card.closed ? " · closed" : ""}
          </p>
          {card.decision_owner_name ? <p>Decision owner — {card.decision_owner_name}</p> : null}
        </section>
        <section aria-label="Release">
          <h3>Release</h3>
          <ol>
            {data.release_steps.map((s) => (
              <li key={s.key} data-done={s.met ? "yes" : "no"}>
                {STEP_WORDS[s.key] ?? s.key}
              </li>
            ))}
            <li data-done={released ? "yes" : "no"}>Release K-1s to the portal (POR-13)</li>
          </ol>
        </section>
      </aside>
    </div>
  );
}
