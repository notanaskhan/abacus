// POR-15 · Governance room (R-02-T21). One test per artboard (a to f) on its fixture scenario, the
// not-allowed state (a management grant opens no room) and the 390 layout. Every letter, date and
// name is the API's; Acknowledge sends the hash of the letter read with an Idempotency-Key; the
// inquiry answers go through the questionnaire service at the version read.
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
import { POR15 } from ".";
import { COPY } from "./copy";
import { NOT_ALLOWED, OPENING, type Por15State, scenarios } from "./scenarios";

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
  calls: {
    method: string;
    path: string;
    body: unknown;
    key: string | null;
    ifMatch: string | null;
  }[];
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
          ifMatch: request.headers?.get("If-Match") ?? null,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR15 {...opening} mobile={mobile} />
    </QueryClientProvider>,
  );
  return seen;
}

const at = (state: Por15State, mobile = false): Seen =>
  show(scenarios[state], OPENING[state] ?? {}, mobile);

describe("POR-15 governance room", () => {
  it("a: the planning letter is new, two of three have acknowledged", async () => {
    at("a");
    expect(await screen.findByText("Benefits Committee")).toBeTruthy();
    expect(screen.getByText("Northwind Robotics 401(k) Plan · 2025 audit")).toBeTruthy();
    expect(await screen.findByText("Our responsibilities")).toBeTruthy();
    expect(screen.getByText("September 17, 2026")).toBeTruthy();
    expect(screen.getByText("Planning: September 14–18, 2026")).toBeTruthy();
    expect(screen.getByText("Margaret Okonkwo · Engagement Partner")).toBeTruthy();
    expect(screen.getByText(COPY.notYetAcknowledged)).toBeTruthy();
    expect(screen.getByText("Acknowledged Sep 19")).toBeTruthy();
    expect(screen.getByText("Acknowledged Sep 18")).toBeTruthy();
    expect(screen.getByText(COPY.ackLine)).toBeTruthy();
    expect(screen.getByText("Sent Sep 18")).toBeTruthy();
  });

  it("a: Acknowledge sends the hash of the letter read, with a key", async () => {
    const seen = at("a");
    fireEvent.click(await screen.findByRole("button", { name: COPY.acknowledge }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/acknowledge"))).toBe(
        true,
      );
    });
    const post = seen.calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ seen_hash: "fixture-planning-260-v1" });
    expect(post?.key).not.toBeNull();
  });

  it("a: Ask the auditor… posts a private question on the letter", async () => {
    const seen = at("a");
    fireEvent.click(await screen.findByRole("button", { name: COPY.askAuditor }));
    fireEvent.change(screen.getByLabelText(COPY.askAuditor), {
      target: { value: "Does the bridge letter cover December?" },
    });
    fireEvent.click(screen.getByRole("button", { name: COPY.send }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/questions"))).toBe(
        true,
      );
    });
  });

  it("b: acknowledged by the committee, no Acknowledge left", async () => {
    at("b");
    expect(await screen.findAllByText("Acknowledged by the committee · Sep 21")).not.toHaveLength(
      0,
    );
    expect(screen.queryByRole("button", { name: COPY.acknowledge })).toBeNull();
    expect(document.querySelectorAll("[data-member] [data-disc='done']")).toHaveLength(3);
  });

  it("c: the two private inquiries and Send answers through the questionnaire", async () => {
    const seen = at("c");
    const first = await screen.findByLabelText<HTMLTextAreaElement>(
      "Do you know of any actual, suspected or alleged fraud affecting the plan?",
    );
    expect(screen.getByText(COPY.privacy("Brightwater Hale"))).toBeTruthy();
    const send = screen.getByRole<HTMLButtonElement>("button", { name: COPY.sendAnswers });
    expect(send.disabled).toBe(true);
    fireEvent.change(first, { target: { value: "No." } });
    fireEvent.change(
      screen.getByLabelText(
        "How does the committee oversee the way management identifies and responds to fraud risks in the plan?",
      ),
      { target: { value: "Quarterly review with the plan administrator." } },
    );
    fireEvent.click(send);
    expect(await screen.findByText(COPY.answersSent)).toBeTruthy();
    const puts = seen.calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(2);
    expect(puts.every((p) => p.ifMatch === "0")).toBe(true);
    expect(seen.calls.some((c) => c.path.endsWith(":submit"))).toBe(true);
  });

  it("d: the internal control letter is new; the earlier two are acknowledged", async () => {
    at("d");
    expect(
      await screen.findByText("Significant deficiency — Remittance of participant contributions"),
    ).toBeTruthy();
    expect(screen.getByText(/December 26, 2025 payroll \(\$48,600\)/)).toBeTruthy();
    expect(screen.getByText("Sent Nov 20 · due Dec 8")).toBeTruthy();
    expect(screen.getByText("Sent · acknowledged")).toBeTruthy();
    expect(screen.getByRole("button", { name: COPY.acknowledge })).toBeTruthy();
  });

  it("e: Reports lists the report and the statements with Download", async () => {
    const seen = at("e");
    expect(await screen.findByText("Independent auditor's report")).toBeTruthy();
    expect(screen.getByText("Financial statements and supplemental schedules")).toBeTruthy();
    expect(screen.getByText(/14 pages/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: COPY.download })[1] as HTMLElement);
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/versions/5/download"))).toBe(true);
    });
  });

  it("f: nothing from your auditor yet", async () => {
    at("f");
    expect(await screen.findByText(COPY.empty)).toBeTruthy();
    expect(screen.getByText(COPY.emptyBody)).toBeTruthy();
  });

  it("not allowed: a management grant opens no room (DEC-93)", async () => {
    show(NOT_ALLOWED);
    expect(await screen.findByText(COPY.notOn)).toBeTruthy();
    expect(screen.queryByText("Our responsibilities")).toBeNull();
  });

  it("the reduced nav offers the room's three areas only", async () => {
    at("a");
    await screen.findByText("Our responsibilities");
    for (const label of [COPY.communications, COPY.reports, COPY.questions]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    for (const label of ["Documents", "Approvals", "Sign", "Messages"]) {
      expect(screen.queryByRole("link", { name: label })).toBeNull();
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
  });

  it("390: the segmented control and a full-width Acknowledge", async () => {
    at("a", true);
    expect(await screen.findByRole("tablist", { name: "Benefits Committee" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: COPY.acknowledge })).toBeTruthy();
  });

  it("no banned word: the product, the agent, thresholds or materiality", async () => {
    at("a");
    await screen.findByText("Our responsibilities");
    expect(document.body.textContent).not.toMatch(/Accrued|agent|threshold|materiality|SAS 114/i);
  });
});
