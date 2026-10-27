// POR-20 Transactional email templates: one fixture scenario per artboard (R-01-T25; R-01 §5.4;
// docs/screens/POR-20.md "States"). Grace Holloway (Firm Admin) at E0, Mon Sep 14, 2026, 9:24 AM
// CT, with `portal.settings_editor` on for Brightwater Hale:
//
//   a  `reminder`: v3 published, the v4 draft saved; preview at 600 for Claire Feld
//   b  data of a; the editor opened by clicking the body (a step, not a prop)
//   c  data of a at 390;  d  data of a in the phone frame
//   e–i  `invitation` v3, `signature_request` v2, `deliverable_ready` v2,
//        `confirmation_request` v1, `reconnect_request` v1, each previewed for its sample
//   j  data of a; "Send test…" opened (a step)
//   k  data of a at 9:26 AM; the test send's toast (a step)
//   l  at 9:27 AM: v4 published by Grace, no draft

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { emailTemplateHandlers } from "../handlers/email-templates";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { PUBLISHED_V4_AT, SAMPLE_RECIPIENTS, templateSeed } from "../seed/email-templates";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const AT_926 = "2026-09-14T09:26:00-05:00";
const AT_927 = "2026-09-14T09:27:00-05:00";

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "grace-holloway");
  return { ...base, flags: { ...base.flags, "portal.settings_editor": true } };
}

type Setup = Parameters<typeof emailTemplateHandlers>[0]["states"];

const DRAFTED: Setup = { reminder: { published: 3, draft: true } };
const PUBLISHED_V4: Setup = {
  reminder: { published: 4, draft: false, publishedAt: PUBLISHED_V4_AT },
};

function at(state: string, setup: Setup, clock: string = DEMO_INSTANT) {
  return {
    state,
    persona: "grace-holloway",
    clock,
    handlers: {
      ...E0.handlers,
      ...emailTemplateHandlers({ ...(setup === undefined ? {} : { states: setup }), now: clock }),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", DRAFTED),
  b: at("b", DRAFTED),
  c: at("c", DRAFTED),
  d: at("d", DRAFTED),
  e: at("e", DRAFTED),
  f: at("f", DRAFTED),
  g: at("g", DRAFTED),
  h: at("h", DRAFTED),
  i: at("i", DRAFTED),
  j: at("j", DRAFTED),
  k: at("k", DRAFTED, AT_926),
  l: at("l", PUBLISHED_V4, AT_927),
});

export type Por20State = keyof typeof scenarios;

export interface Por20Opens {
  templateKey: string;
  w: "600" | "390" | "phone";
  sample: string;
}

const sampleOf = (key: string): string => templateSeed(key)?.sample.id ?? "";

/** The template, width and sample each state opens with. */
export const OPENS: Record<Por20State, Por20Opens> = {
  a: { templateKey: "reminder", w: "600", sample: sampleOf("reminder") },
  b: { templateKey: "reminder", w: "600", sample: sampleOf("reminder") },
  c: { templateKey: "reminder", w: "390", sample: sampleOf("reminder") },
  d: { templateKey: "reminder", w: "phone", sample: sampleOf("reminder") },
  e: { templateKey: "invitation", w: "600", sample: sampleOf("invitation") },
  f: { templateKey: "signature_request", w: "600", sample: sampleOf("signature_request") },
  g: { templateKey: "deliverable_ready", w: "600", sample: sampleOf("deliverable_ready") },
  h: { templateKey: "confirmation_request", w: "600", sample: sampleOf("confirmation_request") },
  i: { templateKey: "reconnect_request", w: "600", sample: sampleOf("reconnect_request") },
  j: { templateKey: "reminder", w: "600", sample: sampleOf("reminder") },
  k: { templateKey: "reminder", w: "600", sample: sampleOf("reminder") },
  l: { templateKey: "reminder", w: "600", sample: sampleOf("reminder") },
};

/** The Send test sheet's sample recipients (POR-20 j), as the seed contacts render. */
export const SAMPLES = SAMPLE_RECIPIENTS.map(({ id, name, line, email }) => ({
  id,
  name,
  line,
  email,
}));
