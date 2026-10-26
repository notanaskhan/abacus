// Fixture handlers for the security-center contract v1 (G-02-T11;
// docs/contracts/security-center.md): ADM-06 as the live routes will answer it. Writes are the
// QI's (Felix Andersen): anyone else gets 403, as `security.manage` says. A longer session
// answers 422 `policy_loosening_refused`; Require SSO without a verified admin sign-in 409
// `sso_not_verified`; an incident decision by Felix waits for the partner he names, and the
// second distinct decider completes it (409 `decider_must_differ` for the same person); the
// schedule runs once both seats approve. The support switch off makes the support card say so.
// Q-02's halves (incident create, the on-demand export, retention) are their own handlers.
import type { SupportSessionOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { FELIX, MARGARET } from "../seed/governance";
import {
  type FirmExportScheduleOut,
  INCIDENTS,
  INCIDENT_005,
  INCIDENT_005_DETAIL,
  POSTURE_E0,
  SAFEGUARDS_E0,
  SCHEDULE_E0,
  SECURITY_E0,
  SESSIONS,
  type SecurityIncidentOut,
  type SecurityView,
  type SessionSignedOutOut,
  type SupportAccessOut,
  type SupportState,
  WISP_PACK,
  incidentPage,
  overview,
  stillLocked,
  supportSession,
  waitingForMargaret,
} from "../seed/security-center";

const NOT_FOUND = { detail: "not found" };
const FORBIDDEN = { detail: "forbidden" };
const QI = "felix-andersen";

export interface SecurityOptions {
  view?: SecurityView;
  /** ADM-06 d's waiting state: Felix has decided and named Margaret. */
  waiting?: boolean;
  /** The support card's session state; omitted, the Aug 17 session reads Closed. */
  support?: SupportState;
}

const isQi = (request: FixtureRequest): boolean => (request.persona ?? QI) === QI;
const bodyOf = (request: FixtureRequest): Record<string, unknown> =>
  typeof request.body === "object" && request.body !== null
    ? (request.body as Record<string, unknown>)
    : {};

export function securityCenterHandlers(
  options: SecurityOptions = {},
): Record<string, FixtureHandler> {
  const view = options.view ?? "e0";
  let incident: SecurityIncidentOut = options.waiting
    ? waitingForMargaret("close_not_reportable", SECURITY_E0)
    : INCIDENT_005;
  let schedule: FirmExportScheduleOut = SCHEDULE_E0;
  let support: SupportAccessOut = overview(view, QI).support;
  let sessions = [...SESSIONS];
  let supportSessions: SupportSessionOut[] = [supportSession(options.support ?? "closed")];

  const incidents = (): SecurityIncidentOut[] => [incident, ...INCIDENTS.slice(1)];
  return {
    "GET /v1/firm/security": ({ persona }) => json({ ...overview(view, persona), support }),
    "PUT /v1/firm/security/sign-in": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      const body = bodyOf(request);
      const current = overview(view, QI).sign_in;
      if (Number(body.session_absolute_minutes) > 720) {
        return json(
          { detail: "policy_loosening_refused", facts: { field: "session_absolute_minutes" } },
          422,
        );
      }
      if (Number(body.session_idle_minutes) > 30) {
        return json(
          { detail: "policy_loosening_refused", facts: { field: "session_idle_minutes" } },
          422,
        );
      }
      if (body.require_sso === true && !current.sso_verified) {
        return json({ detail: "sso_not_verified" }, 409);
      }
      return json({
        ...current,
        require_sso: body.require_sso === true,
        session_absolute_minutes: Number(body.session_absolute_minutes),
        session_idle_minutes: Number(body.session_idle_minutes),
        version: current.version + 1,
      });
    },
    "PUT /v1/firm/security/portal-sign-in": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      const minutes = Number(bodyOf(request).session_minutes);
      if (minutes > 480) {
        return json(
          { detail: "policy_loosening_refused", facts: { field: "session_minutes" } },
          422,
        );
      }
      const current = overview(view, QI).portal;
      return json({ ...current, session_minutes: minutes, version: current.version + 1 });
    },
    "PUT /v1/firm/security/sso-exempt-account": (request) =>
      isQi(request) ? json(overview(view, QI).sign_in) : json(FORBIDDEN, 403),
    "GET /v1/firm/security/sessions": () =>
      json({ items: sessions, next_cursor: null, total: sessions.length, total_capped: false }),
    "POST /v1/firm/security/sessions/{session_id}/sign-out": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      const found = sessions.find((s) => s.id === request.params.session_id);
      if (found === undefined) return json(NOT_FOUND, 404);
      sessions = sessions.filter((s) => s.id !== found.id);
      const body: SessionSignedOutOut = {
        session_id: found.id,
        signed_out_at: SECURITY_E0,
        signed_out_by: FELIX,
      };
      return json(body);
    },
    "GET /v1/firm/security/posture": () => json(POSTURE_E0),
    "POST /v1/firm/staff/{user_id}/unlock": (request) =>
      isQi(request) ? json(stillLocked(request.params.user_id ?? "")) : json(FORBIDDEN, 403),
    "GET /v1/firm/support-access": () => json(support),
    "PUT /v1/firm/support-access": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      support = {
        ...support,
        allow_support_requests: bodyOf(request).allow_support_requests === true,
        updated_at: SECURITY_E0,
        updated_by: FELIX,
        version: support.version + 1,
      };
      return json(support);
    },
    "GET /v1/support-sessions": () => json(supportSessions),
    "POST /v1/support-sessions/{session_id}/approve": (request) => {
      supportSessions = supportSessions.map((s) =>
        s.id === request.params.session_id ? supportSession("active") : s,
      );
      return json(supportSessions[0]);
    },
    "POST /v1/support-sessions/{session_id}/revoke": (request) => {
      supportSessions = supportSessions.map((s) =>
        s.id === request.params.session_id ? supportSession("revoked") : s,
      );
      return json(supportSessions[0]);
    },
    "GET /v1/firm/security/incidents": () => json(incidentPage(incidents())),
    "GET /v1/firm/security/incidents/{incident_id}": ({ params }) => {
      if (params.incident_id === incident.id) return json({ ...INCIDENT_005_DETAIL, ...incident });
      const found = incidents().find((i) => i.id === params.incident_id);
      return found === undefined
        ? json(NOT_FOUND, 404)
        : json({ ...found, timeline: [], reminders_on: [] });
    },
    "POST /v1/firm/security/incidents/{incident_id}/decisions": (request) => {
      if (request.params.incident_id !== incident.id) return json(NOT_FOUND, 404);
      const kind =
        bodyOf(request).kind === "start_notification"
          ? "start_notification"
          : "close_not_reportable";
      const who = request.persona ?? QI;
      const pending = incident.pending_decision;
      if (pending === null || pending === undefined) {
        if (who !== QI) return json(FORBIDDEN, 403);
        incident = waitingForMargaret(kind, SECURITY_E0);
        return json(incident);
      }
      if (who !== "margaret-okonkwo" || kind !== pending.kind) {
        return json({ detail: "decider_must_differ" }, 409);
      }
      incident = {
        ...incident,
        status: kind === "close_not_reportable" ? "closed" : "investigating",
        pending_decision: null,
        decisions: [
          pending.first,
          { kind, decided_by: MARGARET, seat: "partner", decided_at: SECURITY_E0 },
        ],
        notification_started_at: kind === "start_notification" ? SECURITY_E0 : null,
      };
      return json(incident);
    },
    "GET /v1/firm/data-exports/schedule": () => json(schedule),
    "PUT /v1/firm/data-exports/schedule": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      schedule = {
        ...schedule,
        status: "pending_approval",
        approvals: [],
        version: schedule.version + 1,
      };
      return json(schedule);
    },
    "POST /v1/firm/data-exports/schedule/approve": (request) => {
      const who = request.persona ?? QI;
      const seat = who === QI ? "security_admin" : "partner";
      const approvals = schedule.approvals ?? [];
      if (approvals.some((a) => a.seat === seat)) {
        return json({ detail: "approver_must_differ" }, 409);
      }
      const next = [...approvals, { seat, approved_by: who === QI ? FELIX : MARGARET } as const];
      schedule = {
        ...schedule,
        approvals: next,
        status: next.length === 2 ? "active" : "pending_approval",
      };
      return json(schedule);
    },
    "GET /v1/firm/safeguards": () => json(SAFEGUARDS_E0),
    "PUT /v1/firm/safeguards": (request) =>
      isQi(request) ? json(SAFEGUARDS_E0) : json(FORBIDDEN, 403),
    "PUT /v1/firm/safeguards/controls/{control_key}": (request) => {
      if (!isQi(request)) return json(FORBIDDEN, 403);
      const found = SAFEGUARDS_E0.open_controls?.find(
        (c) => c.control_key === request.params.control_key,
      );
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "POST /v1/firm/safeguards/wisp-pack": (request) =>
      isQi(request) ? json(WISP_PACK, 202) : json(FORBIDDEN, 403),
  };
}
