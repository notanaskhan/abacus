// A-03-T11 (TASK-2613): AUD-11 a, b, d, the picker and the C-20 states in fixture mode, inside the
// AUD-02 cockpit. Row acceptance: "Fixture scenarios a, b and d render with all 25 names and the
// 13,813,400.00 + 746,600.00 = 14,560,000.00 tie, and the picker lists Participants and
// Distributions without counts for walled engagements." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_PARTICIPANTS } from "../../fixtures/seed/sampling";
import { newQueryClient } from "../../testing/support";
import { AUD11Frame } from "./artboard";
import { type Aud11State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud11State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD11Frame state={state} />
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

async function names(): Promise<string[]> {
  await waitFor(
    () => {
      expect(document.querySelectorAll("[data-aud11='items'] [data-item]")).toHaveLength(25);
    },
    { timeout: 6000 },
  );
  return Array.from(document.querySelectorAll("[data-aud11='items'] [data-item]")).map(
    (li) => li.querySelectorAll("span")[1]?.textContent ?? "",
  );
}

describe.each(["a", "b", "d"] as const)("AUD-11%s", (state) => {
  it("renders all 25 names in draw order and the W-3 tie", async () => {
    show(state);
    expect(await names()).toEqual(NORTHWIND_PARTICIPANTS.map(([name]) => name));
    const body = await drawn("[data-aud11='body']");
    expect(body.textContent).toContain("= W-3 Box 1 $13,813,400.00 + W-3 Box 12 D $746,600.00");
    expect(body.textContent).toContain("Census compensation $14,560,000.00");
    expect(body.querySelectorAll("[data-tie='tie']")).toHaveLength(2);
    expect(body.textContent).toContain("0x5E2A91");
    expect(body.textContent).toContain("Accrued sampler v2.3 · uniform without replacement");
  });
});

describe("AUD-11 states", () => {
  it("a: Version 2 approved by Hannah Leclerc, Version 1 struck, Generate enabled", async () => {
    show("a");
    const v1 = await drawn("[data-version='1']");
    expect(v1.getAttribute("data-status")).toBe("superseded");
    expect(v1.textContent).toContain("completeness off $182,300.00");
    expect(v1.querySelector(".line-through")).not.toBeNull();
    const v2 = await drawn("[data-version='2']");
    expect(v2.textContent).toContain("Approved");
    expect(v2.textContent).toContain("HL");
    const generate = screen.getByRole<HTMLButtonElement>("button", {
      name: "Generate item requests (25 × 5)…",
    });
    expect(generate.disabled).toBe(false);
  });

  it("b: Prepared · MD, no approval chip, Generate disabled with its tooltip", async () => {
    show("b");
    const v2 = await drawn("[data-version='2']");
    expect(v2.textContent).toContain("Prepared · MD");
    expect(v2.textContent).not.toContain("Approved");
    const generate = screen.getByRole<HTMLButtonElement>("button", {
      name: "Generate item requests (25 × 5)…",
    });
    expect(generate.disabled).toBe(true);
    const wrapper = await drawn("[data-aud11='generate-disabled']");
    fireEvent.focus(wrapper);
    await waitFor(() => {
      expect(
        screen.getAllByText("A manager must approve the sample first").length,
      ).toBeGreaterThan(0);
    });
  });

  it("d: size 20 shows the amber banner and Save waits for a rationale", async () => {
    show("d");
    const banner = await drawn("[data-aud11='override']");
    expect(banner.textContent).toBe(
      "Size below methodology (25). Needs manager approval and a rationale.",
    );
    const save = screen.getByRole<HTMLButtonElement>("button", { name: "Save and draw" });
    expect(save.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Rationale (required)"), {
      target: { value: "Plan has 412 participants; 20 meets the firm's minimum for low RMM." },
    });
    expect(save.disabled).toBe(false);
  });

  it("picker: Participants and Distributions with size, population and status", async () => {
    show("picker");
    await names();
    const picker = screen.getByRole("button", { name: /Sample set/u });
    expect(picker.textContent).toContain("Participants · 25 of 412 · Approved");
    fireEvent.pointerDown(picker, { button: 0, pointerType: "mouse" });
    fireEvent.click(picker);
    await waitFor(() => {
      expect(screen.getAllByText("Distributions · 10 of 64 · Draft").length).toBeGreaterThan(0);
    });
  });

  it("off: the C-20 'not turned on' state, never a 404", async () => {
    show("off");
    await waitFor(
      () => {
        expect(
          document.querySelector("[data-state-kind='flag-off'], [data-view-state='flag-off']"),
        ).not.toBeNull();
      },
      { timeout: 6000 },
    );
    expect(document.querySelector("[data-aud11='body']")).toBeNull();
  });

  it("not allowed: a walled person sees no sample, no picker and no count", async () => {
    show("not_allowed");
    await waitFor(
      () => {
        expect(document.querySelector("[data-screen='AUD-11']")).not.toBeNull();
      },
      { timeout: 6000 },
    );
    await new Promise((r) => setTimeout(r, 300));
    expect(document.querySelector("[data-aud11='body']")).toBeNull();
    expect(screen.queryByText(/of 412/u)).toBeNull();
    expect(screen.queryByText(/Distributions/u)).toBeNull();
  });
});

// A-03-T15 (TASK-2713): c, e and f. Row acceptance: "State c shows 125 requests 100 to POR-03 25
// to POR-14 and creates them, state f foots 24 + 1,102 + 786 = 1,912 and 24 + 16 = 40, and SHL-14
// c offers only approved versions."
describe("AUD-11 c, e and f (A-03-T15)", () => {
  it("c: the sheet previews 125 · 100 · 25 from the server and creates them", async () => {
    show("c");
    const preview = await drawn("[data-aud11='generate-preview']");
    await waitFor(
      () => {
        expect(preview.textContent).toBe("125 requests · 100 to POR-03 · 25 to POR-14");
      },
      { timeout: 6000 },
    );
    expect(document.querySelectorAll("[data-aud11='template']")).toHaveLength(5);
    const recipients = await drawn("[data-aud11='recipients']");
    expect(recipients.textContent).toContain("Dana Kowalski sees 100 requests (POR-03)");
    expect(recipients.textContent).toContain("Sam Ortiz, Keystone sees 25 requests (POR-14)");
    expect(document.body.textContent).toContain("Generate item requests");
    const create = await screen.findByRole<HTMLButtonElement>("button", {
      name: "Create 125 requests",
    });
    await waitFor(() => {
      expect(create.disabled).toBe(false);
    });
    fireEvent.click(create);
    await waitFor(
      () => {
        expect(screen.queryByRole("button", { name: "Create 125 requests" })).toBeNull();
      },
      { timeout: 6000 },
    );
  });

  it("e: a person's draw reads Drawing, polls …/draw and shows the rows drawn so far", async () => {
    show("e");
    const label = await drawn("[data-aud11='drawing']");
    expect(label.textContent).toBe("Drawing");
    await waitFor(
      () => {
        expect(document.querySelectorAll("[data-aud11='drawn'] [data-item]")).toHaveLength(8);
      },
      { timeout: 6000 },
    );
    expect(document.body.textContent).toContain("8 of 25 drawn");
    expect(document.querySelector("[data-aud11='items']")).toBeNull();
  });

  it("f: the ledger population and strata foot 24 + 1,102 + 786 = 1,912 and 24 + 16 = 40", async () => {
    show("f");
    const body = await drawn("[data-aud11='body']");
    await waitFor(() => {
      expect(body.textContent).toContain("NetSuite · Granite Peak Outdoor Supply");
    });
    expect(body.textContent).toContain("Disbursements Jul 1 – Sep 18, 2026");
    expect(body.textContent).toContain("1,912 payments");
    expect(body.textContent).toContain("24 + 16 = 40");
    expect(body.textContent).toContain("0x7C31B4");
    const strata = Array.from(document.querySelectorAll("[data-aud11='strata'] [data-stratum]"));
    expect(strata.map((r) => r.querySelectorAll("td")[2]?.textContent)).toEqual([
      "24",
      "1,102",
      "786",
    ]);
    expect(strata.map((r) => r.querySelectorAll("td")[3]?.textContent)).toEqual([
      "all tested",
      "16 random",
      "none",
    ]);
    expect(document.querySelector("[data-aud11='hr-tooltip']")).not.toBeNull();
  });
});
