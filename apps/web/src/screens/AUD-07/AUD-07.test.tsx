// A-04-T10 (TASK-2801): AUD-07 a–e and the C-20 states in fixture mode, inside the AUD-02 cockpit.
// Row acceptance: "AUD-07 a-e render from fixtures at Tier C, Hannah's radios are disabled under
// the banner, and no threshold is computed in the browser." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AUD07Frame } from "./artboard";
import { percentText, stepped } from "./Materiality";
import { type Aud07State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.restoreAllMocks();
});

function show(state: Aud07State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD07Frame state={state} />
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

const figure = (name: string): string =>
  document.querySelector(`[data-aud07='thresholds'] [data-figure='${name}']`)?.textContent ?? "";

describe.each(["a", "b", "c", "d", "e"] as const)("AUD-07%s", (state) => {
  it("draws the R2 benchmark table without $ and the prior-year line", async () => {
    show(state);
    const table = await drawn("[data-aud07='benchmarks']");
    expect(table.textContent).toContain("Benchmarks — unadjusted at 12/31/2025");
    expect(table.textContent).not.toContain("$");
    const na = await drawn("[data-benchmark='net_assets']");
    for (const v of [
      "16,812,400",
      "14,228,500",
      "11,902,700",
      "1.0%–2.0%",
      "168,100",
      "336,200",
    ]) {
      expect(na.textContent).toContain(v);
    }
    expect(na.textContent).toContain("Overall");
    const c = await drawn("[data-benchmark='contributions']");
    for (const v of ["1,318,300", "1,142,600", "1,016,800", "3.0%–5.0%", "39,500", "65,900"]) {
      expect(c.textContent).toContain(v);
    }
    const bp = await drawn("[data-benchmark='benefit_payments']");
    for (const v of ["812,650", "694,300", "588,900", "24,400", "40,600"]) {
      expect(bp.textContent).toContain(v);
    }
    expect(table.querySelectorAll("svg[role='img']")).toHaveLength(3);
    expect((await drawn("[data-aud07='used']")).textContent).toBe(
      "Overall materiality used: PY2024 1.5% = 213,400 · PY2023 1.5% = 178,500 (final, audited).",
    );
    expect((await drawn("[data-aud07='caption']")).textContent).toContain(
      "net assets grew 18.2% on PY2024",
    );
  });
});

describe("AUD-07 states", () => {
  it("a: Margaret's card, 1.5% preselected with the agent's tag, Decide waits for a rationale", async () => {
    show("a");
    const card = await drawn("[data-aud07='decision']");
    expect(card.textContent).toContain("Which planning materiality should this audit use?");
    expect(card.textContent).toContain("Reserved to Engagement Partner");
    expect(card.querySelector("[data-option='rate_1_5'][data-checked]")).not.toBeNull();
    expect(card.querySelector("[data-option='rate_1_5'] [data-recommended]")?.textContent).toBe(
      "Recommended by Accrued Agent",
    );
    expect(card.textContent).toContain("1.0% of net assets — $168,100");
    expect(card.textContent).toContain("Another rate within 1.0%–2.0%…");
    for (const chip of ["BH-EBP-110 step 7", "AU-C 320", "AU-C 450", "Trial Balance · 9:26 AM"]) {
      expect(card.textContent).toContain(chip);
    }
    const decide = screen.getByRole<HTMLButtonElement>("button", { name: /Decide/u });
    expect(decide.disabled).toBe(true);
    expect(figure("overall")).toBe("$252,200");
    expect(figure("pm")).toBe("$189,150");
    expect(figure("ct")).toBe("$12,610");
    const v1 = await drawn("[data-version='1']");
    expect(v1.querySelector("[data-line]")?.textContent).toBe(
      "Version 1 · Proposed · Marcus Delaney via Agent · Sep 14 9:27 AM · 1.5% recommended",
    );
    expect(v1.textContent).toContain("Current");
  });

  it("a: choosing 1.0% shows the option's figures from the card, not the browser", async () => {
    show("a");
    const low = await drawn("[data-option='rate_1_0'] [role='radio']");
    fireEvent.click(low);
    await waitFor(() => {
      expect(figure("overall")).toBe("$168,100");
    });
    expect(figure("pm")).toBe("$126,075");
    expect(figure("ct")).toBe("$8,405");
  });

  it("a: the slider asks POST …/materiality/preview and shows what it answers", async () => {
    show("a");
    // The fixture client's own fetch answers, so the request is read off the client.
    const asked: string[] = [];
    const record = (request: Request): Request => {
      asked.push(`${request.method} ${request.url}`);
      return request;
    };
    client.interceptors.request.use(record);
    const slider = (await drawn("[data-aud07='slider']")) as HTMLInputElement;
    // The slider is the reserved partner's only once her card has loaded.
    await waitFor(() => {
      expect(slider.disabled).toBe(false);
    });
    fireEvent.change(slider, { target: { value: "2.0" } });
    await waitFor(() => {
      expect(figure("overall")).toBe("$336,200");
    });
    client.interceptors.request.eject(record);
    expect(asked.some((r) => r.startsWith("POST ") && r.includes("/materiality/preview"))).toBe(
      true,
    );
    expect(document.querySelector("[data-option='custom'][data-checked]")).not.toBeNull();
  });

  it("a: Decide with a rationale moves the card to decided", async () => {
    show("a");
    fireEvent.change(await drawn("[data-aud07='decision'] textarea"), {
      target: { value: "Recurring plan, clean PY2024, certified investments; mid-range rate." },
    });
    const decide = screen.getByRole<HTMLButtonElement>("button", { name: /Decide/u });
    await waitFor(() => {
      expect(decide.disabled).toBe(false);
    });
    fireEvent.click(decide);
    expect((await drawn("[data-decision-line]")).textContent).toContain(
      "Decided by Margaret Okonkwo",
    );
  });

  it("b: Hannah's radios are disabled under the banner, Remind Margaret, no Decide", async () => {
    show("b");
    const card = await drawn("[data-aud07='decision']");
    expect((await drawn("[data-aud07='banner']")).textContent).toBe(
      "Only the engagement partner can decide materiality.",
    );
    const radios = card.querySelectorAll<HTMLButtonElement>("[role='radio']");
    expect(radios).toHaveLength(3);
    for (const r of radios) expect(r.disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Remind Margaret" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Decide/u })).toBeNull();
    expect(card.querySelector("textarea")).toBeNull();
    expect((await drawn("[data-aud07='slider']")).hasAttribute("disabled")).toBe(true);
  });

  it("c: the card collapses to the decided line; v2 current, v1 superseded", async () => {
    show("c");
    expect((await drawn("[data-decision-line]")).textContent).toBe(
      "Decided by Margaret Okonkwo · Sep 14 11:12 AM · 1.5% of net assets = $252,200",
    );
    const body = await drawn("[data-aud07='body']");
    expect(body.textContent).toContain(
      "Recurring plan, clean PY2024, certified investments; mid-range rate.",
    );
    expect(screen.getByText("Version 2 · Decided")).toBeTruthy();
    expect((await drawn("[data-version='2']")).textContent).toContain(
      "Version 2 · Decided · Margaret Okonkwo · 11:12 AM · PM $189,150 · CT $12,610",
    );
    expect((await drawn("[data-version='1']")).getAttribute("data-status")).toBe("superseded");
  });

  it("d: reassessed at final, 252,900, +700 (0.3%), no change", async () => {
    show("d");
    const r = await drawn("[data-aud07='reassessment']");
    expect(r.textContent).toContain("Reassessment at final");
    expect(r.textContent).toContain("16,861,000");
    expect(r.textContent).toContain("$252,900");
    expect(r.textContent).toContain("$700 (0.3%)");
    expect((await drawn("[data-aud07='conclusion']")).textContent).toBe(
      "No change. Version 2 thresholds stand; work performed at PM $189,150 remains appropriate.",
    );
    expect((await drawn("[data-version='3']")).textContent).toContain(
      "Version 3 · Reassessed at final · Margaret Okonkwo · Oct 6 · no change",
    );
    expect(figure("overall")).toBe("$252,200");
  });

  it("e: the Revised pill and the impact list", async () => {
    show("e");
    const r = await drawn("[data-aud07='reassessment']");
    expect(r.textContent).toContain("Revised");
    const impact = await drawn("[data-aud07='impact']");
    expect(impact.textContent).toContain("Sample Selection");
    expect(impact.textContent).toContain("Marcus Delaney");
  });

  it("the dock shows the recommender's reasons as agent text and the SHL-11 e card", async () => {
    show("a");
    const dock = await drawn("[data-aud07='dock']");
    expect(dock.textContent).toContain("Waiting on Margaret Okonkwo since 9:27 AM");
    const agent = dock.querySelectorAll("[data-actor='agent']");
    expect(agent).toHaveLength(3);
    expect(agent[2]?.textContent).toBe(
      "1.5% keeps planning materiality in line with the rate used in both prior years.",
    );
    expect(await drawn("[data-aud07='dock'] [data-decision-inline='dock']")).toBeTruthy();
  });

  it("no agent-owned element carries a gate verb", async () => {
    show("a");
    const dock = await drawn("[data-aud07='dock']");
    for (const el of dock.querySelectorAll("[data-actor='agent']")) {
      expect(el.textContent).not.toMatch(/\b(Approve|Sign off|Release|Send|Post|Decide)\b/u);
    }
  });

  it("loading, error and walled", async () => {
    show("loading");
    await drawn(
      "[data-screen='AUD-07'] [aria-busy='true'], [data-screen='AUD-07'] [data-state='loading']",
    );
    cleanup();
    restore?.();
    show("error");
    await drawn(
      "[data-screen='AUD-07'] [role='alert'], [data-screen='AUD-07'] [data-view-state='error']",
    );
    cleanup();
    restore?.();
    show("not_allowed");
    await waitFor(() => {
      expect(document.querySelector("[data-aud07='body']")).toBeNull();
    });
  });
});

describe("AUD-07 helpers", () => {
  it("formats the server's percents as the handoff writes them", () => {
    expect(percentText("1.5000", true)).toBe("1.5");
    expect(percentText("1.0000", true)).toBe("1.0");
    expect(percentText("75.0000")).toBe("75");
    expect(percentText("1.3700", true)).toBe("1.37");
  });

  it("steps the control's own input, never a threshold", () => {
    expect(stepped("75", "5", false)).toBe("70");
    expect(stepped("1.5", "0.1", true)).toBe("1.6");
  });
});
