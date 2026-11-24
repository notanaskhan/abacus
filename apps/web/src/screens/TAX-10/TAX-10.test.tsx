// T-08-T22 (TASK-8936; DEC-5938): TAX-10 a–e and x1 from the Python slice. Acceptance: "TAX-10 a-e
// render from data, Accept is offered only to the reviewer, and the agents-off state lets Samuel
// Ito type an explanation."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { TAX10, type TAX10Props } from "./index";
import { TAX10_RETURN_ID, type Tax10ScenarioState, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(sc: Scenario, props: Partial<TAX10Props> = {}): void {
  restore = installFixtureMode(sc);
  renderRoutes([{ path: "/", component: () => <TAX10 returnId={TAX10_RETURN_ID} {...props} /> }]);
}

const state = (s: Tax10ScenarioState, props: Partial<TAX10Props> = {}): void => {
  show(scenarios[s], props);
};

async function table(): Promise<HTMLElement> {
  return waitFor(() => {
    const t = document.querySelector<HTMLElement>("[data-tax10='statement']");
    expect(t?.querySelectorAll("[data-line]").length).toBeGreaterThan(0);
    return t as HTMLElement;
  });
}

const row = (t: HTMLElement, key: string): HTMLElement =>
  t.querySelector(`[data-line='${key}']`) as HTMLElement;

describe("TAX-10 Two-year comparison", () => {
  it("TAX-10a default: the statement, the tally and Sch A 11 awaiting acceptance", async () => {
    state("a");
    const t = await table();
    expect(t.querySelectorAll("[data-line]").length).toBe(22);
    expect(row(t, "1040.1a").textContent).toContain("251,000");
    expect(row(t, "1040.1a").textContent).toContain("6.9%");
    expect(row(t, "scha.8a").textContent).toContain("(720)");
    expect(row(t, "scha.8a").textContent).toContain("(3.8%)");
    expect(row(t, "1040.34").getAttribute("data-total")).toBe("grand");
    expect(row(t, "1040.34").textContent).toContain("(921)");
    expect(row(t, "1040.3a").querySelector("[data-explained='accepted']")?.textContent).toContain(
      "Accepted · SI",
    );
    expect(row(t, "scha.11").querySelector("[data-explained='proposed']")?.textContent).toContain(
      "new gift: Mercer Hill Health Foundation 2,500",
    );
    const body = document.body.textContent;
    expect(body).toContain("598,030 (+8.4%)");
    expect(body).toContain("123,223 (+11.2%)");
    expect(body).toContain("253 (2024: 1,174)");
    expect(body).toContain("7 of 8");
  });

  it("TAX-10 acceptance: Accept is offered only to the reviewer (the server's two_year.accept)", async () => {
    state("a");
    const t = await table();
    const accepts = within(t).getAllByRole("button", { name: C.accept });
    expect(accepts).toHaveLength(1);
    expect(row(t, "scha.11").contains(accepts[0] as HTMLElement)).toBe(true);
    fireEvent.click(accepts[0] as HTMLElement);
    await waitFor(() => {
      expect(
        row(t, "scha.11").querySelector("[data-explained='accepted']")?.textContent,
      ).toContain("Accepted · SI 10:07 AM");
    });
  });

  it("TAX-10b over threshold: only the 8 flagged lines", async () => {
    state("b", { filter: "over_threshold" });
    const t = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-tax10='statement']");
      expect(found?.querySelectorAll("[data-line]").length).toBe(8);
      return found as HTMLElement;
    });
    expect([...t.querySelectorAll("[data-line]")].map((r) => r.getAttribute("data-line"))).toEqual(
      ["1040.3a", "1040.3b", "scha.11", "1040.16", "1040.23", "1040.24", "sch3.10", "1040.33"],
    );
  });

  it("TAX-10c all accepted: 8 of 8 and no Accept left", async () => {
    state("c");
    const t = await table();
    expect(document.body.textContent).toContain("8 of 8");
    expect(within(t).queryByRole("button", { name: C.accept })).toBeNull();
    expect(t.querySelectorAll("[data-explained='accepted']").length).toBe(8);
  });

  it("TAX-10d unexplained: every flagged line asks for Explain…", async () => {
    state("d");
    const t = await table();
    expect(within(t).getAllByRole("button", { name: C.explain })).toHaveLength(8);
    expect(document.body.textContent).toContain("0 of 8");
  });

  it("TAX-10e agent explaining: a spinner in each flagged cell, no Explain…", async () => {
    state("e");
    const t = await table();
    expect(within(t).getAllByText(C.explaining).length).toBe(8);
    expect(within(t).queryByRole("button", { name: C.explain })).toBeNull();
  });

  it("TAX-10 acceptance: agents off (x1) lets Samuel Ito type an explanation", async () => {
    state("x1");
    const t = await table();
    expect(within(t).queryByRole("button", { name: C.explain })).toBeNull();
    const line = row(t, "scha.11");
    expect(line.textContent).toContain(C.agentsOff.agents_off_for_taxpayer);
    fireEvent.click(within(line).getByRole("button", { name: C.edit }));
    fireEvent.change(within(line).getByRole("textbox"), {
      target: { value: "Six 2025 receipts total 12,500." },
    });
    fireEvent.click(within(line).getByRole("button", { name: C.save }));
    await waitFor(() => {
      expect(row(t, "scha.11").textContent).toContain("Six 2025 receipts total 12,500.");
    });
  });

  it("TAX-10 no explained variance reads red", async () => {
    state("c");
    const t = await table();
    expect(t.querySelector(".text-red")).toBeNull();
  });

  it("TAX-10 the threshold names its source", async () => {
    state("a");
    await table();
    expect(document.querySelector("[data-tax10='threshold']")?.textContent).toContain(
      "> $1,000 and 10%",
    );
  });
});
