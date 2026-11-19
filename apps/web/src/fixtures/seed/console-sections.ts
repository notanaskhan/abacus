// The console's undesigned sections on fixtures (G-04-T17; DEC-5701), from facts the handoff and the
// seed already hold: Brightwater Hale's Aug 17 support session (PLT-01b history), Kessling Mott's
// pending request (PLT-01d), the CCH Axcess incident and Ines's thread with Grace (SHL-05 a), and
// Brightwater Hale's seats request (ADM-14 f: 46 → 48, partner approval Margaret Okonkwo). Publication rows are the two-person
// publish states: a version Rowan drafted (his own: Publish disabled) and one Jordan drafted.
import type {
  ConsolePublicationsOut,
  PlatformPlanRequestsOut,
  PlatformSessionsOut,
  QueueConversationDetailOut,
  QueueConversationsOut,
  StatusIncidentsOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

const BH = { tenant_code: "tnt_bh01", firm_display_name: "Brightwater Hale LLP" };
const KM = { tenant_code: "tnt_km03", firm_display_name: "Kessling Mott LLP" };

export function consoleSessions(): PlatformSessionsOut {
  return {
    counts: { requested: 1, active: 0, ended: 1 },
    items: [
      {
        ...KM,
        history: {
          session_id: stableId("support-session:km:2026-09-14"),
          status: "requested",
          scope_kind: "integration_settings",
          requested_by: "Jordan Pryce",
          approver_display_name: null,
          approver_role: null,
          started_at: null,
          closed_at: null,
          duration_minutes: 120,
          reason_fingerprint: "0".repeat(16),
        },
      },
      {
        ...BH,
        history: {
          session_id: stableId("support-session:bh:2026-08-17"),
          status: "ended",
          scope_kind: "integration_settings",
          requested_by: "Jordan Pryce",
          approver_display_name: "Felix Andersen",
          approver_role: "firm_admin",
          started_at: "2026-08-17T10:12:00-05:00",
          closed_at: "2026-08-17T11:40:00-05:00",
          duration_minutes: 88,
          reason_fingerprint: "0".repeat(16),
        },
      },
    ],
  };
}

export const STATUS_COMPONENTS = [
  "cch_axcess_export",
  "quickbooks_online_sync",
  "portal",
] as const;

export function consoleIncidents(): StatusIncidentsOut {
  return {
    counts: { open: 1, resolved: 0 },
    items: [
      {
        id: stableId("incident:cch-axcess:2026-09-14"),
        component_key: "cch_axcess_export",
        severity: "degraded",
        title: "CCH Axcess exports delayed",
        public_note:
          "CCH Axcess is accepting exports with delays of up to 15 minutes since 8:40 AM CT. Exports queue and finish on their own; nothing is lost.",
        posted_by: "Jordan Pryce",
        started_at: "2026-09-14T08:40:00-05:00",
        resolved_at: null,
        updates: [],
      },
    ],
  };
}

const GRACE_THREAD = stableId("support-conversation:bh:grace:2026-09-14");

export function consoleQueue(): QueueConversationsOut {
  return {
    counts: { unanswered: 1 },
    items: [
      {
        ...BH,
        id: GRACE_THREAD,
        owner_display_name: "Grace Holloway",
        assigned_to: "Ines",
        last_firm_message_at: "2026-09-14T09:21:00-05:00",
        last_staff_message_at: "2026-09-14T09:19:00-05:00",
        unanswered: true,
      },
    ],
  };
}

export function consoleConversation(): QueueConversationDetailOut {
  const [conversation] = consoleQueue().items;
  if (conversation === undefined) throw new Error("no conversation");
  const msg = (n: number, staff: boolean, at: string, body: string) => ({
    id: stableId(`support-message:${String(n)}`),
    author_kind: staff ? ("staff" as const) : ("firm_user" as const),
    author_display_name: staff ? "Ines" : "Grace Holloway",
    body,
    created_at: at,
    related_article_slug: null,
  });
  return {
    conversation,
    messages: [
      msg(
        1,
        false,
        "2026-09-14T09:17:00-05:00",
        "Our CCH Axcess exports are taking a long time this morning. Ridgeline's 1065 is due tomorrow.",
      ),
      msg(
        2,
        true,
        "2026-09-14T09:19:00-05:00",
        "Thanks, Grace. CCH Axcess is accepting exports with delays of up to 15 minutes since 8:40 AM CT. Exports queue and finish on their own; nothing is lost. Ridgeline's return shows 'Not yet exported', so it isn't affected yet.",
      ),
      msg(3, false, "2026-09-14T09:21:00-05:00", "Can you check Kevin's export from Friday too?"),
    ],
  };
}

export function consolePublications(): ConsolePublicationsOut {
  return {
    counts: { draft: 2 },
    items: [
      {
        id: stableId("publication:help:exporting-cch"),
        kind: "help_article",
        key: "exporting-a-return-to-cch-axcess",
        version: 2,
        status: "draft",
        drafted_by: "Rowan Achebe",
        can_publish: false,
        effective_from: null,
        rows_added: 0,
        rows_changed: 1,
        rows_removed: 0,
      },
      {
        id: stableId("publication:reference:status-components"),
        kind: "reference_set",
        key: "status_components",
        version: 1,
        status: "draft",
        drafted_by: "Jordan Pryce",
        can_publish: true,
        effective_from: null,
        rows_added: 3,
        rows_changed: 0,
        rows_removed: 0,
      },
    ],
  };
}

export function consolePlanRequests(): PlatformPlanRequestsOut {
  return {
    counts: { sent_to_accrued: 1, applied: 0 },
    items: [
      {
        ...BH,
        id: stableId("plan-request:bh:seats"),
        kind: "seats",
        from_value: 46,
        to_value: 48,
        modules_add: [],
        approved_by_display_name: "Margaret Okonkwo",
        sent_at: "2026-09-14T09:24:00-05:00",
        status: "sent_to_accrued",
        effective_from: null,
      },
    ],
  };
}
