import { type JSX, useEffect, useState } from "react";
import { installFixtureMode } from "../app-core/fixture-mode";
import { type FixtureParams, registerScreen } from "../gallery/fixture-mode";
import { SHL01 } from "./SHL-01";
import { STATES, type Shl01State, scenarios } from "./SHL-01/scenarios";

// The built screens as /components/screens/<ID> draws them (gallery builds only; chapter 04 §9.2).
// `?st=` picks the artboard; its scenario answers the generated client under the screen, over the
// seed, and the screen mounts once it does.

function stateOf(params: FixtureParams): Shl01State {
  return STATES.find((s) => s === params.st) ?? "a";
}

function Shl01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state = stateOf(params);
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL01 state={state} /> : null;
}

registerScreen("SHL-01", { title: "Firm app shell · toolbar and nav", Component: Shl01Artboard });
