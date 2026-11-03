// N-04-T09: NOT-01 b, c and d, the O3 intake sheet in fixture mode. Acceptance: "Scenario tests for
// b, c and d pass, Create notice stays disabled while extracting or while a low-confidence field is
// unconfirmed, and no full SSN reaches the DOM." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { NoticesIndex } from ".";
import { INTAKE, type Not01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Not01State): void {
  restore = installFixtureMode(scenarios[state]);
  const intakeId = INTAKE[state];
  renderRoutes([
    {
      path: "/",
      component: () => <NoticesIndex {...(intakeId === undefined ? {} : { intakeId })} />,
    },
  ]);
}

function create(): HTMLButtonElement {
  return screen.getByRole("button", { name: "Create notice" });
}

const FULL_SSN = /\b\d{3}-\d{2}-\d{4}\b/u;

describe("NOT-01 b: the intake sheet", () => {
  it("reads every field with its confidence, the TIN as its last four", async () => {
    mount("b");
    await screen.findByText("Extracted by Accrued Agent");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-intake-field]").length).toBe(8);
    });
    const pills = [...document.querySelectorAll("[data-confidence]")].map((p) => p.textContent);
    expect(pills).toEqual(["99%", "99%", "98%", "98%", "97%", "97%", "98%", "96%"]);
    expect(document.body.textContent).toContain("•••-••-6602");
    expect(document.body.textContent).not.toMatch(FULL_SSN);
    expect(document.body.textContent).toContain("Santos_IRS_letter.jpg · 2 pages");
    expect(document.body.textContent).toContain("Draft Form 2848…");
  });

  it("enables Create notice once read", async () => {
    mount("b");
    await waitFor(() => {
      expect(create().disabled).toBe(false);
    });
  });
});

describe("NOT-01 c: the agent still reading", () => {
  it("shows Reading 2 pages… with Create notice disabled", async () => {
    mount("c");
    await screen.findByText("Reading 2 pages…");
    expect(create().disabled).toBe(true);
    expect(document.querySelector("[data-intake='extracting']")).not.toBeNull();
  });
});

describe("NOT-01 d: a low-confidence field", () => {
  it("reads 71% · date partly obscured with its helper, Create notice disabled until confirmed", async () => {
    mount("d");
    await screen.findByText("71% · date partly obscured");
    expect(document.body.textContent).toContain("Check page 1, top right");
    expect(document.querySelector("[data-confidence='low']")).not.toBeNull();
    expect(create().disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      expect(create().disabled).toBe(false);
    });
    expect(document.body.textContent).not.toMatch(FULL_SSN);
  });
});
