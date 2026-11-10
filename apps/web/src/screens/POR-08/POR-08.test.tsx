// POR-08 · Approvals (R-02-T19). One test per artboard (a, a2, b, c, d, e, e2, f) on its fixture
// scenario, the flag-off state and the 390 layout. Every figure is the API's; each decision sends
// the seen_hash it read and an Idempotency-Key; the browser adds nothing up (22,250 is the API's).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { POR08 } from ".";
import { COPY } from "./copy";
import { FLAG_OFF, OPENING, type Por08State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => undefined });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown; key: string | null }[];
}

function show(scenario: Scenario, opening: Record<string, unknown> = {}, mobile = false): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
          key: request.headers?.get("Idempotency-Key") ?? null,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR08 {...opening} mobile={mobile} />
    </QueryClientProvider>,
  );
  return seen;
}

const at = (state: Por08State, mobile = false): Seen =>
  show(scenarios[state], OPENING[state] ?? {}, mobile);

function posts(seen: Seen): Seen["calls"] {
  return seen.calls.filter((c) => c.method === "POST");
}

describe("POR-08 approvals", () => {
  it("a: the August package waits, with its parts, highlights and legend", async () => {
    at("a");
    expect(await screen.findByText("August 2026 financial statements")).toBeTruthy();
    expect(await screen.findByText("5 parts")).toBeTruthy();
    for (const part of ["Balance sheet", "Income statement", "AR & AP aging", "Commentary"]) {
      expect(screen.getByText(part)).toBeTruthy();
    }
    expect(screen.getByText(/Revenue rose 4.5% to \$214,600/)).toBeTruthy();
    expect(
      screen.getByText("Prepared by Brightwater Hale. No assurance is provided."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.approve })).toBeTruthy();
  });

  it("a: the six posted entries are read-only, whole dollars, and the 14,900 one opens its lines", async () => {
    at("a");
    expect(await screen.findByText("Entries posted for August (6)")).toBeTruthy();
    for (const amount of ["$11,860", "$700", "$2,140", "$5,320", "$14,900", "$380"]) {
      expect(screen.getByText(amount)).toBeTruthy();
    }
    expect(await screen.findByText("Inventory — Green Coffee")).toBeTruthy();
    expect(screen.getByText("$12,600.00")).toBeTruthy();
    expect(screen.getAllByText("$14,900.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Receiving log — Aug 28 (1,800 lb green coffee)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.accept })).toBeNull();
    expect(screen.getByRole("button", { name: COPY.askEntry })).toBeTruthy();
  });

  it("a: the rail counts are the server's", async () => {
    at("a");
    await screen.findByText("August 2026 financial statements");
    const waiting = document.querySelector("[data-filter='waiting']");
    expect(waiting?.textContent).toContain("1");
    expect(document.querySelector("[data-filter='posted']")?.textContent).toContain(
      "Entries posted for August6",
    );
    expect(screen.getByText("Coming next")).toBeTruthy();
    expect(screen.getAllByText("September 2026 Close").length).toBeGreaterThan(0);
  });

  it("a2: the confirm approves with the hash that was seen and a key", async () => {
    const seen = at("a2");
    expect(await screen.findByText(/Approve the August 2026 financial statements/)).toBeTruthy();
    const confirm = screen.getAllByRole("button", { name: COPY.approve }).at(-1);
    if (confirm === undefined) throw new Error("no confirm");
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(posts(seen).some((c) => c.path.endsWith("/decide"))).toBe(true);
    });
    const post = posts(seen)[0];
    expect(post?.body).toEqual({
      decision: "approve",
      seen_hash: "fixture-copperleaf-2026-08-v1",
    });
    expect(post?.key).not.toBeNull();
  });

  it("b: approved by Tess Moreno, nothing left to decide", async () => {
    at("b");
    expect(await screen.findByText(/Approved by Tess Moreno · Sep 15, 8:42 AM/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: COPY.approve })).toBeNull();
    expect(
      document.querySelector("[data-approval='fs_package'] [data-disc='done']"),
    ).not.toBeNull();
  });

  it("c: the decline sheet offers the three reasons and sends the code", async () => {
    const seen = show(scenarios.a, { overlay: "decline" });
    // The sheet opens once the package's detail (its seen_hash) has loaded.
    await screen.findByText("5 parts", {}, { timeout: 3000 });
    expect(await screen.findByText(COPY.reasons.number_looks_wrong)).toBeTruthy();
    expect(screen.getByText(COPY.reasons.something_missing)).toBeTruthy();
    expect(screen.getByText(COPY.reasons.other)).toBeTruthy();
    fireEvent.click(screen.getByLabelText(COPY.reasons.number_looks_wrong));
    const send = screen.getAllByRole("button", { name: COPY.declineTitle }).at(-1);
    if (send === undefined) throw new Error("no decline");
    fireEvent.click(send);
    await waitFor(() => {
      expect(posts(seen).length).toBe(1);
    });
    expect(posts(seen)[0]?.body).toMatchObject({
      decision: "decline",
      reason_code: "number_looks_wrong",
    });
  });

  it("c: the declined card reads its reason in red tint", async () => {
    show(scenarios.c);
    expect(await screen.findByText("Declined · A number looks wrong")).toBeTruthy();
  });

  it("d: Ask about this entry is prefilled and posts to the item's thread", async () => {
    const seen = at("d");
    const box = await screen.findByLabelText<HTMLTextAreaElement>(COPY.askEntry);
    expect(box.value).toBe("About: Accrued expenses $14,900.00 (August 2026 Close)");
    fireEvent.click(screen.getByRole("button", { name: COPY.send }));
    await waitFor(() => {
      expect(posts(seen).some((c) => c.path.endsWith("/questions"))).toBe(true);
    });
    expect(screen.getByText("Question sent Sep 14")).toBeTruthy();
  });

  it("e: Dana's four attest entries with Accept, Decline and Ask", async () => {
    const seen = at("e");
    expect(await screen.findByText(COPY.attestIntro)).toBeTruthy();
    for (const amount of ["$48,600.00", "$14,850.00", "$35,300.00", "$13,050.00"]) {
      expect(screen.getByText(amount)).toBeTruthy();
    }
    expect(screen.getAllByRole("button", { name: COPY.accept }).length).toBe(4);
    const aje1 = (await screen.findAllByText(/AJE-1/))[0];
    if (aje1 === undefined) throw new Error("no AJE-1");
    fireEvent.click(aje1);
    expect(await screen.findByText("Participant contributions")).toBeTruthy();
    expect(screen.getByText("$33,540.00")).toBeTruthy();
    await waitFor(() => {
      expect(
        screen.getAllByRole<HTMLButtonElement>("button", { name: COPY.accept })[0]?.disabled,
      ).toBe(false);
    });
    fireEvent.click(screen.getAllByRole("button", { name: COPY.accept })[0] as HTMLElement);
    await waitFor(() => {
      expect(posts(seen).some((c) => c.path.endsWith("/decide"))).toBe(true);
    });
    expect(posts(seen)[0]?.body).toEqual({
      decision: "accept",
      seen_hash: expect.stringMatching(/^fixture-/) as string,
    });
  });

  it("e2: the decisions read as recorded and 22,250 is acknowledged from the snapshot", async () => {
    const seen = at("e2");
    expect(await screen.findAllByText(/Accepted by Dana Kowalski · Sep 25/)).toHaveLength(2);
    expect(
      await screen.findByText("Not recorded · Sep 25 · Sponsor will correct under EPCRS in 2026"),
    ).toBeTruthy();
    expect(screen.getByText("Not recorded · Sep 25 · Recorded when invoiced")).toBeTruthy();
    expect(
      await screen.findByText(
        /would increase net assets by \$22,250\.00 in total \(\$35,300\.00 − \$13,050\.00\)/,
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.acknowledge }));
    await waitFor(() => {
      expect(posts(seen).some((c) => c.path.endsWith("/acknowledge"))).toBe(true);
    });
    // the client sends only what it saw: no figure
    expect(posts(seen)[0]?.body).toEqual({ seen_hash: "fixture-uncorrected-py2025" });
  });

  it("f: nothing to approve", async () => {
    at("f");
    expect(await screen.findByText(COPY.empty)).toBeTruthy();
    expect(
      screen.getByText(/will ask here when statements or an entry need your OK\./),
    ).toBeTruthy();
  });

  it("flag off: the designed state, never a 404 page", async () => {
    show(FLAG_OFF);
    expect(await screen.findByText(COPY.flagOff)).toBeTruthy();
  });

  it("390: the package reads Review required with a full-width Review", async () => {
    at("a", true);
    expect(await screen.findByText(COPY.reviewRequired)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.review }));
    expect(await screen.findByText("Balance sheet")).toBeTruthy();
  });

  it("no banned word: the product, the agent, thresholds, policy, materiality or Post", async () => {
    for (const state of ["a", "e", "e2"] as const) {
      at(state);
      await screen.findAllByRole("button");
      await waitFor(() => {
        expect(document.querySelector("[data-approval]")).not.toBeNull();
      });
      const text = document.body.textContent;
      // "Accrued expenses" and "Accrued administrative expenses" are entries' own names (CLS-07,
      // AUD-16), not the product's.
      expect(text).not.toMatch(
        /\bAccrued\b(?!\s+(?:administrative\s+)?expenses)|agent|threshold|materiality|policy|\bPost\b|SAS 114/i,
      );
      cleanup();
      restore?.();
    }
  });
});
