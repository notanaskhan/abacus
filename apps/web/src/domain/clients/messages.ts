// Clients (P-07 §5, L3): codes the clients read model returns, in words. Never a raw code on
// screen (ADR P-36).
//
// `kind` words: "Household", "Plan sponsor", "Exempt org" and "Trust" are the handoff's type pills
// (CLI-01 spec ROWS); "Business" stands for the business kind, whose handoff pills name the
// entity's tax form ("S corporation", "C corporation", "Partnership", "Single-member LLC"), which
// `ClientRowOut` does not carry (docs/screens/CLI-01.md, Open gaps).
//
// `last_activity_event_type` words (docs/contracts/clients.md: "an audit event type the UI
// words"; the table P-07-T08 and T11 confirm): the row carries the event's type, not its actor or
// object, so the line names what happened ("Documents uploaded"), not who did it to what (the
// handoff's "Claire Feld emailed 2 forms"); see docs/screens/CLI-01.md, Open gaps. An event type
// with no words here shows the time alone.

import type { ClientKind } from "./queries";

export const KIND_WORDS: Readonly<Record<ClientKind, string>> = {
  household: "Household",
  business: "Business",
  plan_sponsor: "Plan sponsor",
  nonprofit: "Exempt org",
  trust_family: "Trust",
};

export const ACTIVITY_WORDS: Readonly<Record<string, string>> = {
  "evidence.uploaded": "Documents uploaded",
  "request_item.received": "Request received",
  "engagement.created": "Engagement created",
  "engagement.accepted": "Engagement accepted",
  "engagement.letter_recorded": "Engagement letter signed",
  "engagement.delivered": "Work delivered",
  "binder.published": "Binder published",
  "client.record_changed": "Client details updated",
};

/** The words for an activity event type, or null when the screen shows only the time. */
export function activityWords(eventType: string | null | undefined): string | null {
  if (eventType === null || eventType === undefined) return null;
  return ACTIVITY_WORDS[eventType] ?? null;
}
