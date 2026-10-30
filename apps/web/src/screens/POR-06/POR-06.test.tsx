// POR-06 · Sign, part 1 (N-02-T26; SPEC-381 AC-10, AC-12; docs/screens/POR-06.md). One test per
// artboard on its fixture scenario at 1400 and 390, and the task's acceptance: "Scenario tests for
// a, b, c and g pass at 1400 and 390, and Completed never renders from a return parameter alone."
// Pages come into view through a stubbed IntersectionObserver (jsdom has none); the provider's
// view never loads (the `.invalid` host). The walk with axe is N-02-T43's Playwright lock.
import type { PortalEnvelopeView } from "@abacus/api-client";
import { Toaster } from "@abacus/ui";
import { client } from "@abacus/api-client/client";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { freshScenario } from "../../fixtures/scenarios/POR-06";
import { E13_SESSION, ERSD_VERSION } from "../../fixtures/seed/portal-envelopes";
import { renderRoutes } from "../../testing/support";
import { PortalSign, phaseOf, stepsOf } from ".";
import { ARTBOARD, type Por06State } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

/** Every observed page reports itself in view at once: the whole letter has been read. */
class SeeEverything {
  private readonly callback: IntersectionObserverCallback;
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }
  observe(target: Element): void {
    this.callback(
      [{ isIntersecting: true, target } as unknown as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
  disconnect(): void {}
  unobserve(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.unstubAllGlobals();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Por06State, options: { mobile?: boolean } = {}): Seen {
  const seen: Seen = { calls: [] };
  const scenario = freshScenario(state);
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const board = ARTBOARD[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <PortalSign
            mobile={options.mobile === true}
            {...(board.envelopeId === undefined ? {} : { envelopeId: board.envelopeId })}
            {...(board.session === undefined ? {} : { session: board.session })}
          />
          <Toaster />
        </>
      ),
    },
  ]);
  return seen;
}

const WIDTHS = [
  ["1400", false],
  ["390", true],
] as const;

async function continueButton(): Promise<HTMLButtonElement> {
  return screen.findByRole<HTMLButtonElement>("button", { name: "Continue to sign" });
}

describe.each(WIDTHS)("POR-06 at %s", (_width, mobile) => {
  it("test_ac10_a_review_continue_waits_for_the_last_page", async () => {
    show("a", { mobile });
    expect((await continueButton()).disabled).toBe(true);
    expect(screen.getByText("Read to page 3 to continue.")).toBeTruthy();
    expect(document.querySelector("[data-signing='provider-frame']")).toBeNull();
    expect(screen.queryByText("Completed")).toBeNull();
  });

  it("test_ac10_a_continue_unlocks_once_page_3_was_seen", async () => {
    vi.stubGlobal("IntersectionObserver", SeeEverything);
    const seen = show("a", { mobile });
    await waitFor(async () => {
      expect((await continueButton()).disabled).toBe(false);
    });
    expect(
      seen.calls.some(
        (c) =>
          c.path.endsWith("/progress") &&
          (c.body as { last_page_seen?: number }).last_page_seen === 3,
      ),
    ).toBe(true);
  });

  it("test_ac10_b_consent_then_the_providers_view", async () => {
    vi.stubGlobal("IntersectionObserver", SeeEverything);
    const seen = show("a", { mobile });
    const go = await continueButton();
    await waitFor(() => {
      expect(go.disabled).toBe(false);
    });
    fireEvent.click(go);
    const consent = await screen.findByRole("region", { name: "Agree to sign electronically" });
    const agree = within(consent).getByRole("button", { name: "Agree and continue" });
    expect((agree as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(
      within(consent).getByRole("checkbox", {
        name: "I agree to sign electronically and that my electronic signature is binding",
      }),
    );
    fireEvent.click(agree);
    const frame = await waitFor(() => {
      const found = document.querySelector("[data-signing='provider-frame']");
      expect(found).not.toBeNull();
      return found as HTMLIFrameElement;
    });
    expect(frame.getAttribute("title")).toBe(
      "Sign: Engagement letter — Cost segregation and §754",
    );
    expect(frame.getAttribute("src")).toBe(E13_SESSION.url);
    const consentCall = seen.calls.find((c) => c.path.endsWith("/esign-consent"));
    expect(consentCall?.body).toEqual({ disclosure_version_id: ERSD_VERSION });
    expect(seen.calls.some((c) => c.path.endsWith("/signing-session"))).toBe(true);
  });

  it("test_ac10_b_opens_in_the_providers_view", async () => {
    show("b", { mobile });
    await waitFor(() => {
      expect(document.querySelector("[data-signing='provider-frame']")).not.toBeNull();
    });
    expect(screen.queryByRole("button", { name: /Adopt signature/ })).toBeNull();
  });

  it("test_ac10_c_the_server_says_signed_the_completion_card", async () => {
    show("c", { mobile });
    const card = await waitFor(() => {
      const found = document.querySelector("[data-signing='completion']");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(within(card).getByText("Signed. Thank you, Owen.")).toBeTruthy();
    expect(within(card).getByText("SHA-256 a41f…9c07")).toBeTruthy();
    expect(within(card).getByText("1 of 2 signed")).toBeTruthy();
    expect(within(card).getByText("Waiting for 1 more signature.")).toBeTruthy();
  });

  it("test_ac10_a_return_parameter_alone_never_renders_completed", async () => {
    show("pending", { mobile });
    await screen.findByText("Checking your signature");
    expect(document.querySelector("[data-signing='completion']")).toBeNull();
    expect(screen.queryByText("Completed")).toBeNull();
    expect(screen.queryByText(/Thank you/)).toBeNull();
  });

  it("test_ac12_g_declined_and_withdrawn", async () => {
    const seen = show("g", { mobile });
    const withdraw = await screen.findByRole("button", { name: "Withdraw decline" });
    expect(screen.getAllByText("Declined").length).toBeGreaterThan(0);
    fireEvent.click(withdraw);
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/decline/withdraw"))).toBe(true);
    });
    await screen.findByRole("button", { name: "Continue to sign" });
  });

  it("restricted: one state, no page, no field", async () => {
    show("restricted", { mobile });
    await screen.findByText("You aren't a signer on this envelope.");
    expect(document.querySelector("[data-signing='page']")).toBeNull();
    expect(screen.queryByRole("button", { name: /^Sign here:/ })).toBeNull();
  });
});

describe("POR-06 decline (g) from review", () => {
  it("test_ac12_g_a_reason_is_required_and_sends_c7s_code", async () => {
    const seen = show("a");
    fireEvent.click(await screen.findByRole("button", { name: "Decline…" }));
    const dialog = await screen.findByRole("dialog", { name: "Decline to sign?" });
    const confirm = within(dialog).getByRole<HTMLButtonElement>("button", { name: "Decline" });
    expect(confirm.disabled).toBe(true);
    fireEvent.click(within(dialog).getByRole("radio", { name: "Something is wrong" }));
    await act(async () => {
      fireEvent.click(confirm);
      await Promise.resolve();
    });
    await waitFor(() => {
      const call = seen.calls.find((c) => c.path.endsWith("/decline"));
      expect((call?.body as { reason?: string } | undefined)?.reason).toBe("something_wrong");
    });
    await screen.findByRole("button", { name: "Withdraw decline" });
  });
});

describe("POR-06 list", () => {
  it("to sign first, then the signed band with the two §7216 consents as separate documents", async () => {
    show("list");
    const toSign = await screen.findByRole("list", { name: "To sign" });
    expect(
      within(toSign).getByText("Engagement letter — Cost segregation and section 754 analysis"),
    ).toBeTruthy();
    const signed = screen.getByRole("list", { name: "Signed" });
    expect(within(signed).getAllByRole("listitem")).toHaveLength(3);
    expect(within(signed).getByText("Consent to use tax return information")).toBeTruthy();
    expect(
      within(signed).getByText(
        "Consent to disclose tax return information to AI service providers",
      ),
    ).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Accrued/);
  });
});

describe("phases and steps", () => {
  it("the server's view decides the phase; review waits only on the screen's own reading", () => {
    const view = freshScenario("a");
    expect(view.state).toBe("a");
    expect(stepsOf("review", 0, 3)[1]).toEqual({
      key: "review",
      state: "current",
      sub: "Page 1 of 3",
    });
    expect(stepsOf("provider", 3, 3).map((s) => s.state)).toEqual([
      "done",
      "done",
      "current",
      "todo",
    ]);
    expect(stepsOf("signed", 3, 3).every((s) => s.state === "done")).toBe(true);
  });

  it("signed only when the server's signer status says so", () => {
    const base: PortalEnvelopeView = {
      row: { id: "x", title: "t", status: "sent", my_status: "viewed", due_on: null },
      documents: [],
      my_fields: [],
      signers_signed: 0,
      signers_total: 2,
      esign_consent_needed: false,
      disclosure_version_id: null,
      date_as_of: null,
      paper_form_follows: false,
      signing_session: E13_SESSION,
      outcome: "signed",
    };
    // A view that says "outcome: signed" while the signer is still viewed is not signed.
    expect(phaseOf({ ...base, row: { ...base.row } }, false)).toBe("provider");
    expect(phaseOf({ ...base, row: { ...base.row, my_status: "signed" } }, false)).toBe("signed");
  });
});
