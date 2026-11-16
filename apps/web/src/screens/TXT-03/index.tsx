import { EmptyState } from "@abacus/ui";
import type { JSX } from "react";

// TXT-03 Beneficiaries, K-1s & 65-day election (T-07-T25; handoff TXT-03): states A to E in
// fixture mode, every word and figure from the handoff (the allocation foots 160,000 + 80,000 =
// 240,000; boxes 60,000 / 180,000 / 144,000). "Release K-1s…" is enabled only when both gate
// facts hold (final approval and the trustee's 8879-F), else disabled with its reason; after
// release each beneficiary's K-1 goes to the portal (POR-13).

export const TXT03_SCENARIOS = ["a", "b", "c", "d", "e"] as const;
type Scenario = (typeof TXT03_SCENARIOS)[number];

const ROWS = [
  ["Nora Calloway", "160,000 (Jun 30 80,000 · Dec 15 80,000)", "66.7%", "160,000", "40,000", "120,000", "96,000"],
  ["Theo Calloway", "80,000 (Dec 15)", "33.3%", "80,000", "20,000", "60,000", "48,000"],
] as const; // prettier-ignore
const TOTAL = ["Total", "240,000", "100.0%", "240,000", "60,000", "180,000", "144,000"] as const;
const RELEASE_REASON =
  "Requires final approval (Daniel Reyes) and Form 8879-F signed by the trustee";
const STEPS = [
  "Final approval — Daniel Reyes (BH-TAX-02)",
  "Form 8879-F signed by Eleanor Calloway (trustee)",
  "Release K-1s to the portal (POR-13)",
] as const;

export interface Txt03Facts {
  finalApproved: boolean;
  form8879fSigned: boolean;
}

export function releaseEnabled(f: Txt03Facts): boolean {
  return f.finalApproved && f.form8879fSigned;
}

export function Beneficiaries({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Scenario = (TXT03_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Scenario)
    : "a";
  if (scenario === "e") {
    return (
      <div data-screen="TXT-03" data-scenario="e">
        <EmptyState title="Run the trust calculation to allocate DNI to beneficiaries." />
      </div>
    );
  }
  const released = scenario === "b";
  const facts: Txt03Facts = { finalApproved: released, form8879fSigned: released };
  const enabled = releaseEnabled(facts);
  return (
    <div data-screen="TXT-03" data-scenario={scenario} className="flex bg-shell">
      <section aria-label="Beneficiary allocation and K-1s" className="w-[878px]">
        <header className="flex justify-between">
          <h2>Beneficiary allocation and K-1s</h2>
          <button
            type="button"
            disabled={!enabled && !released}
            title={enabled ? undefined : RELEASE_REASON}
          >
            {released ? "Resend…" : "Release K-1s…"}
          </button>
        </header>
        <table>
          <thead>
            <tr>
              {[
                "Beneficiary",
                "Distributions",
                "Share",
                "DNI carried out",
                "Box 1",
                "Box 2a",
                "Box 2b",
                "K-1 status",
              ].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r[0]} data-beneficiary={r[0]}>
                {r.map((c, i) => (
                  <td key={i}>{c}</td>
                ))}
                <td data-k1-status>{released ? "Released Sep 28" : "Draft K-1 · pre-release"}</td>
              </tr>
            ))}
            <tr>
              {TOTAL.map((c, i) => (
                <td key={i}>{c}</td>
              ))}
              <td />
            </tr>
          </tbody>
        </table>
        <p>
          TIE-OUT: Σ DNI carried out = income distribution deduction (Form 1041 line 18) · 240,000
        </p>
      </section>
      <aside className="w-[488px]">
        <section aria-label="§663(b) 65-day election">
          <h3>§663(b) 65-day election</h3>
          <span data-pill>
            {scenario === "c" ? "Elected for TY2026 · 50,000 paid Feb 20, 2027" : "Not made"}
          </span>
          {scenario === "c" && <p>Treated as paid on Dec 31, 2026 on the 2026 Form 1041</p>}
          <p>Decision owner — Eleanor Calloway (trustee)</p>
        </section>
        <section aria-label="Release">
          <h3>Release</h3>
          <ol>
            {STEPS.map((s, i) => (
              <li key={s} data-done={released || (i === 0 && facts.finalApproved) ? "yes" : "no"}>
                {s}
              </li>
            ))}
          </ol>
          <p className="text-[11.5px] text-ink-3">Return due Sep 30, 2026 (extended).</p>
        </section>
        {scenario === "d" && (
          <section role="dialog" aria-label="Ask the trustee">
            <p>
              Would you like to make additional distributions to Nora or Theo before Mar 6, 2027?
            </p>
            <button type="button">Send</button>
          </section>
        )}
      </aside>
    </div>
  );
}
