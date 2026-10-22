// P-01-T07 footings for SHL-03: the firm row's 46 seats, the person cards against the seats,
// job titles, the offices and default office filter, the sandbox membership and the capability
// nav per persona.
import { describe, expect, it } from "vitest";
import { getSeed } from "./seed";
import { JOB_TITLES, OFFICES, SEATS, slugOf } from "./seed/people";
import {
  ALL_OFFICES,
  FIRM_FACTS_LINE,
  OFFICE_REFS,
  SANDBOX_FIRM_ID,
  SANDBOX_FIRM_NAME,
  SHELL_PERSONAS,
  SWITCH_TOAST,
  capabilitiesFor,
  meV3For,
  officeIdOf,
  officeMenu,
} from "./seed/shell";

const seed = getSeed();

describe("the firm row", () => {
  it("reads US · Central Time · 46 seats, and the seats foot 22 + 14 + 10 = 46", () => {
    expect(FIRM_FACTS_LINE).toBe(`US · Central Time · ${String(seed.seats.length)} seats`);
    expect(OFFICES.reduce((n, o) => n + o.seats, 0)).toBe(46);
    expect(seed.firm.timeZone).toBe("America/Chicago");
  });
});

describe("person cards", () => {
  it("each card ends with the seat's office and carries its job title", () => {
    for (const p of SHELL_PERSONAS) {
      const seat = SEATS.find((s) => slugOf(s.name) === p.slug);
      expect(seat?.initials, p.slug).toBe(p.initials);
      expect(p.cardLine.endsWith(` · ${seat?.office ?? ""}`), p.slug).toBe(true);
      expect(p.cardLine, p.slug).toContain(JOB_TITLES[p.initials] ?? "?");
    }
  });

  it("/v1/me v3 carries initials, job title and email as the cards show them", () => {
    const grace = meV3For(seed, "grace-holloway");
    expect(grace?.user).toEqual({ initials: "GH", job_title: "Client Service Coordinator" });
    expect(grace?.email).toBe("grace.holloway@brightwaterhale.com");
    expect(meV3For(seed, "hannah-leclerc")?.email).toBe("hannah.leclerc@brightwaterhale.com");
    expect(meV3For(seed, "daniel-reyes")?.user.job_title).toBe("Tax Partner");
    expect(meV3For(seed, "felix-andersen")?.user.job_title).toBe("Qualified Individual");
    expect(meV3For(seed, "ana-cruz")?.user.job_title).toBeNull();
  });
});

describe("offices and the default office filter", () => {
  it("the submenu reads All offices · Chicago · Denver · New York, ids shared with the loader", () => {
    expect(officeMenu()).toEqual([ALL_OFFICES, "Chicago", "Denver", "New York"]);
    expect(OFFICE_REFS.map((o) => o.id)).toEqual(OFFICES.map((o) => officeIdOf(o.name)));
    expect(new Set(OFFICE_REFS.map((o) => o.id)).size).toBe(3);
  });

  it("Hannah's default is Chicago (b); Grace's is All offices (a, f)", () => {
    expect(meV3For(seed, "hannah-leclerc")?.default_office_id).toBe(officeIdOf("Chicago"));
    expect(meV3For(seed, "grace-holloway")?.default_office_id).toBeNull();
    expect(meV3For(seed, "grace-holloway")?.offices).toHaveLength(3);
  });
});

describe("the training sandbox (SHL-03e)", () => {
  it("only Grace holds it, as a second membership marked is_sandbox", () => {
    const grace = meV3For(seed, "grace-holloway");
    expect(grace?.memberships.map((m) => m.firm.is_sandbox)).toEqual([false, true]);
    const sandbox = grace?.memberships[1];
    expect(sandbox?.tenant_id).toBe(SANDBOX_FIRM_ID);
    expect(sandbox?.firm_name).toBe(SANDBOX_FIRM_NAME);
    expect(sandbox?.firm.sandbox_of).toBe(seed.firm.id);
    expect(SWITCH_TOAST).toBe("Switched to Brightwater Hale LLP — Training sandbox");
    for (const slug of ["hannah-leclerc", "daniel-reyes", "felix-andersen"]) {
      expect(meV3For(seed, slug)?.memberships, slug).toHaveLength(1);
    }
    expect(meV3For(seed, "grace-holloway")?.memberships[0]?.firm.seats_total).toBe(46);
  });
});

describe("capability nav (AC 2.1.2)", () => {
  const nav = (slug: string) => capabilitiesFor(seed, slug).nav;
  const shown = (slug: string) =>
    Object.entries(nav(slug))
      .filter(([, access]) => access !== "none")
      .map(([key]) => key);

  it("a Grace: Firm settings, Users & roles, Audit log", () => {
    expect(shown("grace-holloway")).toEqual(["firm_settings", "users_roles", "audit_log"]);
    expect(nav("grace-holloway").firm_settings).toBe("write");
  });
  it("b Hannah: no admin section", () => {
    expect(shown("hannah-leclerc")).toEqual([]);
  });
  it("c Daniel: Firm settings read-only and Audit log", () => {
    expect(shown("daniel-reyes")).toEqual(["firm_settings", "audit_log"]);
    expect(nav("daniel-reyes").firm_settings).toBe("read");
  });
  it("d Felix: Security center, Developer & API and Audit log", () => {
    expect(shown("felix-andersen")).toEqual(["audit_log", "security_center", "developer_api"]);
  });
});
