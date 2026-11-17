// C-01-T39 (TASK-8535): CLS-06 Review in fixture mode. Row acceptance: "The Review badge equals the
// open exceptions (2 + 5), Resolve stays disabled without a note, and an issue assigned to the agent
// shows no resolve control for the agent."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { copperleafAugust } from "../../fixtures/seed/closes";
import { CLOSE_IDS } from "../../fixtures/seed/closes";
import { newQueryClient } from "../../testing/support";
import { CLS06, type CLS06Props } from "./index";
import { type Cls06State, INITIAL, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Cls06State, props: Partial<CLS06Props> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLS06 closeId={CLOSE_IDS.august} initial={INITIAL[state]} {...props} />
    </QueryClientProvider>,
  );
}

async function queue(): Promise<void> {
  await waitFor(() => {
    expect(
      document.querySelector("[data-cls06='queue'], [data-cls06='notes'], [data-cls06='empty']"),
    ).not.toBeNull();
  });
}

describe("CLS-06 Review", () => {
  it.each(Object.keys(scenarios) as Cls06State[])("renders %s", async (st) => {
    show(st);
    await queue();
  });

  it("the Review badge equals the open exceptions: Medium 2 + Low 5 = 7", async () => {
    show("a");
    await queue();
    const medium = document.querySelectorAll("[data-band='medium'] [data-issue]").length;
    const low = document.querySelectorAll("[data-band='low'] [data-issue]").length;
    expect([medium, low]).toEqual([2, 5]);
    expect(screen.getByRole("tab", { name: "Exceptions 7" })).toBeTruthy();
    expect(copperleafAugust().open_issues).toBe(medium + low);
  });

  it("notes never count (e shows 4 notes beside 7 exceptions)", async () => {
    show("e");
    await queue();
    expect(document.querySelectorAll("[data-note]").length).toBe(4);
    expect(screen.getByRole("tab", { name: "Exceptions 7" })).toBeTruthy();
  });

  it("Resolve stays disabled until the note is written", async () => {
    show("a2");
    await waitFor(() => {
      expect(document.querySelector("[data-cls06='resolve']")).not.toBeNull();
    });
    const confirm = screen.getByRole("button", { name: "Resolve" });
    expect(confirm).toHaveProperty("disabled", true);
    fireEvent.change(screen.getByLabelText("Resolution note"), {
      target: { value: "Invoice agreed." },
    });
    expect(confirm).toHaveProperty("disabled", false);
  });

  it("an issue assigned to the agent offers no resolve control to the agent", async () => {
    show("a", { grants: [] });
    await queue();
    expect(document.querySelector("[data-cls06='detail']")?.textContent).toContain(
      "Sound Electric",
    );
    expect(screen.queryByRole("button", { name: "✓ Resolve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark Not Applicable" })).toBeNull();
    cleanup();
    restore?.();
    show("a");
    await queue();
    expect(screen.getByRole("button", { name: "✓ Resolve" })).toBeTruthy();
  });

  it("c pre-fills the agent's note; d is resolved with Reopen and badge 6", async () => {
    show("c");
    await waitFor(() => {
      expect(document.querySelector("[data-cls06='answer']")).not.toBeNull();
    });
    cleanup();
    restore?.();
    show("d");
    await queue();
    expect(screen.getByRole("tab", { name: "Exceptions 6" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reopen" })).toBeTruthy();
  });

  it("the register selects check #2285 for Sound Electric", async () => {
    show("a");
    await waitFor(() => {
      expect(
        document.querySelector("[data-register-line='chk-2285']")?.hasAttribute("data-selected"),
      ).toBe(true);
    });
  });

  it("g reads 'No open issues.'", async () => {
    show("g");
    await waitFor(() => {
      expect(document.querySelector("[data-cls06='empty']")?.textContent).toContain(
        "No open issues.",
      );
    });
  });
});
