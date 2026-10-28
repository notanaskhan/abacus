// ADM-10 Portal branding & client experience: one fixture scenario per artboard (R-01-T28; R-01
// §5.4; docs/screens/ADM-10.md "States"). Grace Holloway (Firm Admin) at E0, Mon Sep 14, 2026,
// 9:24 AM CT, with `portal.settings_editor` and `communications.firm_sender_domain` on:
//
//   a  published settings, no draft; brightwaterhale.com verified; preview as Claire Feld
//   b  a draft with cadence 5 days: "Unsaved changes", Next reminder Mon, Sep 21 (Sat moved)
//   c  data of a on the phone
//   d  brightwaterhale.com Pending DNS: the records and the neutral fallback lines
//   e  data of a; the Reconnect request editor drawer open (`?ov=email-template:reconnect_request`)
//   f  b's draft published: no draft, the toast (a step)
//   g  data of a; preview as Tess Moreno (Copperleaf, an entity client: Approvals)

import type { CapabilitiesOut } from "@abacus/api-client";
import { type FixtureRequest, defineScenarios, json } from "../../app-core/fixture-mode";
import { emailTemplateHandlers } from "../handlers/email-templates";
import {
  NEUTRAL_SENDER,
  PREVIEW_CONTACTS,
  type PortalSettingsSetup,
  portalSettingsHandlers,
} from "../handlers/portal-settings";
import { seedScenario } from "../scenario";
import { getSeed } from "../seed";
import { DEMO_INSTANT } from "../seed/clock";
import { capabilitiesFor } from "../seed/shell";

const E0 = seedScenario();
const seed = getSeed();
const TESS_LAST = "2026-09-11T15:00:00Z"; // Fri Sep 11, 9:00 AM MT

function capabilities(persona: string | undefined): CapabilitiesOut {
  const base = capabilitiesFor(seed, persona ?? "grace-holloway");
  return {
    ...base,
    flags: {
      ...base.flags,
      "portal.settings_editor": true,
      "communications.firm_sender_domain": true,
    },
  };
}

function at(state: string, setup: Omit<PortalSettingsSetup, "now">) {
  const neutral = setup.domain === "pending_dns" || setup.domain === "failed";
  const templates = emailTemplateHandlers({
    states: { reminder: { published: 3, draft: true } },
    now: DEMO_INSTANT,
  });
  const preview = templates["POST /v1/firm/email-templates/{key}/preview"];
  return {
    state,
    persona: "grace-holloway",
    clock: DEMO_INSTANT,
    handlers: {
      ...E0.handlers,
      ...templates,
      ...portalSettingsHandlers({ ...setup, now: DEMO_INSTANT }),
      // d: until the domain verifies, mail goes from the neutral sender (DEC-950).
      ...(neutral && preview !== undefined
        ? {
            "POST /v1/firm/email-templates/{key}/preview": async (request: FixtureRequest) => {
              const answer = await preview(request);
              const body = (await answer.json()) as Record<string, unknown>;
              return json({ ...body, from_address: NEUTRAL_SENDER });
            },
          }
        : {}),
      "GET /v1/me/capabilities": ({ persona: who }: FixtureRequest) => json(capabilities(who)),
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a", { domain: "verified" }),
  b: at("b", { domain: "verified", draftCadence: 5 }),
  c: at("c", { domain: "verified" }),
  d: at("d", { domain: "pending_dns" }),
  e: at("e", { domain: "verified" }),
  f: at("f", { domain: "verified", draftCadence: 5 }),
  g: at("g", { domain: "verified", lastSentAt: TESS_LAST }),
});

export type Adm10State = keyof typeof scenarios;

export interface Adm10Opens {
  as: string;
  device: "desktop" | "phone";
  ov?: string;
  /** f: the screen publishes on open (a step, not a prop of the screen). */
  publish?: true;
}

const CLAIRE = PREVIEW_CONTACTS[0].id;
const TESS = PREVIEW_CONTACTS[1].id;

/** The search each state opens with. */
export const OPENS: Record<Adm10State, Adm10Opens> = {
  a: { as: CLAIRE, device: "desktop" },
  b: { as: CLAIRE, device: "desktop" },
  c: { as: CLAIRE, device: "phone" },
  d: { as: CLAIRE, device: "desktop" },
  e: { as: CLAIRE, device: "desktop", ov: "email-template:reconnect_request" },
  f: { as: CLAIRE, device: "desktop", publish: true },
  g: { as: TESS, device: "desktop" },
};

/** "Preview as": the contacts the viewer can see (DEC-20), as the seed's personas. */
export const PREVIEW_AS = PREVIEW_CONTACTS.map(({ id, name }) => ({ id, name }));
