// CLI-06 · New client / prospect intake, single client (P-07-T49; docs/screens/CLI-06.md). One test
// per artboard a–f, h and i on its fixture scenario (g is P-07-T54's bulk import), and the
// acceptance: "Scenarios a to f, h and i pass with axe and Create and start acceptance lands on
// CLI-07" (axe: e2e/screens/CLI-06.spec.ts, Playwright). Also: Next validates each step, step rows
// jump only to finished steps, a person records screening, a manager clears a hit, and the AVOID
// list.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { CLI06, type Cli06Target } from ".";
import { COPY } from "./copy";
import { type Cli06State, DRAFT_ID, OPENS, STATES, freshScenario } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function install(scenario: Scenario): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return calls;
}

function show(state: Cli06State, onNavigate?: (t: Cli06Target) => void): Call[] {
  const calls = install(freshScenario(state));
  const opens = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CLI06
          draftId={DRAFT_ID}
          step={opens.step}
          {...(opens.problems === undefined ? {} : { problems: opens.problems })}
          screened={opens.screened === true}
          {...(onNavigate === undefined ? {} : { onNavigate })}
        />
      ),
    },
  ]);
  return calls;
}

function next(): void {
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
}

describe("CLI-06 artboards", () => {
  it("has a scenario for every single-intake artboard (g is the bulk import's)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "h", "i"]);
  });

  it("a: four names searched, No conflicts, screening recorded by a person", async () => {
    show("a");
    expect(await screen.findByText(COPY.conflicts.none)).toBeTruthy();
    expect(screen.getByText(/^Searched 4 names across every client/)).toBeTruthy();
    expect(screen.getByText("Same family · not adverse")).toBeTruthy();
    expect(screen.getAllByText(/ · Recorded by /)).toHaveLength(3);
  });

  it("b: the dedupe card recommends adding the estate under Walter Thornbury", async () => {
    show("b");
    expect(await screen.findByText(COPY.dedupe.match(96, "Walter Thornbury"))).toBeTruthy();
    const radio = screen.getByRole("radio", { name: COPY.dedupe.recommended });
    expect(radio.getAttribute("aria-checked")).toBe("true");
  });

  it("c: the decedent and the executor, and the fiduciary disclosure rule", async () => {
    show("c");
    expect(
      await screen.findByText(
        COPY.relationships.decedent("Walter Thornbury", "Estate of Walter Thornbury"),
      ),
    ).toBeTruthy();
    expect(screen.getByText(COPY.relationships.executor("Paul Thornbury"))).toBeTruthy();
    expect(screen.getByText(COPY.relationships.note)).toBeTruthy();
  });

  it("d: Paul Thornbury, executor", async () => {
    show("d");
    expect(await screen.findByDisplayValue("Paul Thornbury")).toBeTruthy();
    expect(screen.getByDisplayValue("paul.thornbury@thornburylaw.com")).toBeTruthy();
  });

  it("e: the services, Form 706 among them", async () => {
    show("e");
    const box = await screen.findByRole("checkbox", { name: "Form 706" });
    expect(box.getAttribute("aria-checked")).toBe("true");
    expect(
      screen.getByRole("checkbox", { name: "Estate Form 1041" }).getAttribute("aria-checked"),
    ).toBe("true");
  });

  it("f: Create & start acceptance lands on CLI-07 (Prospect only)", async () => {
    const onNavigate = vi.fn();
    const calls = show("f", onNavigate);
    fireEvent.click(await screen.findByRole("button", { name: COPY.review.createStart }));
    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalled();
    });
    const target = onNavigate.mock.calls[0]?.[0] as Cli06Target;
    expect(target.screen).toBe("CLI-07");
    const commit = calls.find((c) => c.path.endsWith("/commit"));
    expect(commit?.body).toEqual({ start_acceptance: true });
  });

  it("f: Create lands on CLI-02", async () => {
    const onNavigate = vi.fn();
    show("f", onNavigate);
    fireEvent.click(await screen.findByRole("button", { name: COPY.review.create }));
    await waitFor(() => {
      expect((onNavigate.mock.calls[0]?.[0] as Cli06Target | undefined)?.screen).toBe("CLI-02");
    });
  });

  it("h: a counterparty to review, cleared as not adverse by Samuel Ito", async () => {
    const calls = show("h");
    expect(await screen.findByText("Harborline Trust Company")).toBeTruthy();
    expect(screen.queryByText(COPY.conflicts.none)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: COPY.conflicts.clear }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "Custodian only; no adverse interest." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.conflicts.clearConfirm }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/clear"))).toBe(true);
    });
  });

  it("i: Date of death empty says why", async () => {
    show("i");
    expect(await screen.findByText("Required for Form 706 due date")).toBeTruthy();
  });

  it("i: Next on Services stops and jumps to Entity details with the reason", async () => {
    install(freshScenario("i"));
    renderRoutes([{ path: "/", component: () => <CLI06 draftId={DRAFT_ID} step="services" /> }]);
    await screen.findByRole("checkbox", { name: "Form 706" });
    next();
    expect(await screen.findByText("Required for Form 706 due date")).toBeTruthy();
    expect(screen.getByDisplayValue("Estate of Walter Thornbury")).toBeTruthy();
  });
});

describe("CLI-06 steps", () => {
  it("rows jump only to finished steps", async () => {
    show("c");
    await screen.findByText(COPY.relationships.note);
    fireEvent.click(screen.getByText(COPY.steps.review));
    expect(screen.queryByRole("button", { name: COPY.review.create })).toBeNull();
    fireEvent.click(screen.getByText(COPY.steps.entity));
    expect(await screen.findByDisplayValue("Estate of Walter Thornbury")).toBeTruthy();
  });

  it("Next saves and validates the step before moving on", async () => {
    const calls = show("b");
    await screen.findByText(COPY.dedupe.match(96, "Walter Thornbury"));
    next();
    expect(await screen.findByText(COPY.relationships.note)).toBeTruthy();
    expect(calls.some((c) => c.method === "PATCH")).toBe(true);
    expect(calls.some((c) => c.path.endsWith("/validate"))).toBe(true);
  });
});

describe("CLI-06 avoid", () => {
  it("no automated screening result: each list waits for a person", async () => {
    show("h");
    await screen.findByText("Harborline Trust Company");
    expect(screen.getAllByRole("button", { name: COPY.conflicts.record })).toHaveLength(3);
    expect(document.body.innerHTML).not.toMatch(/gradient|lorem/i);
  });
});
