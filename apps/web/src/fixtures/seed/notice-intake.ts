// NOT-01 b, c and d (N-04-T09; the handoff spec): Aurelio Santos's photographed CP14, uploaded
// through the portal on Sep 10, 2:11 PM, read by the agent. b ready, c still reading two pages, d
// "Respond by" read at 71% ("date partly obscured"). The TIN comes back as its last four only.
// Dev and test only.

import type { IntakeFieldOut, IntakeOut } from "@abacus/api-client";
import { stableId } from "./prng";

export const SANTOS_INTAKE = stableId("not01:intake:santos");
export const SANTOS_ENTITY = stableId("client-entity:aurelio-santos");
export const SANTOS_NOTICE = stableId("notice:santos-cp14");
export const SANTOS_ENGAGEMENT = stableId("engagement:santos-notice");
export const DANIEL = stableId("person:daniel-reyes");

export type IntakeVariant = "b" | "c" | "d";

function field(
  key: IntakeFieldOut["key"],
  value: string | null,
  confidence: string,
  over: Partial<IntakeFieldOut> = {},
): IntakeFieldOut {
  return {
    key,
    value_text: value,
    confidence,
    low_confidence: Number(confidence) < 0.95,
    confirmed: false,
    origin: "agent",
    ...over,
  };
}

function fields(variant: IntakeVariant): IntakeFieldOut[] {
  return [
    field("agency.name", "IRS", "0.99"),
    field("notice.code", "CP14 · Balance due", "0.99"),
    field("notice.tax_year", "2024", "0.98"),
    field("notice.form", "1040", "0.98"),
    field("notice.date", "Sep 10, 2026", "0.97"),
    variant === "d"
      ? field("notice.respond_by", "Oct 1, 2026 (21 days)", "0.71", {
          note: "date partly obscured",
          helper: "Check page 1, top right",
        })
      : field("notice.respond_by", "Oct 1, 2026 (21 days)", "0.97"),
    field("notice.amount_total", "$1,106.00", "0.98"),
    field("taxpayer.name", "Aurelio Santos", "0.96"),
    field("taxpayer.tin", null, "0.96", {
      tin: { kind: "ssn", last4: "6602", presence: "on_file" },
    }),
  ];
}

export function santosIntake(variant: IntakeVariant, version = 1): IntakeOut {
  const extracting = variant === "c";
  return {
    id: SANTOS_INTAKE,
    status: extracting ? "extracting" : "ready",
    source: "portal",
    extraction_mode: "agent",
    file_name: "Santos_IRS_letter.jpg",
    pages: 2,
    uploaded_by_label:
      "Uploaded by Aurelio Santos · portal · Upload something else · Sep 10, 2:11 PM",
    fields: extracting ? [] : fields(variant),
    match: {
      client_entity_id: SANTOS_ENTITY,
      client_name: "Aurelio Santos",
      method: "name_tin",
      office: "Chicago",
      return_id: stableId("return:santos-2024"),
      return_label: "TY2024 Form 1040 · Accepted",
      candidates: [{ client_entity_id: SANTOS_ENTITY, name: "Aurelio Santos", tin: null }],
    },
    authorization: {
      kind: "none",
      label:
        "No Form 8821 or 2848 on file. We can analyze the client's copy, but we cannot contact the IRS for him.",
      on_file: false,
      can_represent: false,
    },
    assignee_user_id: null,
    notify_user_ids: [DANIEL],
    duplicate_of: null,
    created_work_item_id: null,
    manual_reason: null,
    version,
  };
}
