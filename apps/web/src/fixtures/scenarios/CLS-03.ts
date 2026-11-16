// CLS-03 Intake's fixture scenarios (C-01-T35): Copperleaf August at 9:02 AM. a Pending
// incorporation (Square selected), a2 the net total lit, a3 the return reason picker, b
// Incorporated with "Re-run affected tasks", c the requested Savings ••4436 row, d the
// questionnaire, e the tree as a drop target, f September before BD1, g the Amex row flagged, h
// screening rerunning. The handlers serve the request tree, the questionnaire, the summary and the
// Square file's text from `seed/close-intake.ts`.
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  SQUARE_VERSION,
  copperleafRequestTree,
  septemberRequestTree,
  squarePayoutText,
} from "../seed/close-intake";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function intake(state: string, tree: () => object = () => copperleafRequestTree()): Scenario {
  return {
    ...E0,
    state,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? E0.persona ?? "");
          return json({ ...base, flags: { ...base.flags, "closes.engine": true } });
        },
        "GET /v1/closes/{close_id}/requests": () => json(tree()),
        "GET /v1/evidence-versions/{version_id}/text": ({
          params,
        }: {
          params: Record<string, string>;
        }) =>
          params.version_id === SQUARE_VERSION
            ? json(squarePayoutText())
            : json({ items: [], sheets: [], truncated: false }),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: intake("a"),
  a2: intake("a2"),
  a3: intake("a3"),
  b: intake("b", () => copperleafRequestTree("b")),
  c: intake("c"),
  d: intake("d"),
  e: intake("e"),
  f: intake("f", septemberRequestTree),
  g: intake("g", () => copperleafRequestTree("g")),
  h: intake("h"),
});

export type IntakeState = keyof typeof scenarios;
