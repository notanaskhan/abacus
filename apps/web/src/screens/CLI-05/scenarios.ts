// CLI-05 a–g (T-01-T09 scenarios; T-01-T14 builds d and f, T-01-T34 b, c, e and g): one scenario
// per artboard, the taxpayer entity it opens on and the section it opens at.
import { ENTITY, SECTION, scenarios } from "../../fixtures/scenarios/CLI-05";

export { ENTITY, SECTION, scenarios };

export type Cli05State = keyof typeof scenarios;

export const STATES = Object.keys(scenarios) as Cli05State[];

// T-01-T50: the agent's note on CLI-05 a is fixture-only (T-01 §3.6: no agent writes the note in
// production; the arithmetic is shown only in the fixture's agent block). The gallery and the
// scenario tests hand it to the screen; the routed page never does.
export const AGENT_NOTE = {
  text: "Both 1099-INT forms appear on the IRS transcript and not on the 2024 return. Their total, 3,120.00, matches the CP2000’s unreported interest. At the 22% bracket, 3,120.00 × 22% = 686.40, the tax the notice proposes; interest 66.61 (figured to the notice date, Aug 24, 2026; it keeps accruing until paid), so the amount due is 753.01; no penalty proposed. The notice looks correct.",
  sources: [
    "IRS CP2000 · Aug 24, 2026 · 2 citations",
    "Wage & Income transcript TY2024 · 2 citations",
  ],
} as const;
