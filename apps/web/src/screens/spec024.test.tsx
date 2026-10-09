// SPEC-024 (TASK-040): sign-up, the no-firm page, client-only routing, engagement types.
import type { MeOut, TemplateVersionOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Layout } from "./Layout";
import { ApplyMethodology } from "./Overview";
import { Signup } from "./Signup";

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const signupPage = (): void => {
  renderRoutes([
    { path: "/", component: Signup },
    { path: "/home", component: () => <p>Workspace</p> },
  ]);
};

describe("ac1 sign-up", () => {
  it("creates the firm with the name and code", async () => {
    const { calls } = mockApi({ "POST /v1/signup": () => json({ tenant_id: "t-new" }, 201) });
    signupPage();
    fireEvent.change(await screen.findByLabelText("Firm name"), {
      target: { value: "Whitfield & Lane" },
    });
    fireEvent.change(screen.getByLabelText("Sign-up code"), {
      target: { value: " ABCD-EFGH-JKMN-PQRS " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create firm" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path === "/v1/signup")?.body).toEqual({
        firm_name: "Whitfield & Lane",
        code: "ABCD-EFGH-JKMN-PQRS",
      });
    });
    await waitFor(() => {
      expect(sessionStorage.getItem("abacus.tenant")).toBe("t-new");
    });
  });

  it.each([
    ["signup_code_invalid", /isn't valid/],
    ["signup_already_staff", /already belong to a firm/],
    ["signup_rate_limited", /Too many attempts/],
  ])("explains %s in plain words", async (code, text) => {
    mockApi({ "POST /v1/signup": () => json({ detail: code }, 409) });
    signupPage();
    fireEvent.change(await screen.findByLabelText("Firm name"), { target: { value: "Firm" } });
    fireEvent.change(screen.getByLabelText("Sign-up code"), { target: { value: "WRONG-CODE" } });
    fireEvent.click(screen.getByRole("button", { name: "Create firm" }));
    expect(await screen.findByText(text)).toBeTruthy();
  });
});

describe("signed in without a firm", () => {
  it("shows the no-firm page with the way to set up a firm", async () => {
    mockApi({ "GET /v1/me": () => json({ detail: "forbidden" }, 403) });
    renderRoutes([{ path: "/", component: () => <p>Page</p> }], { root: Layout });
    expect(await screen.findByText("You're not part of a firm yet")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Set up your firm" }).getAttribute("href")).toBe(
      "/signup",
    );
  });

  it("sends someone who is only a client contact to their client home (amendment 3)", async () => {
    const client: MeOut = {
      user_id: "c1",
      display_name: "Fay Director",
      email: "fd@northwind.test",
      active_tenant_id: null,
      memberships: [
        { tenant_id: "t1", firm_name: "Firm one", firm_role: null, kind: "client" },
        { tenant_id: "t2", firm_name: "Firm two", firm_role: null, kind: "client" },
      ],
    };
    mockApi({ "GET /v1/me": () => json(client) });
    renderRoutes([
      { path: "/", component: Layout },
      { path: "/client", component: () => <p>Client home</p> },
    ]);
    expect(await screen.findByText("Client home")).toBeTruthy();
    expect(screen.queryByText("You're not part of a firm yet")).toBeNull();
  });
});

describe("ac6 engagement types", () => {
  it("offers only the templates for the engagement's type", async () => {
    const template = (name: string, types: string[]): TemplateVersionOut =>
      ({
        template_id: name,
        template_name: name,
        version_id: `v-${name}`,
        version: 1,
        created_at: "2026-10-01T00:00:00Z",
        engagement_types: types,
      }) as TemplateVersionOut;
    mockApi({
      "GET /v1/methodology/templates": () =>
        json([template("Audit core", ["audit"]), template("Review pack", ["review"])]),
      "GET /v1/engagements/e1": () => json({ id: "e1", type: "review", team: [] }),
    });
    renderRoutes([{ path: "/", component: () => <ApplyMethodology engagementId="e1" /> }]);
    const options = await screen.findAllByRole("option");
    await waitFor(() => {
      expect(options.map((o) => o.textContent)).toContain("Review pack · v1");
    });
    expect(screen.queryByText("Audit core · v1")).toBeNull();
  });
});
