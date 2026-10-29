import { publishPortalSettings } from "@abacus/api-client";
import { AppShell, toast } from "@abacus/ui";
import { type JSX, useEffect, useState } from "react";
import { installFixtureMode } from "../app-core/fixture-mode";
import { useSession } from "../app-core/session";
import { type FixtureParams, registerScreen } from "../gallery/fixture-mode";
import { useFirmToolbar } from "../shell/firm/ToolbarData";
import { ADM01 } from "./ADM-01";
import { FilesPage } from "./FIL-01";
import {
  FIL01_STATES,
  type Fil01State,
  OPENS as FIL01_OPENS,
  REVEALED_TIN,
  scenarios as fil01Scenarios,
} from "../fixtures/scenarios/FIL-01";
import {
  type Adm01State,
  STATES as ADM01_STATES,
  scenarios as adm01Scenarios,
} from "./ADM-01/scenarios";
import { PeoplePage } from "./ADM-02";
import {
  type Adm02State,
  STATES as ADM02_STATES,
  OPENS as ADM02_OPENS,
  scenarios as adm02Scenarios,
} from "./ADM-02/scenarios";
import { OfficesPage } from "./ADM-03";
import {
  type Adm03State,
  STATES as ADM03_STATES,
  OPENS as ADM03_OPENS,
  scenarios as adm03Scenarios,
} from "./ADM-03/scenarios";
import { ADM04 } from "./ADM-04";
import {
  type Adm04State,
  STATES as ADM04_STATES,
  OPENS as ADM04_OPENS,
  scenarios as adm04Scenarios,
} from "./ADM-04/scenarios";
import { ADM06 } from "./ADM-06";
import {
  type Adm06State,
  STATES as ADM06_STATES,
  ENTERPRISE as ADM06_ENTERPRISE,
  OPENS as ADM06_OPENS,
  scenarios as adm06Scenarios,
} from "./ADM-06/scenarios";
import { ADM05 } from "./ADM-05";
import { CLI05 } from "./CLI-05";
import {
  type Cli05State,
  ENTITY as CLI05_ENTITY,
  STATES as CLI05_STATES,
  scenarios as cli05Scenarios,
} from "./CLI-05/scenarios";
import {
  type Adm05State,
  STATES as ADM05_STATES,
  OPENS as ADM05_OPENS,
  scenarios as adm05Scenarios,
} from "./ADM-05/scenarios";
import { ADM07 } from "./ADM-07";
import { ADM10 } from "./ADM-10";
import {
  type Adm10State,
  STATES as ADM10_STATES,
  OPENS as ADM10_OPENS,
  PREVIEW_AS as ADM10_PREVIEW_AS,
  scenarios as adm10Scenarios,
} from "./ADM-10/scenarios";
import { SIG01 } from "./SIG-01";
import {
  OPENS as SIG01_OPENS,
  STATES as SIG01_STATES,
  type Sig01State,
  scenarios as sig01Scenarios,
} from "./SIG-01/scenarios";
import { INB01 } from "./INB-01";
import { INB02 } from "./INB-02";
import { COPY as INB02_COPY } from "./INB-02/copy";
import {
  type Inb02State,
  STATES as INB02_STATES,
  messageOf as inb02MessageOf,
  scenarios as inb02Scenarios,
} from "./INB-02/scenarios";
import {
  OPENS as INB01_OPENS,
  STATES as INB01_STATES,
  type Inb01State,
  scenarios as inb01Scenarios,
} from "./INB-01/scenarios";
import {
  type Adm07State,
  STATES as ADM07_STATES,
  OPENS as ADM07_OPENS,
  scenarios as adm07Scenarios,
} from "./ADM-07/scenarios";
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
import { AcceptancePage } from "./CLI-07";
import {
  type Cli07State,
  NOTES as CLI07_NOTES,
  OPENS as CLI07_OPENS,
  STATES as CLI07_STATES,
  scenarios as cli07Scenarios,
} from "./CLI-07/scenarios";
import { IntakePage } from "./CLI-06";
import {
  type Cli06State,
  DRAFT_ID as CLI06_DRAFT,
  OPENS as CLI06_OPENS,
  STATES as CLI06_STATES,
  scenarios as cli06Scenarios,
} from "./CLI-06/scenarios";
import { IndependencePage } from "./CLI-08";
import {
  CHECK_ID as CLI08_CHECK,
  CLIENT_ID as CLI08_CLIENT,
  type Cli08State,
  ENGAGEMENT_ID as CLI08_ENGAGEMENT,
  OPENS as CLI08_OPENS,
  STATES as CLI08_STATES,
  scenarios as cli08Scenarios,
} from "./CLI-08/scenarios";
import { HOME01 } from "./HOME-01";
import {
  type Home01State,
  OFFICE as HOME01_OFFICE,
  STATES as HOME01_STATES,
  scenarios as home01Scenarios,
} from "./HOME-01/scenarios";
import { KNW01 } from "./KNW-01";
import {
  type Knw01State,
  OPENS as KNW01_OPENS,
  STATES as KNW01_STATES,
  scenarios as knw01Scenarios,
} from "./KNW-01/scenarios";
import { AuditsIndex } from "./AUD-01";
import {
  STATES as AUD01_STATES,
  SEARCH as AUD01_SEARCH,
  type Aud01State,
  scenarios as aud01Scenarios,
} from "./AUD-01/scenarios";
import { AuditCockpitPage } from "./AUD-02";
import {
  AUDIT_ID as AUD02_AUDIT_ID,
  OPENS as AUD02_OPENS,
  STATES as AUD02_STATES,
  type Aud02State,
  scenarios as aud02Scenarios,
} from "./AUD-02/scenarios";
import { SourceDocumentsPage } from "./AUD-03";
import {
  AUDIT_ID as AUD03_AUDIT_ID,
  OPENS as AUD03_OPENS,
  STATES as AUD03_STATES,
  type Aud03State,
  scenarios as aud03Scenarios,
} from "./AUD-03/scenarios";
import { AUD06Frame } from "./AUD-06/artboard";
import {
  STATES as AUD06_STATES,
  type Aud06State,
  scenarios as aud06Scenarios,
} from "./AUD-06/scenarios";
import {
  OPENS as CLI04_OPENS,
  OVERLAYS as CLI04_OVERLAYS,
  STATES as CLI04_STATES,
  type Cli04State,
  scenarios as cli04Scenarios,
} from "./CLI-04/scenarios";
import { EngagementsIndex } from "./ENG-01";
import {
  STATES as ENG01_STATES,
  SEARCH as ENG01_SEARCH,
  type Eng01State,
  scenarios as eng01Scenarios,
} from "./ENG-01/scenarios";
import { EngagementRecordPage } from "./ENG-02";
import { ENG03 } from "./ENG-03";
import {
  CONSENTS as ENG03_CONSENTS,
  OPENS as ENG03_OPENS,
  STATES as ENG03_STATES,
  type Eng03State,
  scenarios as eng03Scenarios,
} from "./ENG-03/scenarios";
import {
  OPENS as ENG02_OPENS,
  STATES as ENG02_STATES,
  TABS as ENG02_TABS,
  type Eng02State,
  scenarios as eng02Scenarios,
} from "./ENG-02/scenarios";
import { ENG13 } from "./ENG-13";
import {
  type Eng13State,
  OPENS as ENG13_OPENS,
  PREVIEWS as ENG13_PREVIEWS,
  STATES as ENG13_STATES,
  STEP_OF as ENG13_STEP_OF,
  scenarios as eng13Scenarios,
} from "./ENG-13/scenarios";
import {
  OPENS as ENG05_OPENS,
  OVERLAYS as ENG05_OVERLAYS,
  STATES as ENG05_STATES,
  type Eng05State,
  scenarios as eng05Scenarios,
} from "./ENG-05/scenarios";
import { PortalSignIn } from "./POR-01";
import { PortalHome } from "./POR-02";
import { PortalDocuments } from "./POR-03";
import {
  ARTBOARD as POR03_ARTBOARD,
  STATES as POR03_STATES,
  type Por03State,
  scenarios as por03Scenarios,
} from "./POR-03/scenarios";
import { PortalRequest } from "./POR-04";
import { PortalRoom } from "./POR-14";
import { PortalConnections } from "./POR-16";
import { KNW02 } from "./KNW-02";
import { KNW04 } from "./KNW-04";
import {
  type Knw04State,
  OPENS as KNW04_OPENS,
  STATES as KNW04_STATES,
  scenarios as knw04Scenarios,
} from "./KNW-04/scenarios";
import {
  type Knw02State,
  STATES as KNW02_STATES,
  OPENS as KNW02_OPENS,
  scenarios as knw02Scenarios,
} from "./KNW-02/scenarios";
import { POR20 } from "./POR-20";
import {
  OPENS as POR20_OPENS,
  SAMPLES as POR20_SAMPLES,
  STATES as POR20_STATES,
  type Por20State,
  scenarios as por20Scenarios,
} from "./POR-20/scenarios";
import {
  ARTBOARD as POR16_ARTBOARD,
  STATES as POR16_STATES,
  type Por16State,
  scenarios as por16Scenarios,
} from "./POR-16/scenarios";
import {
  ARTBOARD as POR14_ARTBOARD,
  STATES as POR14_STATES,
  type Por14State,
  scenarios as por14Scenarios,
} from "./POR-14/scenarios";
import {
  ARTBOARD as POR04_ARTBOARD,
  STATES as POR04_STATES,
  type Por04State,
  scenarios as por04Scenarios,
} from "./POR-04/scenarios";
import {
  MOBILE_STATES as POR02_MOBILE,
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
import { SHL07 } from "./SHL-07/artboard";
import {
  STATES as SHL07_STATES,
  type Shl07State,
  scenarios as shl07Scenarios,
} from "./SHL-07/scenarios";
import { SHL08 } from "./SHL-08/artboard";
import {
  STATES as SHL08_STATES,
  type Shl08State,
  scenarios as shl08Scenarios,
} from "./SHL-08/scenarios";
import { SHL20 } from "./SHL-20/artboard";
import {
  STATES as SHL20_STATES,
  type Shl20State,
  scenarios as shl20Scenarios,
} from "./SHL-20/scenarios";
import { ApproveSheet } from "./SHL-10";
import {
  OPENS as SHL10_OPENS,
  STATES as SHL10_STATES,
  type Shl10State,
  scenarios as shl10Scenarios,
} from "./SHL-10/scenarios";
import { EnvelopeBuilder } from "./SIG-02";
import {
  OPENS as SIG02_OPENS,
  STATES as SIG02_STATES,
  type Sig02State,
  scenarios as sig02Scenarios,
} from "./SIG-02/scenarios";
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

// ADM-01 a–f (G-01-T07): the T12 frame inside the firm shell, the firm pill pressed.
function Adm01Frame({ state }: { state: Adm01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/general" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM01 />
      </AppShell>
    </div>
  );
}

function Adm01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm01State = ADM01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm01Frame key={state} state={state} /> : null;
}

registerScreen("ADM-01", { title: "Settings home & firm profile", Component: Adm01Artboard });

// ADM-02 a–g (G-01-T10): People on the T12 frame; each state opens with its search (OPENS).
function Adm02Frame({ state }: { state: Adm02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/people" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <PeoplePage initial={ADM02_OPENS[state]} />
      </AppShell>
    </div>
  );
}

function Adm02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm02State = ADM02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm02Frame key={state} state={state} /> : null;
}

registerScreen("ADM-02", { title: "Users & roles · permission matrix", Component: Adm02Artboard });

// ADM-03 a–h (G-01-T14): Offices & teams on the T12 frame; each state opens with its search.
function Adm03Frame({ state }: { state: Adm03State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/offices" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <OfficesPage initial={ADM03_OPENS[state]} />
      </AppShell>
    </div>
  );
}

function Adm03Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm03State = ADM03_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm03Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm03Frame key={state} state={state} /> : null;
}

registerScreen("ADM-03", { title: "Offices, teams, walls & offshore", Component: Adm03Artboard });

/** A state's opening search (`?export=history`) as the screen's search object. */
function searchOf(query: string): Record<string, string> {
  return Object.fromEntries(new URLSearchParams(query.replace(/^\?/, "")).entries());
}

// ADM-06 a–j (G-02-T16; G-02-T21 screen spec): Security on the T12 frame; each state opens with its
// search, and i and j pass revision R2's fixture-only rows (the route never does).
function Adm06Frame({ state }: { state: Adm06State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/security" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const [search, setSearch] = useState(() => searchOf(ADM06_OPENS[state]));
  const enterprise = ADM06_ENTERPRISE[state];
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM06
          search={search}
          onSearch={(next) => {
            setSearch({ ...next });
          }}
          {...(enterprise === undefined ? {} : { enterprise })}
        />
      </AppShell>
    </div>
  );
}

function Adm06Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm06State = ADM06_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm06Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm06Frame key={state} state={state} /> : null;
}

registerScreen("ADM-06", { title: "Security center & data residency", Component: Adm06Artboard });

// ADM-10 a–g (R-01-T28): portal settings on the T12 frame; each state opens with its preview
// contact, device and drawer. f publishes b's draft before it draws (a step, not a prop).
function Adm10Frame({ state }: { state: Adm10State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/portal" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const opens = ADM10_OPENS[state];
  const [search, setSearch] = useState<Record<string, string | undefined>>(() => ({
    as: opens.as,
    device: opens.device,
    ...(opens.ov === undefined ? {} : { ov: opens.ov }),
  }));
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM10
          search={search}
          onSearch={(next) => {
            setSearch({ ...next });
          }}
          previewAs={ADM10_PREVIEW_AS}
        />
      </AppShell>
    </div>
  );
}

function Adm10Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm10State = ADM10_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    const restore = installFixtureMode(
      adm10Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    const step =
      ADM10_OPENS[state].publish === true
        ? publishPortalSettings({ headers: { "Idempotency-Key": `adm10-${state}` } })
        : Promise.resolve();
    void step.finally(() => {
      if (live) setReady(state);
    });
    return () => {
      live = false;
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm10Frame key={state} state={state} /> : null;
}

registerScreen("ADM-10", {
  title: "Portal branding & client experience",
  Component: Adm10Artboard,
});

// ADM-07 a–g (G-02-T13; G-02-T21 screen spec): the audit log on the T12 frame; each state opens
// with its search.
function Adm07Frame({ state }: { state: Adm07State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/audit-log" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const [search, setSearch] = useState(() => searchOf(ADM07_OPENS[state]));
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM07
          search={search}
          onSearch={(next) => {
            setSearch({ ...next });
          }}
        />
      </AppShell>
    </div>
  );
}

function Adm07Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm07State = ADM07_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm07Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm07Frame key={state} state={state} /> : null;
}

registerScreen("ADM-07", { title: "Audit log explorer", Component: Adm07Artboard });

// ADM-05 a, b, f and g (T-01-T13): the consent registry on the T12 frame; each state opens with
// its search (g's three rows are checked by the walk).
function Adm05Frame({ state }: { state: Adm05State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/consents" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const [search, setSearch] = useState(() => searchOf(ADM05_OPENS[state]));
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM05
          search={search}
          onSearch={(next) => {
            setSearch({ ...next });
          }}
        />
      </AppShell>
    </div>
  );
}

function Adm05Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm05State = ADM05_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm05Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm05Frame key={state} state={state} /> : null;
}

registerScreen("ADM-05", { title: "Consent registry (§7216)", Component: Adm05Artboard });

// CLI-05 d and f (T-01-T14): the client's Tax profile cockpit on the consents section.
function Cli05Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli05State = CLI05_STATES.find((s) => s === params.st) ?? "d";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli05Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? (
    <div data-artboard={state}>
      <CLI05 key={state} frame clientEntityId={CLI05_ENTITY[state]} section="consents" />
    </div>
  ) : null;
}

registerScreen("CLI-05", {
  title: "Tax profile, authorizations & consents",
  Component: Cli05Artboard,
});

// N-02-T11: SIG-01 · Signatures hub (a–g); f's reminder and r's Import sheet with N-02-T15.
function Sig01Frame({ state }: { state: Sig01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/signatures" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const open = SIG01_OPENS[state];
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <SIG01
          initialTab={open.tab}
          initialEnvelope={open.envelope}
          initialChecked={open.checked ?? []}
          initialImport={open.importing ?? false}
        />
      </AppShell>
    </div>
  );
}

function Sig01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Sig01State = SIG01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      sig01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Sig01Frame key={state} state={state} /> : null;
}

registerScreen("SIG-01", { title: "Signatures hub & evidence drawer", Component: Sig01Artboard });

// N-01-T10: INB-01 · Inbox on T8 (a–g; DEC-830).
function Inb01Frame({ state }: { state: Inb01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/inbox" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <INB01
        frame
        toolbar={bar.toolbar}
        initialThread={INB01_OPENS[state] ?? null}
        initialClientId={state === "f" ? "00000000-0000-4000-8000-000000000f00" : null}
      />
    </div>
  );
}

function Inb01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Inb01State = INB01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      inb01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Inb01Frame key={state} state={state} /> : null;
}

registerScreen("INB-01", { title: "Inbox", Component: Inb01Artboard });

// N-01-T15: INB-02 · Attachment triage & File-to, the O3 sheet over INB-01 (a–g, a2; DEC-1062).
function Inb02Frame({ state }: { state: Inb02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/inbox" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const message = inb02MessageOf(state);
  useEffect(() => {
    if (state !== "f") return;
    toast.show({ kind: "success", text: INB02_COPY.toast(1, 1, 0, ["Kevin Osei"]) });
  }, [state]);
  return (
    <div data-artboard={state}>
      <INB01
        frame
        toolbar={bar.toolbar}
        initialThread={INB01_OPENS[state === "f" ? "d" : "a"] ?? null}
      />
      {state !== "f" && (
        <INB02
          messageId={message.id}
          subject={message.subject}
          sender={message.sender}
          startDirty={state === "a2"}
          onClose={() => undefined}
        />
      )}
    </div>
  );
}

function Inb02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Inb02State = INB02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      inb02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Inb02Frame key={state} state={state} /> : null;
}

registerScreen("INB-02", { title: "Attachment triage & File-to", Component: Inb02Artboard });

function Adm04Frame({ state }: { state: Adm04State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/settings/ai-policy" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell
        frame
        height={860}
        toolbar={{ ...bar.toolbar, active: "", firmPressed: true }}
        overlay={bar.overlay}
      >
        <ADM04 opens={ADM04_OPENS[state] ?? {}} />
      </AppShell>
    </div>
  );
}

function Adm04Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Adm04State = ADM04_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      adm04Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Adm04Frame key={state} state={state} /> : null;
}

registerScreen("ADM-04", { title: "AI policy & approval gates", Component: Adm04Artboard });

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

function Eng01Frame({ state }: { state: Eng01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/engagements" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        {/* Rows open ENG-02 in the product; the artboard keeps that control (and its keyboard path). */}
        <EngagementsIndex initial={ENG01_SEARCH[state]} onOpen={() => undefined} />
      </AppShell>
    </div>
  );
}

function Eng01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Eng01State = ENG01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      eng01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Eng01Frame key={state} state={state} /> : null;
}

registerScreen("ENG-01", { title: "Engagements index", Component: Eng01Artboard });

function Aud01Frame({ state }: { state: Aud01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/audits" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        {/* Rows open AUD-02 in the product; the artboard keeps that control. */}
        <AuditsIndex initial={AUD01_SEARCH[state]} onOpen={() => undefined} />
      </AppShell>
    </div>
  );
}

function Aud01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Aud01State = AUD01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      aud01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Aud01Frame key={state} state={state} /> : null;
}

registerScreen("AUD-01", { title: "Audits index · All Audits", Component: Aud01Artboard });

function Home01Frame({ state }: { state: Home01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/home" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <HOME01 toolbar={bar.toolbar} height={860} initialOffice={HOME01_OFFICE[state] ?? null} />
    </div>
  );
}

function Home01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Home01State = HOME01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      home01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Home01Frame key={state} state={state} /> : null;
}

registerScreen("HOME-01", { title: "Home dashboard", Component: Home01Artboard });

function Knw01Frame({ state }: { state: Knw01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/knowledge" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <KNW01 toolbar={bar.toolbar} height={860} initial={KNW01_OPENS[state]} />
    </div>
  );
}

function Knw01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Knw01State = KNW01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      knw01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Knw01Frame key={state} state={state} /> : null;
}

registerScreen("KNW-01", { title: "Knowledge library", Component: Knw01Artboard });

function Aud02Frame({ state }: { state: Aud02State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/audits" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <AuditCockpitPage
          auditId={AUD02_AUDIT_ID}
          initial={AUD02_OPENS[state]}
          onBack={() => undefined}
        />
      </AppShell>
    </div>
  );
}

function Aud02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Aud02State = AUD02_STATES.find((s) => s === params.st) ?? "b";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      aud02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Aud02Frame key={state} state={state} /> : null;
}

function Aud03Frame({ state }: { state: Aud03State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/audits" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <SourceDocumentsPage
          auditId={AUD03_AUDIT_ID}
          initial={AUD03_OPENS[state]}
          onBack={() => undefined}
        />
      </AppShell>
    </div>
  );
}

// AUD-03 a–g (A-01-T15): each artboard on its own scenario, as the routed screen draws it.
function Aud03Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Aud03State = AUD03_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      aud03Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Aud03Frame key={state} state={state} /> : null;
}

registerScreen("AUD-03", {
  title: "Source documents · PBC with viewer",
  Component: Aud03Artboard,
});

// AUD-06's fixture frames (A-02-T05): persona, clock and figures per artboard until A-02-T09 and
// A-02-T14 draw the screen on the same scenarios.
// A-02-T31: the artboard inside the app shell at 1440 × 860, as AUD-01 to AUD-03 draw theirs, so
// parity, axe and Tier D find `[data-artboard] [data-shell='app']` (DEC-832).
function Aud06Shell({ state }: { state: Aud06State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/audits" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <AUD06Frame state={state} />
      </AppShell>
    </div>
  );
}

function Aud06Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Aud06State = AUD06_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      aud06Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Aud06Shell key={state} state={state} /> : null;
}

registerScreen("AUD-06", { title: "Trial balance & leadsheets", Component: Aud06Artboard });

registerScreen("AUD-02", {
  title: "Audit cockpit · Overview, Source Documents, Agent",
  Component: Aud02Artboard,
});

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

// CLI-04 (P-07-T33): the client record on its "Contacts & access" tab, opened on the artboard's
// client and overlay.
function Cli04Frame({ state }: { state: Cli04State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/clients" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <ClientRecordPage
        clientId={CLI04_OPENS[state]}
        toolbar={bar.toolbar}
        frame
        initialTab="contacts"
        contactsOpen={CLI04_OVERLAYS[state]}
      />
    </div>
  );
}

function Cli04Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli04State = CLI04_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli04Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Cli04Frame key={state} state={state} /> : null;
}

registerScreen("CLI-04", { title: "Contacts & portal access", Component: Cli04Artboard });

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
      <EngagementRecordPage
        engagementId={ENG02_OPENS[state]}
        initialTab={ENG02_TABS[state]}
        toolbar={bar.toolbar}
        frame
      />
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

// ENG-05 (P-07-T39): Team & roles inside the ENG-02 record, on its Team tab, a–e.
function Eng05Frame({ state }: { state: Eng05State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/engagements" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <EngagementRecordPage
        engagementId={ENG05_OPENS[state]}
        initialTab="team"
        toolbar={bar.toolbar}
        frame
        teamOpen={ENG05_OVERLAYS[state]}
      />
    </div>
  );
}

function Eng05Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Eng05State = ENG05_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      eng05Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Eng05Frame key={state} state={state} /> : null;
}

registerScreen("ENG-05", { title: "Team & roles", Component: Eng05Artboard });

// CLI-07 (P-07-T46): acceptance and continuance, a–g, each on its engagement.
function Cli07Frame({ state }: { state: Cli07State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/clients" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AcceptancePage
        clientId={CLI07_OPENS[state].clientId}
        engagementId={CLI07_OPENS[state].engagementId}
        toolbar={bar.toolbar}
        frame
        note={CLI07_NOTES[state]}
      />
    </div>
  );
}

function Cli07Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli07State = CLI07_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli07Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Cli07Frame key={state} state={state} /> : null;
}

registerScreen("CLI-07", { title: "Acceptance & continuance", Component: Cli07Artboard });

// CLI-06: the single-client intake, a–f, h and i (P-07-T49), and g, the bulk import (P-07-T54).
function Cli06Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli06State = CLI06_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli06Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  const opens = CLI06_OPENS[state];
  return ready === state ? (
    // The wizard is a portal: the frame holds its height so the artboard reads as visible (as ENG-13's).
    <div data-artboard={state} key={state} className="h-[900px]">
      <IntakePage
        draftId={CLI06_DRAFT}
        step={opens.step}
        {...(opens.bulk === undefined
          ? {}
          : { mode: "bulk", importId: opens.bulk.importId, importStep: opens.bulk.step })}
        {...(opens.problems === undefined ? {} : { problems: opens.problems })}
        screened={opens.screened === true}
      />
    </div>
  ) : null;
}

registerScreen("CLI-06", { title: "New client / prospect intake", Component: Cli06Artboard });

// CLI-08 (P-07-T48): independence and conflicts, a–g and the declined-note state (DF-06).
function Cli08Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Cli08State = CLI08_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      cli08Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? (
    <div data-artboard={state} key={state}>
      <IndependencePage
        clientId={CLI08_CLIENT}
        engagementId={CLI08_ENGAGEMENT}
        tab={CLI08_OPENS[state].tab}
        checkId={CLI08_CHECK}
        sheet={CLI08_OPENS[state].sheet === true}
      />
    </div>
  ) : null;
}

registerScreen("CLI-08", { title: "Independence & conflicts", Component: Cli08Artboard });

// SHL-10 (P-04-T41): the approve-agent-output sheet, a, b, c and f, over an empty frame.
function Shl10Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl10State = SHL10_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl10Scenarios[state],
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
      <ApproveSheet
        proposalRef={SHL10_OPENS[state].ref}
        initialMode={SHL10_OPENS[state].mode}
        open
        onOpenChange={() => undefined}
      />
    </div>
  );
}

registerScreen("SHL-10", { title: "Approve agent output", Component: Shl10Artboard });

// SIG-02 (N-02-T21): the envelope builder, a, e and f, over an empty frame.
function Sig02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Sig02State = SIG02_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      sig02Scenarios[state],
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
      <EnvelopeBuilder envelopeId={SIG02_OPENS[state]} open onOpenChange={() => undefined} />
    </div>
  );
}

registerScreen("SIG-02", { title: "Envelope builder", Component: Sig02Artboard });

// SHL-14 (P-06-T13, T24): the request composer drawer, opened over an empty frame.
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

// ENG-03 (P-07-T21, T34): the wizard over an empty frame, on the artboard's draft; e's §7216
// consents card is fixture-only (DEC-345) and only the gallery passes it.
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
      <ENG03 draftId={ENG03_OPENS[state]} consents={ENG03_CONSENTS[state]} />
    </div>
  );
}

registerScreen("ENG-03", { title: "New engagement wizard", Component: Eng03Artboard });

// ENG-13 (P-07-T60): the roll-forward wizard on the artboard's draft and step; the attest and
// structure rows and the template conflicts are fixture-only (DEC-805), so only the gallery passes
// the preview.
function Eng13Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Eng13State = ENG13_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      eng13Scenarios[state],
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
      <ENG13
        sourceId={ENG13_OPENS[state].source}
        draftId={ENG13_OPENS[state].draft}
        initialStep={ENG13_STEP_OF[state]}
        preview={ENG13_PREVIEWS[state]}
      />
    </div>
  );
}

registerScreen("ENG-13", { title: "Roll forward", Component: Eng13Artboard });

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

// POR-02 (P-08-T15, T23): the portal home, a–h and the 390 layout M; the portal draws it from its
// own entry, the gallery from the fixture scenario.
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
      <PortalHome scopeId={null} frame mobile={POR02_MOBILE.has(state)} />
    </div>
  );
}

registerScreen("POR-02", { title: "Portal home · Feld household", Component: Por02Artboard });

// POR-03 (R-01-T06, T10): documents, a–i, motion (`&static=1` freezes it at the sorted frame), c2
// and the 390 layout M; each artboard is its data plus what the client is doing at that instant
// (files over the list, the drop in flight, uploads, the Ignore popover).
function Por03Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por03State = POR03_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por03Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const board = POR03_ARTBOARD[state];
  return (
    <div key={state} data-artboard={state} data-surface="portal">
      <PortalDocuments
        binderId={board.binderId}
        frame
        mobile={board.mobile === true}
        hold={{
          ...(board.uploads === undefined ? {} : { uploads: board.uploads }),
          ...(board.ignoreOpenOn === undefined ? {} : { ignoreOpenOn: board.ignoreOpenOn }),
          ...(board.dragging === undefined ? {} : { dragging: board.dragging }),
          ...(board.motion === undefined ? {} : { motion: board.motion }),
          ...(board.dropBatch === undefined ? {} : { dropBatch: board.dropBatch }),
          ...(params.static ? { still: true } : {}),
        }}
      />
    </div>
  );
}

registerScreen("POR-03", { title: "Documents · Feld 2025 Binder", Component: Por03Artboard });

// POR-04 (R-01-T12): the request sheet over POR-03, a–g; e and f are the typed question and
// decision slots (fixture only: C-01 and T-06 / T-09 wire them). `&w=390` draws the phone width.
function Por04Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por04State = POR04_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por04Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const board = POR04_ARTBOARD[state];
  return (
    <div key={state} data-artboard={state} data-surface="portal">
      <PortalRequest
        requestId={board.requestId}
        frame
        mobile={params.w === "390"}
        hold={{
          ...(board.ignoreOpen === true ? { ignoreOpen: true } : {}),
          ...(board.uploading === undefined ? {} : { uploading: board.uploading }),
          ...(board.question === undefined ? {} : { question: board.question }),
          ...(board.decision === undefined ? {} : { decision: board.decision }),
        }}
      />
    </div>
  );
}

registerScreen("POR-04", {
  title: "Request detail · ignore reason sheet",
  Component: Por04Artboard,
});

// POR-14 (R-01-T14): the third-party room, a–f, as the `ScopedRequestRoom` composition; `&w=390`
// draws the 390 page (no tab bar; wired with POR-04's in R-01-T31).
function Por14Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por14State = POR14_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por14Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const board = POR14_ARTBOARD[state];
  return (
    <div key={state} data-artboard={state} data-surface="portal">
      <PortalRoom
        frame
        mobile={params.w === "390"}
        {...(board.expanded === undefined ? {} : { expanded: board.expanded })}
      />
    </div>
  );
}

registerScreen("POR-14", {
  title: "Third-party request room · Keystone Retirement Services",
  Component: Por14Artboard,
});

// POR-16 (A-02-T18): Connections for Copperleaf, a–g; the sheet and the dialog open on b, e, f.
function Por16Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por16State = POR16_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por16Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const board = POR16_ARTBOARD[state];
  return (
    <div key={state} data-artboard={state} data-surface="portal">
      <PortalConnections
        frame
        {...(board.sheet === undefined ? {} : { sheet: board.sheet })}
        {...(board.dialog === undefined ? {} : { dialog: board.dialog })}
        onAuthorise={() => undefined}
      />
    </div>
  );
}

registerScreen("POR-16", { title: "Connections · Copperleaf", Component: Por16Artboard });

// POR-20 (R-01-T25; gallery R-01-T31): the email templates, a–l on each state's template, width
// and sample. A firm screen with a POR id: the email it previews is the client's, white-labelled.
function Por20Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Por20State = POR20_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      por20Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  const opens = POR20_OPENS[state];
  return (
    <div key={state} data-artboard={state} className="h-[900px] p-[20px]">
      {/* The 1400 × 860 window the handoff draws (without SHL-01's chrome here). */}
      <div data-window="" className="flex h-[860px] w-[1400px] flex-col bg-shell">
        <POR20
          templateKey={opens.templateKey}
          width={opens.w}
          sample={opens.sample}
          samples={POR20_SAMPLES}
        />
      </div>
    </div>
  );
}

// KNW-02 e, f (K-01-T07): the workbook slice on the T3 triad (Prepare preset), each state on its
// version and search.
function Knw02Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Knw02State = KNW02_STATES.find((s) => s === params.st) ?? "e";
  const [ready, setReady] = useState<string | null>(null);
  const [search, setSearch] = useState<Record<string, string | undefined>>({});
  useEffect(() => {
    const restore = installFixtureMode(
      knw02Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    const opens = KNW02_OPENS[state];
    setSearch(opens.ov === undefined ? {} : { ov: opens.ov });
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  if (ready !== state) return null;
  return (
    <div key={state} data-artboard={state} className="h-[900px] p-[20px]">
      <div data-window="" className="flex h-[860px] w-[1400px] flex-col bg-shell">
        <KNW02
          versionId={KNW02_OPENS[state].versionId}
          search={search}
          onSearch={(next) => {
            setSearch({ ...next });
          }}
        />
      </div>
    </div>
  );
}

registerScreen("KNW-02", {
  title: "Methodology versions & import review",
  Component: Knw02Artboard,
});

// KNW-04 a–h (K-02-T13): the T12 standards page in the firm shell (Knowledge active), each state
// on its section.
function Knw04Frame({ state }: { state: Knw04State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/knowledge/standards" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <KNW04 initial={KNW04_OPENS[state]} />
      </AppShell>
    </div>
  );
}

function Knw04Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Knw04State = KNW04_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      knw04Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Knw04Frame key={state} state={state} /> : null;
}

registerScreen("KNW-04", { title: "Firm standards & thresholds", Component: Knw04Artboard });

registerScreen("POR-20", {
  title: "Transactional email templates · Reminder",
  Component: Por20Artboard,
});

// SHL-07 (P-03-T07, T11): the citation popover on the AUD-04 and AUD-05 underlays, a–e.
function Shl07Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl07State = SHL07_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl07Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL07 key={state} state={state} /> : null;
}

registerScreen("SHL-07", { title: "Citation popover", Component: Shl07Artboard });

// SHL-08 (P-03-T07, T14): the source viewer on its two hosts, a–f and h.
function Shl08Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl08State = SHL08_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl08Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL08 key={state} state={state} /> : null;
}

registerScreen("SHL-08", { title: "Source viewer · drawer and pane", Component: Shl08Artboard });

// SHL-20 (P-06-T22): the C-34 screening card on the Granite Peak SURL upload, a–f.
function Shl20Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Shl20State = SHL20_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      shl20Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <SHL20 key={state} state={state} /> : null;
}

registerScreen("SHL-20", { title: "Evidence screening", Component: Shl20Artboard });

// FIL-01 Files browser and document drawer (N-01-T16): a to j; e, h, i and j fixture-only.
function Fil01Frame({ state }: { state: Fil01State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const bar = useFirmToolbar({
    at: { pathname: "/files" },
    firm,
    navigate: () => undefined,
    hotkeys: false,
  });
  const persona = fil01Scenarios[state].persona ?? "";
  const viewer = persona
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
  return (
    <div data-artboard={state}>
      <AppShell frame height={860} toolbar={bar.toolbar} overlay={bar.overlay}>
        <FilesPage
          node={FIL01_OPENS[state].node}
          doc={FIL01_OPENS[state].doc}
          viewer={viewer}
          reveal={() => Promise.resolve(REVEALED_TIN)}
          revealedValue={state === "f" ? REVEALED_TIN : null}
          frame
        />
      </AppShell>
    </div>
  );
}

function Fil01Artboard({ params }: { params: FixtureParams }): JSX.Element | null {
  const state: Fil01State = FIL01_STATES.find((s) => s === params.st) ?? "a";
  const [ready, setReady] = useState<string | null>(null);
  useEffect(() => {
    const restore = installFixtureMode(
      fil01Scenarios[state],
      params.as === undefined ? {} : { persona: params.as },
    );
    setReady(state);
    return () => {
      setReady(null);
      restore();
    };
  }, [state, params.as]);
  return ready === state ? <Fil01Frame key={state} state={state} /> : null;
}

registerScreen("FIL-01", { title: "Files browser & document drawer", Component: Fil01Artboard });
