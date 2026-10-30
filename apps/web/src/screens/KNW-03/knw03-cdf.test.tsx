// KNW-03 c, d and f (K-01-T15). The acceptance: "KNW-03c, d and f pass Tier C and the state-f
// banner quotes the 9:58 AM run error verbatim without rendering markup." Tier C (pixels) is the
// visual sweep's; here the content, the locks and the writes the drafter's clicks send.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { KNW03_RUN_ERROR, KNW03_TAILORING } from "../../fixtures/seed/knw03";
import { newQueryClient } from "../../testing/support";
import { ProgramEditorPage } from ".";
import { COPY } from "./copy";
import { type Knw03State, OPENS, scenarios } from "./scenarios";

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

function show(state: Knw03State): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const open = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ProgramEditorPage
        programId={open.programId}
        initialSegment={open.segment}
        {...(open.step === undefined ? {} : { step: open.step })}
        {...(open.from === undefined ? {} : { from: open.from })}
        {...(open.run === undefined ? {} : { run: open.run })}
        {...(open.tailoredFor === undefined ? {} : { tailoring: KNW03_TAILORING })}
      />
    </QueryClientProvider>,
  );
  return calls;
}

const row = (n: number): HTMLElement | null =>
  document.querySelector<HTMLElement>(`tr[data-step="${String(n)}"]`);

describe("KNW-03 c · editing a draft (Hannah Leclerc, v4)", () => {
  it("shows the draft banner, Done and + Step, and locks every mandatory step to the QM owner", async () => {
    show("c");
    expect(await screen.findByText(COPY.draft.banner(4))).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.draft.done })).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.actions.addStep })).toHaveProperty(
      "disabled",
      false,
    );
    await waitFor(() => {
      expect(row(1)).not.toBeNull();
    });
    // Step 1 is mandatory: locked with the tooltip's words, and its trash is disabled.
    expect(row(1)?.querySelector(`[aria-label="${COPY.draft.lockTip}"]`)).not.toBeNull();
    expect(screen.getByRole("button", { name: COPY.draft.remove(1) })).toHaveProperty(
      "disabled",
      true,
    );
    // Step 3 is optional: its text is an input and its trash works.
    expect(screen.getByRole("textbox", { name: COPY.draft.stepLabel(3) })).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: COPY.draft.stepLabel(1) })).toBeNull();
    expect(screen.getByRole("button", { name: COPY.draft.remove(3) })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("+ Step adds row 17; an edit sends the new text; removal and Submit (with row_version) reach the server", async () => {
    const calls = show("c");
    fireEvent.click(await screen.findByRole("button", { name: COPY.actions.addStep }));
    await waitFor(() => {
      expect(row(17)).not.toBeNull();
    });
    const input = screen.getByRole("textbox", { name: COPY.draft.stepLabel(3) });
    fireEvent.change(input, { target: { value: "Plan documents and amendments" } });
    fireEvent.blur(input);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      text: "Plan documents and amendments",
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.draft.remove(5) }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "DELETE")).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.draft.submit }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/submit"))).toBe(true);
    });
    expect(calls.find((c) => c.path.endsWith("/submit"))?.body).toEqual({ row_version: 3 });
  });
});

describe("KNW-03 d · tailored on the Northwind engagement", () => {
  it("shows the engagement chip, the tailored and decided tags, and no removal", async () => {
    show("d");
    expect(
      await screen.findByText(COPY.tailored.chip("Northwind Robotics 401(k) Plan")),
    ).toBeTruthy();
    await waitFor(() => {
      expect(row(11)).not.toBeNull();
    });
    expect(row(11)?.textContent).toContain(
      "Tailored — rationale: no related-party transactions outside Northwind Robotics, Inc.",
    );
    expect(row(7)?.textContent).toContain("Decided 1.5% · Margaret Okonkwo");
    for (const n of [1, 3, 11]) {
      expect(screen.getByRole("button", { name: COPY.draft.remove(n) })).toHaveProperty(
        "disabled",
        true,
      );
    }
  });
});

describe("KNW-03 f · Fix in Knowledge from the 9:58 AM run", () => {
  it("lights BH-EBP-140 step 8 and quotes the run's error verbatim, as text", async () => {
    show("f");
    const banner = await waitFor(() => {
      const el = document.querySelector<HTMLElement>("[data-knw03='run-error']");
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    expect(banner.textContent).toBe(KNW03_RUN_ERROR);
    expect(banner.querySelector("a, b, strong, em, script")).toBeNull();
    await waitFor(() => {
      expect(row(8)?.hasAttribute("data-lit")).toBe(true);
    });
    const card = document.querySelector<HTMLElement>("[data-knw03='run-card']");
    expect(card?.textContent).toContain("Internal Control run failed · 9:58 AM");
    expect(card?.textContent).toContain("no evidence written");
    // Retry waits for P-09.
    expect(screen.queryByRole("button", { name: /Retry/u })).toBeNull();
  });
});
