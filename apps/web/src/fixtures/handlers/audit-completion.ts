// A-07-T11: the completion, letters, report, release and archive reads in fixture mode, one state at a
// time, on the stub's paths. Writes stay out until each screen's task adds them.

import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  aud18,
  aud19,
  aud21,
  aud22,
  aud23,
  aud24,
  aud25,
} from "../seed/audit-completion";

const P = "/v1/audits/{work_item_id}";

export type CompletionState = {
  aud18?: Parameters<typeof aud18>[0];
  aud19?: Parameters<typeof aud19>[0];
  aud21?: Parameters<typeof aud21>[0];
  aud22?: Parameters<typeof aud22>[0];
  aud23?: Parameters<typeof aud23>[0];
  aud24?: Parameters<typeof aud24>[0];
  aud25?: Parameters<typeof aud25>[0];
};

export function completionHandlers(state: CompletionState = {}): Record<string, FixtureHandler> {
  return {
    [`GET ${P}/eqr`]: () => json(aud18(state.aud18 ?? "a")),
    [`GET ${P}/completion`]: () => json(aud19(state.aud19 ?? "a")),
    [`GET ${P}/rep-letter`]: () => json(aud21(state.aud21 ?? "a")),
    [`GET ${P}/governance-communications`]: () => json(aud22(state.aud22 ?? "a")),
    [`GET ${P}/report`]: () => json(aud23(state.aud23 ?? "a")),
    [`GET ${P}/release`]: () => json(aud24(state.aud24 ?? "a")),
    [`GET ${P}/archive`]: () => json(aud25(state.aud25 ?? "a")),
  };
}
