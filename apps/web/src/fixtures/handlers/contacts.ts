// Contacts and portal access over the seed (P-07-T33; docs/contracts/contacts-access.md): the
// CLI-04 routes typed with the generated client. Northwind's six contacts and Copperleaf's two are
// the handoff's (spec.md ROWS 1–6 and g), in its row order, so the footer's `parts` read
// 10 + 9 + 2 + 2 + 1 (the live list sorts by name, DEC-302; the sum is the same). Each contact's
// delegated requests are Northwind's 24 PBC requests (seed/requests.ts): first those the seed's
// owner column gives it, then the next unassigned ones, so the counts are the handoff's (the
// owner column disagrees with them: TASK-1161's open gap). Writes follow the live rules: invite
// only a Not invited contact (409 `illegal_transition`), Change scope with the version seen (409
// `stale_version`), Revoke back to Not invited with the requests kept, Unlock only a Locked one.
// A walled client answers 404 (INV-3). Grace Holloway (Firm Admin) holds every row action; anyone
// else none (allowed_actions are judged on the client, DEC-302).

import type {
  ContactDetailOut,
  ContactRowOut,
  ContactsPage,
  InvitationIn,
  InvitationOut,
  InvitationRevokedOut,
  ContactAccessIn,
  ContactAccessOut,
  ContactUnlockedOut,
  GrantOut,
  SignInEventOut,
} from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import type { Seed } from "../seed";
import { COPPERLEAF, NORTHWIND, clientIdOf } from "../seed/client-records";
import { PORTAL_USERS } from "../seed/portal";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
const ROW_ACTIONS = [
  "client_access.grant",
  "client_access.revoke",
  "contact.manage",
  "contact.unlock",
];
/** Who holds the row actions (DEC-302: judged on the client, firm roles). */
const ADMINS = new Set(["grace-holloway"]);

/** Mon Sep 14, 2026 (E0). */
const TODAY = "2026-09-14";
const IN_14_DAYS = "2026-09-28";

export interface ContactFixture {
  clientId: string;
  row: Omit<ContactRowOut, "allowed_actions" | "delegated_request_count">;
  delegated: string[];
  version: number;
  signIns: SignInEventOut[];
}

type Role = NonNullable<ContactRowOut["roles"]>[number];

function role(clientId: string, client: string, code: Role["role"], title?: string): Role {
  return {
    role: code,
    scope_kind: "client",
    scope_id: clientId,
    scope_name: client,
    ...(title === undefined ? {} : { title_text: title }),
  };
}

function portalEmail(name: string): string | null {
  return PORTAL_USERS.find((u) => u.name === name)?.email ?? null;
}

/** Northwind's 24 requests handed out to the six contacts as the handoff counts them. */
function northwindDelegations(seed: Seed, engagementId: string | undefined): string[][] {
  const items = engagementId === undefined ? [] : (seed.requestItems[engagementId] ?? []);
  const plan: [string, number][] = [
    ["Dana Kowalski", 10],
    ["", 0], // the benefits committee: governance communications, no PBC requests
    ["Keystone Retirement Services", 9],
    ["Summit Plan Administrators", 2],
    ["Harborline Trust Company", 2],
    ["PayGrid Payroll", 1],
  ];
  const taken = new Set<string>();
  const out = plan.map(([owner, n]) => {
    const mine = items
      .filter((i) => seed.requestOwners[i.id] === owner && !taken.has(i.id))
      .slice(0, n)
      .map((i) => i.id);
    for (const id of mine) taken.add(id);
    return mine;
  });
  return out.map((mine, i) => {
    const want = plan[i]?.[1] ?? 0;
    while (mine.length < want) {
      const next = items.find((it) => !taken.has(it.id));
      if (next === undefined) break;
      taken.add(next.id);
      mine.push(next.id);
    }
    return mine;
  });
}

/** The contacts at E0 (CLI-04 a and g), keyed by id. */
export function seedContacts(seed: Seed): ContactFixture[] {
  const north = clientIdOf(NORTHWIND);
  const copper = clientIdOf(COPPERLEAF);
  const d = northwindDelegations(seed, seed.engagementIds.A1);
  const at = (slug: string): string => stableId(`contact:${slug}`);
  const nw = (code: Role["role"], title?: string): Role => role(north, NORTHWIND, code, title);
  return [
    {
      clientId: north,
      row: {
        id: at("northwind:dana-kowalski"),
        name: "Dana Kowalski",
        party_kind: "person",
        email: "dana.kowalski@northwindrobotics.com",
        roles: [nw("plan_sponsor_officer", "HR Director")],
        portal_status: "active",
        mfa_enrolled: true,
        last_seen_at: "2026-09-14T13:02:00Z",
        invitation_id: stableId("invitation:northwind:dana-kowalski"),
      },
      delegated: d[0] ?? [],
      version: 4,
      signIns: [{ kind: "signed_in", at: "2026-09-14T13:02:00Z" }],
    },
    {
      clientId: north,
      row: {
        id: at("northwind:benefits-committee"),
        name: "Northwind benefits committee",
        party_kind: "group",
        roles: [],
        portal_status: "active",
        mfa_enrolled: true,
        last_seen_at: "2026-09-03T15:00:00Z",
        invitation_id: stableId("invitation:northwind:benefits-committee"),
      },
      delegated: d[1] ?? [],
      version: 2,
      signIns: [],
    },
    {
      clientId: north,
      row: {
        id: at("northwind:sam-ortiz"),
        name: "Sam Ortiz",
        party_kind: "person",
        email: "sam.ortiz@keystoneretirement.com",
        roles: [nw("recordkeeper", "Keystone Retirement Services")],
        portal_status: "active",
        mfa_enrolled: true,
        last_seen_at: "2026-09-14T13:47:00Z",
        invitation_id: stableId("invitation:northwind:sam-ortiz"),
      },
      delegated: d[2] ?? [],
      version: 3,
      signIns: [{ kind: "signed_in", at: "2026-09-14T13:47:00Z" }],
    },
    {
      clientId: north,
      row: {
        id: at("northwind:summit"),
        name: "Summit Plan Administrators",
        party_kind: "organisation",
        roles: [nw("tpa", "TPA · prepares Form 5500")],
        portal_status: "invited",
        invited_on: "2026-09-10",
        expires_on: "2026-09-24",
        invitation_id: stableId("invitation:northwind:summit"),
      },
      delegated: d[3] ?? [],
      version: 2,
      signIns: [],
    },
    {
      clientId: north,
      row: {
        id: at("northwind:harborline"),
        name: "Harborline Trust Company",
        party_kind: "organisation",
        email: "certifications@harborlinetrust.com",
        roles: [nw("custodian", "Directed trustee / custodian")],
        portal_status: "not_invited",
      },
      delegated: d[4] ?? [],
      version: 1,
      signIns: [],
    },
    {
      clientId: north,
      row: {
        id: at("northwind:paygrid"),
        name: "PayGrid Payroll",
        party_kind: "organisation",
        roles: [nw("payroll_provider", "Payroll provider")],
        portal_status: "not_invited",
      },
      delegated: d[5] ?? [],
      version: 1,
      signIns: [],
    },
    {
      clientId: copper,
      row: {
        id: at("copperleaf:tess-moreno"),
        name: "Tess Moreno",
        party_kind: "person",
        email: portalEmail("Tess Moreno"),
        roles: [role(copper, COPPERLEAF, "owner", "CEO")],
        portal_status: "active",
        mfa_enrolled: true,
        invitation_id: stableId("invitation:copperleaf:tess-moreno"),
      },
      delegated: [],
      version: 1,
      signIns: [],
    },
    {
      clientId: copper,
      row: {
        id: at("copperleaf:ben-ashby"),
        name: "Ben Ashby",
        party_kind: "person",
        email: portalEmail("Ben Ashby"),
        roles: [role(copper, COPPERLEAF, "controller", "Approver of record")],
        portal_status: "active",
        mfa_enrolled: true,
        invitation_id: stableId("invitation:copperleaf:ben-ashby"),
      },
      delegated: [],
      version: 1,
      signIns: [],
    },
  ];
}

export interface ContactHandlerOptions {
  /** A contact's state changed from E0 (c: Harborline invited; d: Sam Ortiz locked). */
  change?: (contacts: ContactFixture[]) => void;
}

export function contactHandlers(
  seed: Seed,
  options: ContactHandlerOptions = {},
): Record<string, FixtureHandler> {
  const contacts = structuredClone(seedContacts(seed));
  options.change?.(contacts);
  const received = new Set(
    Object.values(seed.requestItems)
      .flat()
      .filter((i) => i.status === "received")
      .map((i) => i.id),
  );
  const walled = (request: FixtureRequest, clientId: string): boolean => {
    const who = request.persona ?? DEFAULT_PERSONA;
    return seed.walls.some((w) => w.personSlug === who && w.clientId === clientId);
  };
  const rowOf = (c: ContactFixture, request: FixtureRequest): ContactRowOut => ({
    ...c.row,
    delegated_request_count: c.delegated.length,
    allowed_actions: ADMINS.has(request.persona ?? DEFAULT_PERSONA) ? [...ROW_ACTIONS] : [],
  });
  const find = (request: FixtureRequest): ContactFixture | undefined => {
    const found = contacts.find((c) => c.row.id === request.params.contact_id);
    return found === undefined || walled(request, found.clientId) ? undefined : found;
  };
  const byInvitation = (request: FixtureRequest): ContactFixture | undefined => {
    const found = contacts.find(
      (c) => c.row.invitation_id != null && c.row.invitation_id === request.params.invitation_id,
    );
    return found === undefined || walled(request, found.clientId) ? undefined : found;
  };
  const grantsOf = (c: ContactFixture): GrantOut[] =>
    c.delegated.map((id) => ({
      id: stableId(`grant:${c.row.id}:${id}`),
      role: "third_party",
      scope_kind: "request_item",
      scope_id: id,
      request_item_ids: [id],
      status: c.row.portal_status === "invited" ? "pending" : "active",
      granted_at: "2026-09-01T14:00:00Z",
    }));
  const invitationOut = (c: ContactFixture): InvitationOut => ({
    invitation_id: c.row.invitation_id ?? "",
    contact_id: c.row.id,
    grants: grantsOf(c),
    mfa_policy: "required_by_firm",
    sent_at: `${TODAY}T14:24:00Z`,
    expires_at: `${IN_14_DAYS}T14:24:00Z`,
    portal_status: "invited",
  });
  const requestItemsOf = (grants: InvitationIn["grants"]): string[] => [
    ...new Set(grants.flatMap((g) => g.request_item_ids ?? [])),
  ];

  return {
    "GET /v1/clients/{client_id}/contacts": (request) => {
      const clientId = request.params.client_id ?? "";
      if (walled(request, clientId)) return json(NOT_FOUND, 404);
      const rows = contacts.filter((c) => c.clientId === clientId).map((c) => rowOf(c, request));
      const counts: Record<string, number> = {};
      for (const r of rows) counts[r.portal_status] = (counts[r.portal_status] ?? 0) + 1;
      const parts = rows.map((r) => r.delegated_request_count ?? 0).filter((n) => n > 0);
      const delegatedIds = contacts
        .filter((c) => c.clientId === clientId)
        .flatMap((c) => c.delegated);
      const status = request.query.get("portal_status");
      const items = status === null ? rows : rows.filter((r) => r.portal_status === status);
      const body: ContactsPage = {
        items,
        next_cursor: null,
        total: items.length,
        counts,
        summary: {
          active: counts.active ?? 0,
          invited: counts.invited ?? 0,
          not_invited: counts.not_invited ?? 0,
          locked: counts.locked ?? 0,
        },
        delegated: {
          parts,
          total: parts.reduce((a, b) => a + b, 0),
          received: delegatedIds.filter((id) => received.has(id)).length,
        },
      };
      return json(body);
    },
    "GET /v1/contacts/{contact_id}": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const body: ContactDetailOut = {
        contact: rowOf(found, request),
        grants: grantsOf(found),
        sign_ins: found.signIns,
        delegated_request_ids: found.delegated,
        version: found.version,
      };
      return json(body);
    },
    "POST /v1/contacts/{contact_id}/invitations": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (found.row.portal_status !== "not_invited") {
        return json({ detail: "illegal_transition" }, 409);
      }
      const body = request.body as InvitationIn;
      const items = requestItemsOf(body.grants);
      found.delegated = items.length > 0 ? items : found.delegated;
      found.row = {
        ...found.row,
        portal_status: "invited",
        invited_on: TODAY,
        expires_on: IN_14_DAYS,
        invitation_id: stableId(`invitation:${found.row.id}:${String(found.version + 1)}`),
      };
      found.version += 1;
      return json(invitationOut(found), 201);
    },
    "POST /v1/invitations/{invitation_id}/resend": (request) => {
      const found = byInvitation(request);
      if (found?.row.portal_status !== "invited") return json(NOT_FOUND, 404);
      found.row = { ...found.row, invited_on: TODAY, expires_on: IN_14_DAYS };
      return json(invitationOut(found));
    },
    "POST /v1/invitations/{invitation_id}/revoke": (request) => {
      const found = byInvitation(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const out: InvitationRevokedOut = {
        invitation_id: found.row.invitation_id ?? "",
        contact_id: found.row.id,
        revoked_grant_ids: grantsOf(found).map((g) => g.id),
        kept_request_item_ids: found.delegated,
        revoked_at: `${TODAY}T14:24:00Z`,
      };
      found.row = {
        ...found.row,
        portal_status: "not_invited",
        invited_on: null,
        expires_on: null,
        invitation_id: null,
        mfa_enrolled: null,
      };
      found.delegated = [];
      found.version += 1;
      return json(out);
    },
    "PUT /v1/contacts/{contact_id}/access": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      const body = request.body as ContactAccessIn;
      if (body.seen_version !== found.version) {
        return json({ detail: "stale_version", facts: { contact_id: found.row.id } }, 409);
      }
      if (found.row.portal_status === "not_invited") {
        return json({ detail: "illegal_transition" }, 409);
      }
      found.delegated = requestItemsOf(body.grants);
      found.version += 1;
      const out: ContactAccessOut = {
        contact_id: found.row.id,
        grants: grantsOf(found),
        version: found.version,
      };
      return json(out);
    },
    "POST /v1/contacts/{contact_id}/unlock": (request) => {
      const found = find(request);
      if (found === undefined) return json(NOT_FOUND, 404);
      if (found.row.portal_status !== "locked") return json({ detail: "illegal_transition" }, 409);
      found.row = { ...found.row, portal_status: "active" };
      found.signIns = [...found.signIns, { kind: "unlocked", at: `${TODAY}T14:24:00Z` }];
      const out: ContactUnlockedOut = {
        contact_id: found.row.id,
        portal_status: "active",
        unlocked_at: `${TODAY}T14:24:00Z`,
      };
      return json(out);
    },
  };
}
