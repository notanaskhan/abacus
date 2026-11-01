// AUD-11 Sampling (A-03-T11; A-03 §5.4; docs/screens/AUD-11.md): one fixture scenario per state
// this row builds, each the AUD-02 cockpit with Fieldwork › Sample Selection open on Northwind's
// "Participants" sample set, read through the C9 sampling stub's shapes (seed/sampling.ts):
//
//   a            marcus-delaney  Thu Sep 24, 10:15 AM  Version 2 approved by Hannah Leclerc
//   b            marcus-delaney  9:24 AM               Version 2 "Prepared · MD"; Generate disabled
//   c            marcus-delaney  9:24 AM               a's data, the generate sheet open (A-03-T15)
//   d            marcus-delaney  9:24 AM               a's data, the size edited to 20 (the board)
//   e            marcus-delaney  9:24 AM               Version 3 drawing: 8 of 25 in (A-03-T15)
//   f            simone-baptiste 10:20 AM              Granite Peak disbursements from the general
//                                                      ledger, three strata, 24 + 16 = 40 (T15)
//   picker       marcus-delaney  10:15 AM              the header picker open on two sample sets
//   off          marcus-delaney  10:15 AM              `sampling.sample_sets` off: C-20
//   not_allowed  cole-hart       10:15 AM              walled from Northwind: 404, no count
//   loading      marcus-delaney  10:15 AM              the sample set never answers
//   error        marcus-delaney  10:15 AM              the sample set answers 500
//
// They live under fixtures/ (dev and test only).

import type { CapabilitiesOut, SampleSetOut } from "@abacus/api-client";
import {
  type FixtureHandler,
  type Scenario,
  defineScenarios,
  json,
  never,
} from "../../app-core/fixture-mode";
import { auditHandlers } from "../handlers/audits";
import {
  drawingHandlers,
  generateHandlers,
  samplingHandlers,
  walledSampling,
} from "../handlers/sampling";
import { trustHandlers } from "../handlers/trust";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import {
  generateContacts,
  graniteDisbursements,
  graniteSampleSets,
  northwindParticipants,
  northwindParticipantsDraft,
  northwindParticipantsDrawing,
  northwindSampleSets,
} from "../seed/sampling";
import { capabilitiesFor } from "../seed/shell";
import { DOCUMENTS } from "../seed/trust";

const seed = getSeed();
const E0 = seedScenario();
const AT_1015 = "2026-09-24T10:15:00-05:00";
const AT_0924 = "2026-09-24T09:24:00-05:00";
const AT_1020 = "2026-09-24T10:20:00-05:00";

function capabilities(persona: string | undefined, on: boolean): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "marcus-delaney");
  return {
    ...base,
    capabilities: [...base.capabilities, "engagement.read_metadata"],
    flags: { ...base.flags, "audits.cockpit": true, "sampling.sample_sets": on },
  };
}

function frame(
  state: string,
  clock: string,
  options: {
    persona?: string;
    set?: SampleSetOut;
    on?: boolean;
    sampling?: Record<string, FixtureHandler>;
  } = {},
): Scenario {
  const set = options.set ?? northwindParticipants();
  const on = options.on ?? true;
  return {
    state,
    persona: options.persona ?? "marcus-delaney",
    clock,
    handlers: {
      ...E0.handlers,
      ...trustHandlers({ documents: DOCUMENTS, citations: [] }),
      ...auditHandlers(seed, "run"),
      "GET /v1/me/capabilities": ({ persona }) => json(capabilities(persona, on)),
      ...(options.sampling ?? samplingHandlers({ sets: northwindSampleSets(), set })),
    },
  };
}

const items = samplingHandlers({ sets: northwindSampleSets(), set: northwindParticipants() });
const drawing = northwindParticipantsDrawing();
const granite = graniteDisbursements();

export const scenarios = defineScenarios({
  a: frame("a", AT_1015),
  b: frame("b", AT_0924, { set: northwindParticipantsDraft() }),
  c: frame("c", AT_0924, {
    sampling: { ...items, ...generateHandlers(northwindParticipants(), generateContacts()) },
  }),
  d: frame("d", AT_0924),
  e: frame("e", AT_0924, {
    sampling: { ...items, ...drawingHandlers(drawing, 8) },
  }),
  f: frame("f", AT_1020, {
    persona: "simone-baptiste",
    sampling: samplingHandlers({ sets: graniteSampleSets(), set: granite }),
  }),
  picker: frame("picker", AT_1015),
  off: frame("off", AT_1015, { on: false }),
  not_allowed: frame("not_allowed", AT_1015, { persona: "cole-hart", sampling: walledSampling() }),
  loading: frame("loading", AT_1015, {
    sampling: { ...items, "GET /v1/sample-sets/{sample_set_id}": () => never() },
  }),
  error: frame("error", AT_1015, {
    sampling: {
      ...items,
      "GET /v1/sample-sets/{sample_set_id}": () => json({ detail: "internal" }, 500),
    },
  }),
});

export { GENERATE_DUE, GENERATE_TEMPLATES } from "../seed/sampling";

export type Aud11State = keyof typeof scenarios;
export const STATES = Object.keys(scenarios) as Aud11State[];
