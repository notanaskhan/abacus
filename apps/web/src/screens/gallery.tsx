import { AppShell } from "@abacus/ui";
import { type JSX, useEffect, useState } from "react";
import { installFixtureMode } from "../app-core/fixture-mode";
import { useSession } from "../app-core/session";
import { type FixtureParams, registerScreen } from "../gallery/fixture-mode";
import { useFirmToolbar } from "../shell/firm/ToolbarData";
import { BindersIndex } from "./BND-01";
import {
  STATES as BND01_STATES,
  SEARCH as BND01_SEARCH,
  SELECTED as BND01_SELECTED,
  type Bnd01State,
  scenarios as bnd01Scenarios,
} from "./BND-01/scenarios";
import { BinderPage } from "./BND-02";
import {
  STATES as BND02_STATES,
  OPENS as BND02_OPENS,
  type Bnd02State,
  scenarios as bnd02Scenarios,
} from "./BND-02/scenarios";
import { ClientsIndex } from "./CLI-01";
import {
  STATES as CLI01_STATES,
  SEARCH as CLI01_SEARCH,
  type Cli01State,
  scenarios as cli01Scenarios,
} from "./CLI-01/scenarios";
import { ClientRecordPage } from "./CLI-02";
import {
  OPENS as CLI02_OPENS,
  STATES as CLI02_STATES,
  type Cli02State,
  scenarios as cli02Scenarios,
} from "./CLI-02/scenarios";
import { EngagementRecordPage } from "./ENG-02";
import { ENG03 } from "./ENG-03";
import {
  OPENS as ENG03_OPENS,
  STATES as ENG03_STATES,
  type Eng03State,
  scenarios as eng03Scenarios,
} from "./ENG-03/scenarios";
import {
  OPENS as ENG02_OPENS,
  STATES as ENG02_STATES,
  type Eng02State,
  scenarios as eng02Scenarios,
} from "./ENG-02/scenarios";
import { PortalSignIn } from "./POR-01";
import { PortalHome } from "./POR-02";
import {
  STATES as POR02_STATES,
  type Por02State,
  scenarios as por02Scenarios,
} from "./POR-02/scenarios";
import {
  START as POR01_START,
  STATES as POR01_STATES,
  type Por01State,
  scenarios as por01Scenarios,
} from "./POR-01/scenarios";
import { SHL01 } from "./SHL-01";
import { STATES, type Shl01State, scenarios } from "./SHL-01/scenarios";
import { SHL03 } from "./SHL-03";
import { SHL04 } from "./SHL-04";
import { SHL06 } from "./SHL-06";
import { RequestComposer } from "./SHL-14";
import {
  OPENS as SHL14_OPENS,
  STATES as SHL14_STATES,
  type Shl14State,
  scenarios as shl14Scenarios,
} from "./SHL-14/scenarios";
import {
  SEARCH as SHL06_SEARCH,
  STATES as SHL06_STATES,
  type Shl06State,
  scenarios as shl06Scenarios,
} from "./SHL-06/scenarios";
import {
  STATES as SHL04_STATES,
  type Shl04State,
  scenarios as shl04Scenarios,
} from "./SHL-04/scenarios";
import {
  STATES as SHL03_STATES,
  type Shl03State,
  scenarios as shl03Scenarios,
} from "./SHL-03/scenarios";

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

function Shl03Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl03State = SHL03_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl03Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL03 state={state} /> : null;
}

registerScreen("SHL-03", { title: "Firm switcher & profile menu", Component: Shl03Artboard });

function Shl04Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl04State = SHL04_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl04Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL04 state={state} /> : null;
}

registerScreen("SHL-04", { title: "Notifications panel", Component: Shl04Artboard });

function Bnd01Frame({ state }: { state: Bnd01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/binders" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <BindersIndex
          initial={BND01_SEARCH[state]}
          initialSelected={BND01_SELECTED[state] ?? null}
        />
      </AppShell>
    </div>
  );
}

function Bnd01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Bnd01State = BND01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      bnd01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Bnd01Frame key={state} state={state} /> : null;
}

registerScreen("BND-01", { title: "Binders index", Component: Bnd01Artboard });

function Bnd02Frame({ state }: { state: Bnd02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/binders" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <BinderPage
        binderId={BND02_OPENS[state].binderId}
        initialRequest={BND02_OPENS[state].request}
        toolbar={bar.toolbar}
        frame
      />
    </div>
  );
}

function Bnd02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Bnd02State = BND02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      bnd02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Bnd02Frame key={state} state={state} /> : null;
}

registerScreen("BND-02", { title: "Binder builder & tracker", Component: Bnd02Artboard });

function Cli01Frame({ state }: { state: Cli01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/clients" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <ClientsIndex initial={CLI01_SEARCH[state]} />
      </AppShell>
    </div>
  );
}

function Cli01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli01State = CLI01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Cli01Frame key={state} state={state} /> : null;
}

registerScreen("CLI-01", { title: "Clients index", Component: Cli01Artboard });

function Cli02Frame({ state }: { state: Cli02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/clients" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  // a2 is a with the rail scrolled to its Client Portal and Links bands.
  useEffect(() => {
    if (state !== "a2") return undefined;
    const timer = window.setInterval(() => {
      const body = document.querySelector<HTMLElement>(
        `[data-artboard='a2'] [data-cockpit='rail'] .overflow-auto`,
      );
      if (body !== null && body.scrollHeight > body.clientHeight) {
        body.scrollTop = body.scrollHeight;
        window.clearInterval(timer);
      }
    }, 50);
    return () => {
      window.clearInterval(timer);
    };
  }, [state]);
  return (
    <div data-artboard={state}>
      <ClientRecordPage clientId={CLI02_OPENS[state]} toolbar={bar.toolbar} frame />
    </div>
  );
}

function Cli02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli02State = CLI02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Cli02Frame key={state} state={state} /> : null;
}

registerScreen("CLI-02", { title: "Client record · Overview", Component: Cli02Artboard });

function Eng02Frame({ state }: { state: Eng02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/engagements" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <EngagementRecordPage engagementId={ENG02_OPENS[state]} toolbar={bar.toolbar} frame />
    </div>
  );
}

function Eng02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Eng02State = ENG02_STATES.find((s) => s === params.st) ?? "b";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      eng02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Eng02Frame key={state} state={state} /> : null;
}

registerScreen("ENG-02", { title: "Engagement record", Component: Eng02Artboard });

// SHL-14 (P-06-T13): the request composer drawer, opened over an empty frame.
function Shl14Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl14State = SHL14_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl14Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  return (
    <div key={state} data-artboard={state} className="h-[900px]">
      <RequestComposer
        binderId={SHL14_OPENS[state].binderId}
        requestId={SHL14_OPENS[state].requestId}
        open
        onOpenChange={() => undefined}
      />
    </div>
  );
}

registerScreen("SHL-14", { title: "Request composer drawer", Component: Shl14Artboard });

// ENG-03 (P-07-T21): the wizard over an empty frame, on the artboard's draft.
function Eng03Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Eng03State = ENG03_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      eng03Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  return (
    <div key={state} data-artboard={state} className="h-[900px]">
      <ENG03 draftId={ENG03_OPENS[state]} />
    </div>
  );
}

registerScreen("ENG-03", { title: "New engagement wizard", Component: Eng03Artboard });

const stayOnCard = (): void => undefined;

function Shl06Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl06State = SHL06_STATES.find((s) => s === params.st) ?? "g";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl06Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  // The artboard stays on the card: the return path is never opened here.
  return ready === state ? (
    <div data-artboard={state}>
      <SHL06 key={state} search={SHL06_SEARCH[state]} onDone={stayOnCard} frame />
    </div>
  ) : null;
}

registerScreen("SHL-06", { title: "Firm sign-in · signing in", Component: Shl06Artboard });

// POR-01 (P-08-T09): the portal's sign-in card, a, b, e, f, g and the 390 layout M. The portal is
// its own entry (portal.html); the gallery draws the same screen from its fixture scenario.
function Por01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por01State = POR01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const mobile = state === "M";
  return (
    <div
      key={state}
      data-artboard={state}
      data-surface="portal"
      className={mobile ? "mx-auto h-[844px] w-[390px] overflow-hidden" : "h-[900px]"}
    >
      <PortalSignIn opening={POR01_START[state]} mobile={mobile} />
    </div>
  );
}

registerScreen("POR-01", { title: "Portal sign-in · Brightwater Hale", Component: Por01Artboard });

// POR-02 (P-08-T15): the portal home, a, b, c and f; the portal draws it from its own entry, the
// gallery from the fixture scenario.
function Por02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por02State = POR02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  return (
    <div key={state} data-artboard={state} data-surface="portal">
      <PortalHome scopeId={null} frame />
    </div>
  );
}

registerScreen("POR-02", { title: "Portal home · Feld household", Component: Por02Artboard });
