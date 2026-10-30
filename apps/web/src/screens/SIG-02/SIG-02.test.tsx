// SIG-02 · Envelope builder, part 1 (N-02-T21). Acceptance: "Scenario tests for a, e and f pass
// and SMS code is never selectable on an e-file authorization." Each frame on its fixture
// scenario: the content, the gate sentence, the policy-disabled identity, reorder, Send.
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
import { EnvelopeBuilder } from ".";
import { OPENS, STATES, type Sig02State, scenarios } from "./scenarios";

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

function show(state: Sig02State): Call[] {
  const calls: Call[] = [];
  const scenario: Scenario = scenarios[state];
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
        <EnvelopeBuilder envelopeId={OPENS[state]} open onOpenChange={() => undefined} />
      ),
    },
  ]);
  return calls;
}

const send = () => screen.findByRole<HTMLButtonElement>("button", { name: /^Send$/u });

async function openIdentity(signer: RegExp): Promise<HTMLElement> {
  await screen.findByText(signer, { selector: "[data-signer] span" });
  const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-signer]"));
  const row = rows.find((r) => signer.test(r.textContent));
  if (row === undefined) throw new Error(`no signer row for ${String(signer)}`);
  const trigger = within(row).getByRole("button", { name: /^Identity/u });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  return screen.findByRole("menu");
}

describe("SIG-02 builder", () => {
  it("builds a, e and f", () => {
    expect(STATES).toEqual(["a", "e", "f"]);
    expect(scenarios.a.persona).toBe("grace-holloway");
  });

  it("a: Harborview's 8879-PE, the checks, the signers, the gate and Send", async () => {
    show("a");
    expect(
      (await screen.findAllByText("Form 8879-PE · TY2025 · Harborview Dental Properties, LP"))
        .length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Form 8879-PE (2025)").length).toBeGreaterThan(0);
    expect(await screen.findByText("Amounts match the exported return")).toBeTruthy();
    expect(screen.getByText("ERO and EFIN populated")).toBeTruthy();
    expect(screen.getByText("1 · Dr. Sofia Lindqvist")).toBeTruthy();
    expect(screen.getByText("2 · Daniel Reyes")).toBeTruthy();
    expect(
      screen.getByText(
        "Gate: e-file of the TY2025 Form 1065 is blocked until this envelope is Completed (TAX-12).",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Signed copy → Files › TY2025 Form 1065 › Signed authorizations · keep 7 years",
      ),
    ).toBeTruthy();
    const button = await send();
    await waitFor(() => {
      expect(button.disabled).toBe(false);
    });
    expect(button.getAttribute("data-human-verb")).toBe("Send");
  });

  it("a: the email code (SMS) is never selectable on an e-file authorization", async () => {
    show("a");
    const menu = await openIdentity(/Dr\. Sofia Lindqvist/u);
    const sms = within(menu).getByRole("menuitemradio", { name: /Email \+ SMS code/u });
    expect(sms.getAttribute("aria-disabled")).toBe("true");
    expect(within(menu).getByText("Not allowed for e-file authorizations")).toBeTruthy();
    fireEvent.click(sms);
    const row = screen
      .getByText(/1 · Dr\. Sofia Lindqvist/u)
      .closest("[data-signer]") as HTMLElement;
    expect(
      within(row)
        .getByRole("button", { name: /^Identity/u, hidden: true })
        .getAttribute("aria-label"),
    ).toBe("Identity: Identity questions (KBA)");
  });

  it("a: Alt+↓ moves a document and Send saves the new order before sending", async () => {
    const calls = show("a");
    const first = await screen.findByRole("button", { name: /Form 8879-PE \(2025\)/u });
    fireEvent.keyDown(first, { key: "ArrowDown", altKey: true });
    const order = Array.from(document.querySelectorAll("[data-document]")).map((el) =>
      el.textContent.includes("1065 — client copy"),
    );
    expect(order).toEqual([true, false]);
    const button = await send();
    await waitFor(() => {
      expect(button.disabled).toBe(false);
    });
    fireEvent.click(button);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/send"))).toBe(true);
    });
    const put = calls.find((c) => c.method === "PUT");
    expect((put?.body as { document_order: string[] }).document_order).toHaveLength(2);
    await waitFor(() => {
      expect(toastStore.list().some((t) => t.text.startsWith("Sent to Dr. Sofia Lindqvist"))).toBe(
        true,
      );
    });
  });

  it("e: E13 with a countersigner; the letter's gate; Send toasts Sent to Owen Calder · E13", async () => {
    const calls = show("e");
    expect(
      (
        await screen.findAllByText(
          "Engagement letter · Ridgeline cost segregation & §754 analysis",
        )
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("1 · Owen Calder")).toBeTruthy();
    expect(screen.getByText("2 · Daniel Reyes")).toBeTruthy();
    expect(await screen.findByText("Countersignature follows the client")).toBeTruthy();
    expect(
      screen.getByText("Gate: work on E13 starts when this envelope is Completed (ENG-04)."),
    ).toBeTruthy();
    const menu = await openIdentity(/Owen Calder/u);
    expect(
      within(menu)
        .getByRole("menuitemradio", { name: /Email \+ SMS code/u })
        .getAttribute("aria-disabled"),
    ).toBeNull();
    fireEvent.keyDown(menu, { key: "Escape" });
    const button = await send();
    await waitFor(() => {
      expect(button.disabled).toBe(false);
    });
    fireEvent.click(button);
    await waitFor(() => {
      expect(toastStore.list().some((t) => t.text === "Sent to Owen Calder · E13")).toBe(true);
    });
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("f: a signer with no email shows Email required and Send stays disabled", async () => {
    show("f");
    expect(await screen.findByText(/Email required/u)).toBeTruthy();
    expect(await screen.findByText("Dr. Sofia Lindqvist has no email on file.")).toBeTruthy();
    expect((await send()).disabled).toBe(true);
  });
});
