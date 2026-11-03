// A-06-T18: AUD-15 a–g in fixture mode. Row acceptance: "Every AUD-15 artboard renders from its
// scenario, the severity picker is read-only with Reserved to Engagement Partner for everyone but
// Margaret Okonkwo, and the chip click lights the PayGrid Dec 26 row." Words are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { newQueryClient } from "../../testing/support";
import { FindingsRegister } from ".";
import { type Aud15State, SELECTED, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud15State): void {
  restore = installFixtureMode(scenarios[state]);
  const initial = SELECTED[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <FindingsRegister
        auditId={NORTHWIND_AUDIT}
        {...(initial === undefined ? {} : { initialRef: initial })}
      />
    </QueryClientProvider>,
  );
}

async function detail(ref: string): Promise<HTMLElement> {
  return waitFor(() => {
    const el = document.querySelector<HTMLElement>(`[data-aud15='detail'][data-finding='${ref}']`);
    expect(el).not.toBeNull();
    return el as HTMLElement;
  });
}

function picker(): HTMLButtonElement {
  const el = document.querySelector<HTMLButtonElement>("[data-aud15='severity-picker']");
  if (el === null) throw new Error("no severity picker");
  return el;
}

describe.each(STATES)("AUD-15 %s", (state) => {
  it("renders from its scenario", async () => {
    show(state);
    await waitFor(() => {
      expect(document.querySelector("[data-screen='AUD-15']")).not.toBeNull();
    });
    if (state === "g") {
      await waitFor(() => {
        expect(document.body.textContent).toContain("No findings yet.");
      });
      expect(document.body.textContent).toContain(
        "Exceptions from testing and agent runs appear here.",
      );
      return;
    }
    await detail(SELECTED[state] ?? "F-01");
  });
});

describe("AUD-15 queue", () => {
  it("bands 9 findings 1 + 2 + 1 + 5 in severity order", async () => {
    show("a");
    await detail("F-01");
    const text = document.body.textContent;
    const order = [
      "Significant deficiency",
      "Deficiency",
      "Exception for resolution",
      "Misstatements",
    ];
    const at = order.map((label) => text.indexOf(label));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((x, y) => x - y)).toEqual(at);
    expect(text).toContain("Proposed · Control activities · EBP-04");
  });

  it("Hide concluded drops F-02", async () => {
    show("a");
    await detail("F-01");
    expect(document.body.textContent).toContain("Keystone SOC 1 covers");
    fireEvent.click(document.querySelector("button[aria-pressed]") as HTMLElement);
    await waitFor(() => {
      expect(document.body.textContent).not.toContain("Keystone SOC 1 covers");
    });
  });
});

describe("AUD-15 severity is the engagement partner's", () => {
  it.each(["a", "d", "e"] as const)(
    "%s: Hannah's picker is read-only, Reserved to Engagement Partner",
    async (state) => {
      show(state);
      await detail(SELECTED[state] ?? "F-01");
      if (state === "e") {
        expect(document.querySelector("[data-aud15='severity-picker']")).toBeNull();
        return;
      }
      expect(picker().disabled).toBe(true);
      expect(picker().getAttribute("title")).toBe("Reserved to Engagement Partner");
      expect(document.body.textContent).not.toContain("Conclude severity…");
    },
  );

  it("b: Margaret's picker is live and her footer reads Conclude severity…", async () => {
    show("b");
    await detail("F-01");
    await waitFor(() => {
      expect(picker().disabled).toBe(false);
    });
    expect(picker().getAttribute("title")).toBeNull();
    expect(document.body.textContent).toContain("Conclude severity…");
  });

  it("a: Hannah requests the partner's decision", async () => {
    show("a");
    await detail("F-01");
    expect(document.body.textContent).toContain("Request partner decision…");
    expect(document.body.textContent).toContain("Convert to misstatement…");
    expect(document.body.textContent).toContain("Mark Not Applicable");
  });

  it("c: concluded by Margaret Okonkwo, Proposed gone", async () => {
    show("c");
    await detail("F-01");
    await waitFor(() => {
      expect(document.querySelector("[data-aud15='concluded']")?.textContent).toContain(
        "Concluded by Margaret Okonkwo",
      );
    });
    expect(document.body.textContent).toContain("Add to AU-C 265 letter");
  });

  it("d: F-01 reads Communicated", async () => {
    show("d");
    const el = await detail("F-01");
    expect(el.textContent).toContain("Communicated");
  });
});

describe("AUD-15 detail states", () => {
  it("a: Why This Was Surfaced carries the olive check disc and the agent's reasoning", async () => {
    show("a");
    const el = await detail("F-01");
    expect(el.textContent).toContain("Why This Was Surfaced");
    expect(el.textContent).toContain("9 business days after payday");
    expect(el.textContent).toContain("$48,600.00 (19.3% of overall materiality $252,200)");
  });

  it("e: F-07's projection reads 35,267 → 35,300, Mean per item", async () => {
    show("e");
    const el = await detail("F-07");
    expect(el.querySelector("[data-aud15='projection']")?.textContent).toContain(
      "35,267 → 35,300",
    );
    expect(el.textContent).toContain("Mean per item");
  });

  it("f: F-04's footer is Resolve, Convert to deficiency…, Mark Not Applicable", async () => {
    show("f");
    await detail("F-04");
    const footer = await waitFor(() => {
      const el = document.querySelector("[data-aud15='footer']");
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    expect([...footer.querySelectorAll("button")].map((b) => b.textContent.trim())).toEqual([
      "Resolve",
      "Convert to deficiency…",
      "Mark Not Applicable",
    ]);
  });
});

describe("AUD-15 evidence", () => {
  it("a: the file chip lights the PayGrid Dec 26 row", async () => {
    show("a");
    await detail("F-01");
    const chip = await waitFor(() => {
      const el = document.querySelector<HTMLElement>("[data-aud15='file-chip']");
      expect(el).not.toBeNull();
      return el as HTMLElement;
    });
    expect(chip.textContent).toContain("PayGrid Contribution Detail 2025.xlsx");
    expect(document.querySelector("[data-remittance='2025-12-26'][data-lit]")).toBeNull();
    fireEvent.click(chip);
    await waitFor(() => {
      expect(document.querySelector("[data-remittance='2025-12-26'][data-lit]")).not.toBeNull();
    });
  });
});
