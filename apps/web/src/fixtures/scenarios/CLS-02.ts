// The close shell's fixture scenarios (C-01-T12): Copperleaf August with `closes.engine` on, and
// the same firm with it off (the C-20 flag-off state inside the frame).
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();

function frame(state: string, on: boolean): Scenario {
  return {
    ...E0,
    state,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/me/capabilities": ({ persona }: { persona?: string | undefined }) => {
          const base = capabilitiesFor(getSeed(), persona ?? E0.persona ?? "");
          return json({ ...base, flags: { ...base.flags, "closes.engine": on } });
        },
      };
    },
  };
}

export const scenarios = defineScenarios({
  shell: frame("shell", true),
  off: frame("off", false),
});

export type ShellState = keyof typeof scenarios;
