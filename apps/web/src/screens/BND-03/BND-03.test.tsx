// T-03-T09 (TASK-3276): BND-03 a and e in fixture mode. Row acceptance: "BND-03a and BND-03e render in
// fixture mode with counts footing to 9, 4 and 8 of 9, and the dock shows no tag, banner, helper or
// toggle." Words are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { BND03_QUESTIONNAIRE } from "../../fixtures/seed/bnd03";
import { newQueryClient } from "../../testing/support";
import { QuestionnaireEditor } from "./Editor";
import { type Bnd03State, SECTION_OF, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Bnd03State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <QuestionnaireEditor questionnaireId={BND03_QUESTIONNAIRE} section={SECTION_OF[state]} />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("BND-03", () => {
  it("a: counts foot to 9 questions, 4 follow-ups and 8 of 9 answered", async () => {
    show("a");
    const rail = await drawn("[data-bnd03='rail']");
    expect(rail.querySelector("[data-bnd03='answered']")?.textContent).toContain(
      "8 of 9 · Claire Feld · last answer Sep 9",
    );
    expect(rail.querySelector("[data-logic='follow-ups']")?.textContent).toBe(
      "4 conditional follow-ups",
    );
    expect(rail.querySelector("[data-logic='review-points']")?.textContent).toContain(
      "1 review point raised",
    );
    expect(rail.textContent).toContain("1040 organizer v6");
    expect(document.querySelectorAll("[data-question]").length).toBe(9);
    const q5 = await drawn("[data-question='q5'][data-expanded='true']");
    expect(q5.querySelectorAll("[data-follow-up]").length).toBe(2);
    expect(q5.querySelector("[data-helper='make-required']")?.textContent).toBe(
      "Make required — this answer created the open request 'estimated payment confirmations'",
    );
    expect(
      document.querySelector("[data-question='q2'] [data-banner='review-point']")?.textContent,
    ).toContain("Confirm full-year NYC residency for the IT-201 resident tax");
    expect(document.querySelector("[data-question='q9'] [data-answer]")?.textContent).toBe("—");
  });

  it("a: the preview dock shows no tag, banner, helper or toggle", async () => {
    show("a");
    const dock = await drawn("[data-bnd03='dock']");
    await waitFor(() => {
      expect(dock.querySelector("[data-client-question='q5']")).not.toBeNull();
    });
    expect(dock.textContent).toContain("Brightwater Hale");
    expect(dock.textContent).toContain("Did you make 2025 estimated tax payments?");
    expect(dock.querySelector("[data-client-follow-up='q5b']")?.textContent).toContain("Upload…");
    expect(
      dock.querySelector("[data-type], [data-banner], [data-helper], [role='switch']"),
    ).toBeNull();
    expect(dock.textContent).not.toContain("internal only");
    expect(dock.textContent).not.toContain("Accrued");
  });

  it("e: an empty section reads No questions in this section.", async () => {
    show("e");
    const canvas = await drawn("[data-bnd03='canvas']");
    await waitFor(() => {
      expect(canvas.textContent).toContain("No questions in this section.");
    });
    expect(canvas.querySelectorAll("[data-question]").length).toBe(0);
  });

  it("off: questionnaires.editor off draws C-20", async () => {
    show("off");
    await waitFor(
      () => {
        expect(document.body.textContent).toContain("not turned on");
      },
      { timeout: 6000 },
    );
  });
});
