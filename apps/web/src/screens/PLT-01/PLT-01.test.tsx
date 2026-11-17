import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TenantConsole } from ".";
import { PLT01_SCENARIOS } from "./scenarios";

// G-04-T14 (PLT-01 a to g): every artboard renders from its scenario; e renders in fixture mode and
// its nav item is absent in production; the support sheet has no approve control; no console
// control opens firm content; the seats footer foots.

afterEach(cleanup);

describe("PLT-01 tenant console", () => {
  it.each(PLT01_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(<TenantConsole st={st} />);
    expect(container.querySelector("[data-screen='PLT-01']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("a: six tenants and the tiles 6 / 4 / 1 / 1 / 404 of 490", () => {
    const { container } = render(<TenantConsole st="a" />);
    expect(container.querySelectorAll("[data-tenant]").length).toBe(6);
    const tiles = container.querySelector("[data-plt01='tiles']")?.textContent ?? "";
    for (const n of ["6", "4", "1", "404 of 490"]) expect(tiles).toContain(n);
    expect(container.querySelector("[data-plt01='footer']")?.textContent).toBe(
      "Seats used 46 + 128 + 212 + 18 + 0 = 404 of 490 provisioned (sandbox excluded).",
    );
  });

  it("e renders in fixture mode; its nav item is absent in production", () => {
    const fixture = render(<TenantConsole st="e" />);
    expect(fixture.container.querySelector("[data-plt01='library']")).not.toBeNull();
    expect(fixture.container.querySelector("[data-nav='library']")).not.toBeNull();
    cleanup();
    const prod = render(<TenantConsole st="e" production />);
    expect(prod.container.querySelector("[data-nav='library']")).toBeNull();
    expect(prod.container.querySelector("[data-plt01='library']")).toBeNull();
  });

  it("d: the support request has no approve control", () => {
    render(<TenantConsole st="d" />);
    expect(document.body.textContent).toContain(
      "Awaiting firm approval (Kessling Mott IT/Security)",
    );
    expect(screen.queryByRole("button", { name: /approve/iu })).toBeNull();
  });

  it.each(PLT01_SCENARIOS)("no control opens firm content (%s)", (st) => {
    render(<TenantConsole st={st} />);
    const text = document.body.textContent;
    expect(text).not.toMatch(/View as firm|Open client data/u);
  });

  it("g: the created toast and the tinted Ainsley Ward row", () => {
    const { container } = render(<TenantConsole st="g" />);
    expect(container.querySelector("[data-plt01='toast']")?.textContent).toContain(
      "Tenant created · invites sent to 2 first admins",
    );
    expect(container.querySelector("[data-tenant='tnt_aw15']")?.className).toContain(
      "bg-green-tint",
    );
  });
});
