// ENG-04 · Engagement letter composer, part 1 (N-02-T34). Acceptance: "Scenario tests for a, b and
// c pass and switching clause 5 off strikes it and the redline pill reads 3." Each frame on its
// fixture scenario: the structure pane, the paper, the primary, and a toggle in Draft.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { LetterComposer } from ".";
import { type Eng04State, OPENS, freshScenario } from "./scenarios";

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

function show(state: Eng04State, opened: string[] = []): Call[] {
  const calls: Call[] = [];
  const scenario: Scenario = freshScenario(state);
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
  renderRoutes([
    {
      path: "/",
      component: () => (
        <LetterComposer
          engagementId={OPENS}
          engagementName="Ridgeline cost segregation & §754 analysis"
          onOpenEnvelope={(id) => opened.push(id)}
          height={700}
        />
      ),
    },
  ]);
  return calls;
}

const redline = () => document.querySelector<HTMLElement>("[data-redline]");

describe("ENG-04 a: partner approved", () => {
  it("shows the template, the approval and two non-standard clauses", async () => {
    show("a");
    expect(await screen.findByText("BH Tax Advisory Letter v4")).toBeTruthy();
    expect(screen.getByText("BH clauses 2026.1")).toBeTruthy();
    expect(screen.getByText("Partner approved")).toBeTruthy();
    expect(screen.getByText("Daniel Reyes · Sep 14, 8:32 AM")).toBeTruthy();
    expect(redline()?.textContent).toBe("2 non-standard clauses");
    expect(screen.queryByText("DRAFT")).toBeNull();
  });

  it("lists the variables from facts, with the reasons for those that do not apply", async () => {
    show("a");
    expect(await screen.findByText("$18,500 fixed")).toBeTruthy();
    expect(screen.getByText("50% on signature · 50% on Form 3115 delivery")).toBeTruthy();
    expect(
      screen.getByText("Est. $9,800 · billed by Tallgrass Cost Engineering, LLC"),
    ).toBeTruthy();
    expect(screen.getByText("CAS only")).toBeTruthy();
    expect(screen.getByText("attest clients only")).toBeTruthy();
    expect(screen.getByText("EBP audits only")).toBeTruthy();
    expect(screen.getByText("Sep 15, 2026")).toBeTruthy();
  });

  it("prints the fee the server computed and the engineer's fee apart", async () => {
    show("a");
    const fees = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-section='fees']");
      if (found === null) throw new Error("no fees section");
      return found;
    });
    expect(fees.textContent).toContain("A fixed fee of $18,500");
    expect(fees.textContent).toContain("billed $9,250");
    expect(fees.textContent).toContain("estimated at $9,800, directly.");
  });

  it("keeps §7216 consents as their own documents and links the missing one", async () => {
    show("a");
    expect(await screen.findByText("Signed Feb 6, 2026 · expires Feb 6, 2027")).toBeTruthy();
    expect(screen.getByText("Needs §7216 consent")).toBeTruthy();
    expect(
      screen.getByText(
        "Not on file. No Ridgeline return information goes to Tallgrass (POR-14) until it is signed.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("1 Owen Calder (client) · email code")).toBeTruthy();
    expect(screen.getByText("2 Daniel Reyes (firm countersignature)")).toBeTruthy();
  });

  it("sends for signature as the person and opens the C7 draft", async () => {
    const opened: string[] = [];
    const calls = show("a", opened);
    fireEvent.click(await screen.findByRole("button", { name: "Send for signature…" }));
    await waitFor(() => {
      expect(opened).toHaveLength(1);
    });
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/letter/send"))).toBe(true);
  });

  it("lights a variable row from the paper's citation marker", async () => {
    show("a");
    await screen.findByText("BH Tax Advisory Letter v4");
    const marker = document.querySelector<HTMLElement>("[data-cite='fee.summary']");
    expect(marker).not.toBeNull();
    if (marker !== null) fireEvent.mouseEnter(marker);
    await waitFor(() => {
      expect(document.querySelector("[data-lit='true']")?.textContent).toContain("$18,500 fixed");
    });
  });
});

describe("ENG-04 b: draft", () => {
  it("is watermarked and asks for partner approval", async () => {
    show("b");
    expect(await screen.findByText("DRAFT")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Request partner approval…" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Send for signature…" })).toBeNull();
  });

  it("switching clause 5 off strikes it and the redline pill reads 3", async () => {
    const calls = show("b");
    const toggle = await screen.findByRole("switch", { name: "Reliance on the engineer's study" });
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(redline()?.textContent).toBe("3 non-standard clauses");
    });
    const section = document.querySelector("[data-section='engineer-reliance']");
    expect(section?.getAttribute("data-struck")).toBe("true");
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.body).toMatchObject({
      clause_states: { "engineer-reliance": "off" },
      fees: { lines: [{ amount_cents: 650_000 }, { amount_cents: 1_200_000 }] },
    });
  });
});

describe("ENG-04 c: sent", () => {
  it("is read-only with 0 of 2 signed and View envelope", async () => {
    show("c");
    expect(await screen.findByText("Sent · 0 of 2 signed")).toBeTruthy();
    expect(screen.getByRole("button", { name: "View envelope ›" })).toBeTruthy();
    const clauses = screen.getByRole("region", { name: "Clauses" });
    for (const toggle of within(clauses).getAllByRole("switch")) {
      expect((toggle as HTMLButtonElement).disabled).toBe(true);
    }
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByText("DRAFT")).toBeNull();
  });
});
