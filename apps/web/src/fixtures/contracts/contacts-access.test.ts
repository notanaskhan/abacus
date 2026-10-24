// P-07-T18 (SPEC-321 AC-26 to AC-29): consumer fixture assertions for the contacts and
// portal-access stub (CLI-04, docs/contracts/contacts-access.md). Each frame is typed with the
// generated client, so a removed or renamed field fails `tsc`, and checked against the OpenAPI
// document at run time. Brightwater Hale, synthetic: Northwind's six contacts and their delegated
// requests from docs/screens/CLI-04.md and the contract's §8; ids are placeholders. The pytest half
// is backend/tests/contracts/contacts_access/test_contacts_access_consumer.py.
import type { ContactRowOut, ContactsPage, InvitationIn, InvitationOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateSchema } from "../schema-check";

/** `true` only when T has none of the keys K. */
type Lacks<T, K extends PropertyKey> = [Extract<keyof T, K>] extends [never] ? true : false;
type WallKey = "hidden_by_wall" | "hidden_count" | "walled_count";
type SecretKey = "token" | "link" | "url" | "invitation_url";

// Compile-time contract (AC-28, AC-29): no wall count on the page, never a token or link back.
const PAGE_HAS_NO_WALL: Lacks<ContactsPage, WallKey> = true;
const INVITATION_HAS_NO_TOKEN: Lacks<InvitationOut, SecretKey> = true;
const FOURTEEN_DAYS: NonNullable<InvitationIn["expires_in_days"]> extends 14 ? true : false = true;

const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const NORTHWIND = id(900);

const row = (
  n: number,
  name: string,
  portal_status: ContactRowOut["portal_status"],
  delegated_request_count: number,
  extra: Partial<ContactRowOut> = {},
): ContactRowOut => ({
  id: id(n),
  name,
  party_kind: "person",
  portal_status,
  delegated_request_count,
  ...extra,
});

// ---- CLI-04 a: Northwind Robotics, Inc., Mon Sep 14, 2026, 9:24 AM CT (Grace Holloway) --------

const CLI04_A: ContactsPage = {
  items: [
    row(1, "Dana Kowalski", "active", 10, {
      email: "dana.kowalski@northwindrobotics.com",
      mfa_enrolled: true,
      last_seen_at: "2026-09-14T13:02:00Z",
      roles: [
        {
          role: "plan_sponsor_officer",
          scope_kind: "client",
          scope_id: NORTHWIND,
          scope_name: "Northwind Robotics, Inc.",
          title_text: "HR Director",
        },
      ],
    }),
    row(2, "Northwind benefits committee", "active", 0, {
      party_kind: "group",
      mfa_enrolled: true,
    }),
    row(3, "Sam Ortiz", "active", 9, {
      email: "sam.ortiz@keystoneretirement.com",
      mfa_enrolled: true,
      roles: [
        {
          role: "recordkeeper",
          scope_kind: "client",
          scope_id: NORTHWIND,
          scope_name: "Northwind Robotics, Inc.",
        },
      ],
    }),
    row(4, "Summit Plan Administrators", "invited", 2, {
      party_kind: "organisation",
      invited_on: "2026-09-10",
      expires_on: "2026-09-24",
    }),
    row(5, "Harborline Trust Company", "not_invited", 2, { party_kind: "organisation" }),
    row(6, "PayGrid Payroll", "not_invited", 1, { party_kind: "organisation" }),
  ],
  total: 6,
  counts: { active: 3, invited: 1, not_invited: 2 },
  summary: { active: 3, invited: 1, not_invited: 2, locked: 0 },
  delegated: { parts: [10, 9, 2, 2, 1], total: 24, received: 11 },
};

// ---- CLI-04 c: Harborline's invitation, scoped to its two delegated requests -------------------

const HARBORLINE_INVITED: InvitationOut = {
  invitation_id: id(501),
  contact_id: id(5),
  grants: [
    {
      id: id(601),
      role: "third_party",
      scope_kind: "request_item",
      scope_id: id(701),
      request_item_ids: [id(701), id(702)],
      status: "pending",
    },
  ],
  mfa_policy: "required_by_firm",
  sent_at: "2026-09-14T14:24:00Z",
  expires_at: "2026-09-28T14:24:00Z",
  portal_status: "invited",
};

describe("contacts and portal access v1 (CLI-04)", () => {
  it("AC-28, AC-29: the compile-time contract holds", () => {
    expect([PAGE_HAS_NO_WALL, INVITATION_HAS_NO_TOKEN, FOURTEEN_DAYS]).toEqual([true, true, true]);
  });

  it("AC-26, AC-27: CLI-04 a is a valid page", () => {
    expect(validateSchema("ContactsPage", CLI04_A)).toEqual([]);
    expect(CLI04_A.items).toHaveLength(CLI04_A.total);
  });

  it("AC-27: the header reads 3 active · 1 invited · 2 not invited and sums to the rows", () => {
    const { active, invited, not_invited, locked } = CLI04_A.summary;
    expect([active, invited, not_invited]).toEqual([3, 1, 2]);
    expect(active + invited + not_invited + locked).toBe(CLI04_A.total);
    const byStatus: Record<string, number> = {};
    for (const r of CLI04_A.items)
      byStatus[r.portal_status] = (byStatus[r.portal_status] ?? 0) + 1;
    expect(byStatus).toEqual(CLI04_A.counts);
  });

  it("AC-27: the footer is 10 + 9 + 2 + 2 + 1 = 24 with 11 received", () => {
    const parts = CLI04_A.items
      .map((r) => r.delegated_request_count ?? 0)
      .filter((count) => count > 0);
    expect(CLI04_A.delegated.parts).toEqual(parts);
    expect(parts).toEqual([10, 9, 2, 2, 1]);
    expect(parts.reduce((a, b) => a + b, 0)).toBe(CLI04_A.delegated.total);
    expect(CLI04_A.delegated.total).toBe(24);
    expect(CLI04_A.delegated.received).toBe(11);
  });

  it("AC-28: an invitation carries its scoped grant and no token", () => {
    expect(validateSchema("InvitationOut", HARBORLINE_INVITED)).toEqual([]);
    expect(HARBORLINE_INVITED.grants[0]?.request_item_ids).toHaveLength(2);
    expect(validateSchema("InvitationOut", { ...HARBORLINE_INVITED, token: "x" })).not.toEqual([]);
  });
});
