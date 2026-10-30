// SHL-16 a–f (P-04-T43): one scenario per frame from the C3 stub-3 fixtures (seed/review.ts,
// P-04-T34), Samuel Ito at E0 on the Feld 2025 Form 1040. Each frame names the record, the
// checkpoint it opens and the dialog it holds.
import type { Scenario } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { SHL16 } from "../seed/review";

export const STATES = ["a", "b", "c", "d", "e", "f"] as const;
export type Shl16State = (typeof STATES)[number];

const all = reviewScenarios("SHL-16");

export const scenarios = Object.fromEntries(STATES.map((s) => [s, all[s] as Scenario])) as Record<
  Shl16State,
  Scenario
>;

export const OPENS: Record<
  Shl16State,
  { type: string; id: string; seq?: number; dialog?: "restore" | "rename" }
> = {
  a: { type: "tax_return", id: SHL16.a.target_id, seq: 6 },
  b: { type: "tax_return", id: SHL16.b.target_id, seq: 6 },
  c: { type: "tax_return", id: SHL16.a.target_id, seq: 3, dialog: "restore" },
  d: { type: "tax_return", id: SHL16.d.target_id, seq: 5, dialog: "rename" },
  e: { type: "tax_return", id: SHL16.e.target_id, seq: 6 },
  f: { type: "tax_return", id: SHL16.f.target_id },
};
