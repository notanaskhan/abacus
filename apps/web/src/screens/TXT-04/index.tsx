import type { JSX } from "react";
import {
  DEDUCTIONS,
  GIFTS,
  INVENTORY,
  TALLY,
  adjustedTaxableGifts,
  fmt,
  grossEstate,
  totalDeductions,
} from "./data";

// TXT-04 Gift & estate workpapers (T-07-T26; handoff TXT-04): sections A to E in fixture mode.
// Tables carry no dollar sign; every total is computed from its rows; the Illinois card never
// shows a figure (the interrelated calculation is pending); Request appraisal opens SHL-14's
// request composer for Paul Thornbury.

export const TXT04_SCENARIOS = ["a", "b", "c", "d", "e"] as const;
type Scenario = (typeof TXT04_SCENARIOS)[number];
export const APPRAISAL_HREF = "?ov=request-composer:estate-appraisal:paul-thornbury";

function Tally({ extended }: { extended: boolean }): JSX.Element {
  return (
    <div data-tally className="flex gap-[12px]">
      <span>GROSS ESTATE {fmt(TALLY.gross)}</span>
      <span>DEDUCTIONS {fmt(TALLY.deductions)}</span>
      <span>TAXABLE ESTATE {fmt(TALLY.taxable)}</span>
      <span>ADJUSTED TAXABLE GIFTS {fmt(TALLY.adjustedGifts)}</span>
      <span>APPLICABLE EXCLUSION {fmt(TALLY.exclusion)}</span>
      <span>NET ESTATE TAX —</span>
      {extended && <span data-due>Extended to May 3, 2027</span>}
    </div>
  );
}

export function EstateWorkpapers({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Scenario = (TXT04_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Scenario)
    : "a";
  return (
    <div data-screen="TXT-04" data-scenario={scenario} className="bg-shell">
      <Tally extended={scenario === "e"} />
      {(scenario === "a" || scenario === "e") && (
        <section aria-label="Asset inventory — date-of-death values">
          <header className="flex justify-between">
            <h2>Asset inventory — date-of-death values</h2>
            <a href={APPRAISAL_HREF} data-prefill="Paul Thornbury">
              Request appraisal…
            </a>
          </header>
          <table>
            <tbody>
              {INVENTORY.map((r) => (
                <tr key={r[0]}>
                  <td>{r[0]}</td>
                  <td>{r[1]}</td>
                  <td>{fmt(r[2])}</td>
                  <td>{fmt(r[3])}</td>
                  <td>{r[4] === null ? "—" : fmt(r[4])}</td>
                  <td>{r[5]}</td>
                  <td>{r[6]}</td>
                </tr>
              ))}
              <tr data-total="gross">
                <td />
                <td>Total gross estate</td>
                <td>{fmt(grossEstate())}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
      {scenario === "b" && (
        <section aria-label="Deductions">
          <table>
            <tbody>
              {DEDUCTIONS.map(([label, amount]) => (
                <tr key={label}>
                  <td>{label}</td>
                  <td>{fmt(amount)}</td>
                </tr>
              ))}
              <tr data-total="deductions">
                <td>Total</td>
                <td>{fmt(totalDeductions())}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
      {scenario === "c" && (
        <section aria-label="Computation">
          <p>Tentative tax 6,625,800 (345,800 + 40% × 15,700,000)</p>
          <p>Applicable credit 7,145,800 · Net estate tax —</p>
          <aside aria-label="Without DSUE">
            <p>credit 5,945,800 → tax 680,000</p>
          </aside>
          <aside aria-label="Illinois estate tax (Form 700)" data-illinois>
            <p>
              Required — the gross estate exceeds the Illinois exclusion amount; computed with the
              interrelated Illinois calculation · Pending
            </p>
            <span data-pill>Review point</span>
          </aside>
        </section>
      )}
      {scenario === "d" && (
        <section aria-label="Gifts (709)">
          <table>
            <tbody>
              {GIFTS.map((g) => (
                <tr key={g[0]}>
                  <td>{g[0]}</td>
                  <td>{g[1]}</td>
                  <td>{g[2]}</td>
                  <td>{fmt(g[3])}</td>
                  <td>{fmt(g[4])}</td>
                  <td>{g[3] - g[4] === 0 ? "—" : fmt(g[3] - g[4])}</td>
                </tr>
              ))}
              <tr data-total="gifts">
                <td>Adjusted taxable gifts</td>
                <td>{fmt(adjustedTaxableGifts())}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
