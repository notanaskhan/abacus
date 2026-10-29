// Fixture handlers over the interim seed (F-04-T05), keyed by OpenAPI path as fixture mode wants
// them (app-core/fixture-mode.ts). Every body is typed against the generated client, so a schema
// change breaks the build here. A persona (`?as=`) is a seat holder or portal user; a wall hides a
// client from its person exactly as an absent client (404 semantics, DEC-43: no hidden count).

import type {
  ClientChoiceOut,
  EngagementOut,
  EngagementSummaryOut,
  FirmClientOut,
  FirmMemberOut,
  RequestItemOut,
  SessionTokenOut,
  SignedOutOut,
  StaffListOut,
  TimeZoneIo,
  WorkItemOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../app-core/fixture-mode";
import { type Seed, getSeed, meFor } from "./seed";
import { entityIdOf } from "./seed/clients";

/** The persona a screen is seen as when `?as=` is absent: the audit-core manager of the demo. */
export const DEFAULT_PERSONA = "hannah-leclerc";

const NOT_FOUND = { detail: "not_found" };

/** What fixture mode's `POST /v1/auth/refresh` answers: an opaque word, not a token. */
export const FIXTURE_TOKEN = "fixture-session";

/** P-01-T11: the BFF's session in fixture mode. The refresh hands the shell an in-memory token
 * (an opaque fixture word, never a credential) and sign-out ends it. Kept apart from the seed's
 * read handlers; `make dev-fixtures` and the SHL-06 scenarios add them. */
export function sessionHandlers(): Record<string, FixtureHandler> {
  return {
    "POST /v1/auth/refresh": () => {
      const token: SessionTokenOut = { access_token: FIXTURE_TOKEN, expires_in: 600 };
      return json(token);
    },
    "POST /v1/auth/sign-out": () => {
      const ended: SignedOutOut = { ended: true };
      return json(ended);
    },
  };
}

function walledClients(seed: Seed, request: FixtureRequest): Set<string> {
  const who = request.persona ?? DEFAULT_PERSONA;
  return new Set(seed.walls.filter((w) => w.personSlug === who).map((w) => w.clientId));
}

export function seedHandlers(seed: Seed = getSeed()): Record<string, FixtureHandler> {
  const engagement = (request: FixtureRequest): EngagementOut | undefined => {
    const found = seed.engagements.find((e) => e.id === request.params.engagement_id);
    return found === undefined || walledClients(seed, request).has(found.client_id)
      ? undefined
      : found;
  };

  return {
    "GET /v1/me": ({ persona }) => {
      const me = meFor(seed, persona ?? DEFAULT_PERSONA);
      return me === undefined ? json({ detail: "unknown_persona" }, 404) : json(me);
    },
    "GET /v1/firm/staff": () => {
      const active = seed.staff.filter((m) => m.status === "active").length;
      const body: StaffListOut = {
        items: [],
        total: 0,
        tallies: {
          seats_used: active,
          seats_pending: 0,
          partners: 0,
          professionals: 0,
          operations: 0,
          sso_mfa: active,
          signed_in_of: active,
          seasonal: 0,
        },
        members: seed.staff,
        invitations: [],
      };
      return json(body);
    },
    "GET /v1/firm/members": () => {
      const body: FirmMemberOut[] = seed.members;
      return json(body);
    },
    "GET /v1/firm/time-zone": () => {
      const body: TimeZoneIo = { time_zone: seed.firm.timeZone };
      return json(body);
    },
    "GET /v1/firm/clients": (request) => {
      const walled = walledClients(seed, request);
      const body: FirmClientOut[] = seed.firmClients.filter((c) => !walled.has(c.client_id));
      return json(body);
    },
    "GET /v1/firm/clients/search": (request) => {
      const q = (request.query.get("q") ?? "").trim().toLowerCase();
      const walled = walledClients(seed, request);
      const body: ClientChoiceOut[] =
        q === ""
          ? []
          : seed.clients
              .filter((c) => c.name.toLowerCase().includes(q))
              .filter((c) => !walled.has(seed.clientIds[c.slug] ?? ""))
              .map((c) => ({
                id: seed.clientIds[c.slug] ?? "",
                name: c.name,
                entities: c.entities.map((name) => ({ id: entityIdOf(c.slug, name), name })),
              }));
      return json(body);
    },
    "GET /v1/engagements": (request) => {
      const walled = walledClients(seed, request);
      const body: EngagementSummaryOut[] = seed.summaries.filter((e) => !walled.has(e.client_id));
      return json(body);
    },
    "GET /v1/engagements/{engagement_id}": (request) => {
      const found = engagement(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(found);
    },
    "GET /v1/engagements/{engagement_id}/work-items": (request) => {
      const found = engagement(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const body: WorkItemOut[] = seed.workItems[found.id] ?? [];
      return json(body);
    },
    "GET /v1/engagements/{engagement_id}/request-items": (request) => {
      const found = engagement(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const body: RequestItemOut[] = seed.requestItems[found.id] ?? [];
      return json(body);
    },
    "GET /v1/engagements/{engagement_id}/client-contacts": (request) => {
      const found = engagement(request);
      return found === undefined ? json(NOT_FOUND, 404) : json(seed.contacts[found.id] ?? []);
    },
  };
}

/** The signed-in person (`GET /v1/me`) over the seed: for a screen's own scenario that names its
 * persona and needs the viewer to be a person (a HumanAction; N-01-T15, N-02-T15). */
export function meHandlers(seed: Seed = getSeed()): Record<string, FixtureHandler> {
  const me = seedHandlers(seed)["GET /v1/me"];
  return me === undefined ? {} : { "GET /v1/me": me };
}
