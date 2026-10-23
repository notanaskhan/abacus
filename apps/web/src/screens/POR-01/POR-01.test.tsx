// POR-01 · Portal sign-in, part 1 (P-08-T09). One test per artboard this task builds (a, b, e, f,
// g and the 390 layout) on its fixture scenario, the handoff's acceptance checklist, P-08 Stories
// 2.1, 2.2 and 5.1, §5.6's accessibility rules, the non-artboard states, and the AVOID list.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import type { PortalLanding, SignInOpening } from "../../domain/portal";
import { setPortalAccessToken } from "../../domain/portal";
import { scenarios as all } from "../../fixtures/scenarios/POR-01";
import { NEUTRAL_BRANDING } from "../../fixtures/seed/portal-home";
import { newQueryClient } from "../../testing/support";
import { PortalSignIn } from ".";
import { type Por01State, START, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
  setPortalAccessToken(null);
});

interface Seen {
  calls: { path: string; body: unknown }[];
}

function install(scenario: Scenario): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function show(
  state: Por01State,
  options: { scenario?: Scenario; opening?: SignInOpening } = {},
): { seen: Seen; landed: ReturnType<typeof vi.fn<(l: PortalLanding) => void>> } {
  const seen = install(options.scenario ?? scenarios[state]);
  const landed = vi.fn<(l: PortalLanding) => void>();
  render(
    <QueryClientProvider client={newQueryClient()}>
      <PortalSignIn
        opening={options.opening ?? START[state]}
        mobile={state === "M"}
        onSignedIn={landed}
      />
    </QueryClientProvider>,
  );
  return { seen, landed };
}

const CLAIRE = START.a.email;
const boxes = (): HTMLInputElement[] => screen.getAllByRole("textbox", { name: /^Digit / });
const calls = (seen: Seen, path: string) => seen.calls.filter((c) => c.path === path);

function typeCode(code: string): void {
  const first = boxes()[0];
  if (first === undefined) throw new Error("no code boxes");
  act(() => {
    first.focus();
  });
  for (const digit of code) {
    const focused = document.activeElement as HTMLInputElement;
    fireEvent.change(focused, { target: { value: digit } });
  }
}

/** Every attribute a person or assistive technology meets, plus the text. */
function everything(): string {
  const attrs = [...document.body.querySelectorAll("*")].flatMap((el) =>
    ["aria-label", "title", "alt", "placeholder"].map((a) => el.getAttribute(a) ?? ""),
  );
  return `${document.body.textContent} ${attrs.join(" ")}`;
}

describe("POR-01 artboards", () => {
  it("has scenarios for a–g, c′ and the 390 layout; builds a, b, e, f, g and M here", () => {
    expect(Object.keys(all)).toEqual(["a", "b", "c", "c2", "d", "e", "f", "g", "M"]);
    expect(STATES).toEqual(["a", "b", "e", "f", "g", "M"]);
    expect(all.c.persona).toBe("tess-moreno");
    expect(all.d.persona).toBe("sam-ortiz");
    expect(all.d.clock).toBe("2026-09-02T09:22:00-05:00");
    for (const s of STATES) expect(scenarios[s].clock).toBe("2026-09-14T09:22:00-05:00");
  });

  it("POR-01a email entry: the firm's card, the email on file, Continue and the footnote", async () => {
    show("a");
    expect(
      await screen.findByRole("heading", { name: "Sign in to your client portal" }),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Use the email address Brightwater Hale has on file. We'll send you a 6-digit code — no password needed.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole<HTMLInputElement>("textbox", { name: "Email" }).value).toBe(CLAIRE);
    expect(screen.getByRole("button", { name: "Continue" })).toBeTruthy();
    expect(
      screen.getByText("Brightwater Hale uses secure sign-in. Codes expire after 10 minutes."),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Help" }).getAttribute("href")).toContain("/help");
    expect(screen.getByRole("link", { name: "Privacy" })).toBeTruthy();
    expect(
      screen.getByText("Brightwater Hale LLP · 311 West Brannock Street, Chicago, IL"),
    ).toBeTruthy();
  });

  it("POR-01b code sent: six boxes hold 481027, Sign in, Resend waits 0:42, a different email", async () => {
    const { seen } = show("b");
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    expect(screen.getByText(`We sent a 6-digit code to ${CLAIRE}.`)).toBeTruthy();
    expect(
      boxes()
        .map((b) => b.value)
        .join(""),
    ).toBe("481027");
    expect(screen.getByRole("group", { name: "Sign-in code" })).toBeTruthy();
    expect(screen.getByText("Didn't get it?")).toBeTruthy();
    const resend = screen.getByRole("button", { name: /^Resend code/ });
    expect(resend.hasAttribute("disabled")).toBe(true);
    expect(within(resend).getByText("0:42")).toBeTruthy();
    expect(calls(seen, "/v1/portal/auth/start")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Use a different email" }));
    expect(
      await screen.findByRole("heading", { name: "Sign in to your client portal" }),
    ).toBeTruthy();
  });

  it("POR-01e expired link: Email me a new link renews it and the toast names the address", async () => {
    const { seen } = show("e");
    expect(
      await screen.findByRole("heading", { name: "This sign-in link has expired" }),
    ).toBeTruthy();
    expect(screen.getByText("Links work for 14 days. We can send you a new one.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Email me a new link" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe(`New link sent to ${CLAIRE}`);
    });
    expect(calls(seen, "/v1/portal/links/renew")[0]?.body).toEqual({
      link_token: START.e.linkToken,
    });
  });

  it("POR-01f wrong code: the red-ink ring and '2 tries left' in a polite live region", async () => {
    show("f");
    const helper = await screen.findByText("That code didn't match. 2 tries left.");
    expect(helper.getAttribute("aria-live")).toBe("polite");
    expect(helper.className).toContain("text-red-ink");
    for (const box of boxes()) {
      expect(box.getAttribute("aria-invalid")).toBe("true");
      expect(box.getAttribute("aria-describedby")).toBe(helper.id);
    }
  });

  it("POR-01g locked: Too many attempts names Grace Holloway; focus moves to the title", async () => {
    show("g");
    const title = await screen.findByRole("heading", { name: "Too many attempts" });
    expect(
      screen.getByText(
        "For your security, sign-in is paused for 15 minutes. If you need help now, contact Grace Holloway at Brightwater Hale.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Contact Brightwater Hale" })).toBeTruthy();
    await waitFor(() => {
      expect(document.activeElement).toBe(title);
    });
  });

  it("POR-01 390: the mobile frame, the card full width, the primary pinned near the bottom", async () => {
    show("M");
    await screen.findByRole("heading", { name: "Sign in to your client portal" });
    expect(document.querySelector("[data-variant='auth-mobile']")).not.toBeNull();
    const pin = screen.getByRole("button", { name: "Continue" }).parentElement;
    expect(pin?.className).toContain("sticky");
    expect(pin?.className).toContain("bottom-[16px]");
  });

  it("POR-01 390: the code boxes are 42 × 50 with a gap of 6", async () => {
    show("M", { opening: START.b });
    await screen.findByRole("heading", { name: "Check your email" });
    expect(boxes()[0]?.className).toContain("h-[50px] w-[42px]");
    expect(screen.getByRole("group", { name: "Sign-in code" }).className).toContain("gap-[6px]");
  });
});

describe("POR-01 acceptance", () => {
  it("POR-01 acceptance: one 400-px card; the firm's mark and name above the title; nothing says Accrued", async () => {
    show("a");
    await screen.findByRole("heading", { name: "Sign in to your client portal" });
    const cards = document.querySelectorAll("[data-auth='card']");
    expect(cards).toHaveLength(1);
    expect(cards[0]?.parentElement?.className).toContain("w-[400px]");
    const brand = cards[0]?.querySelector("[data-auth='brand']");
    expect(brand?.lastElementChild?.textContent).toBe("Brightwater Hale");
    expect(brand?.nextElementSibling?.querySelector("h1")?.textContent).toBe(
      "Sign in to your client portal",
    );
    expect(everything()).not.toMatch(/accrued/i);
  });

  it("POR-01 acceptance: passwordless: email → 6 boxes; no password field anywhere", async () => {
    show("b");
    await screen.findByRole("heading", { name: "Check your email" });
    expect(boxes()).toHaveLength(6);
    expect(document.querySelector("input[type='password']")).toBeNull();
    expect(everything()).not.toMatch(/password/i);
  });

  it("POR-01 acceptance: an error is red-ink text and an inset ring only, never a red banner", async () => {
    show("f");
    await screen.findByText("That code didn't match. 2 tries left.");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(boxes()[0]?.className).toContain("inset-ring-red-ink");
  });

  it("P-08 Story 2.1: the 600 ms spinner shows on Continue, then the code step", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      show("a");
      fireEvent.click(await screen.findByRole("button", { name: "Continue" }));
      expect((await screen.findByRole("status")).textContent).toContain("Sending your code");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(300);
      });
      expect(screen.queryByRole("heading", { name: "Check your email" })).toBeNull();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(400);
      });
      expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it("P-08 Story 2.1: the sixth digit submits once and the person lands home", async () => {
    const { seen, landed } = show("a", { opening: { email: CLAIRE, start: true } });
    await screen.findByRole("heading", { name: "Check your email" });
    typeCode("481027");
    await waitFor(() => {
      expect(landed).toHaveBeenCalledWith("home");
    });
    expect(calls(seen, "/v1/portal/auth/verify")).toHaveLength(1);
  });

  it("P-08 §5.6: paste fills the boxes and submits; the boxes are numeric one-time-code inputs", async () => {
    const { landed } = show("a", { opening: { email: CLAIRE, start: true } });
    await screen.findByRole("heading", { name: "Check your email" });
    const first = boxes()[0] as HTMLInputElement;
    expect(first.getAttribute("autocomplete")).toBe("one-time-code");
    expect(first.getAttribute("inputmode")).toBe("numeric");
    fireEvent.paste(first, { clipboardData: { getData: () => "481027" } });
    await waitFor(() => {
      expect(landed).toHaveBeenCalledWith("home");
    });
  });

  it("P-08 Story 2.2: the third wrong code locks sign-in for 15 minutes", async () => {
    show("f");
    await screen.findByText("That code didn't match. 2 tries left.");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("That code didn't match. 1 try left.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Too many attempts" })).toBeTruthy();
  });

  it("P-08 Story 2.1: any email gets the same start answer (no enumeration)", async () => {
    const answer = async (
      email: string,
    ): Promise<{ status: number | undefined; keys: string[] }> => {
      const handler = scenarios.a.handlers["POST /v1/portal/auth/start"];
      const response = await handler?.({
        method: "POST",
        path: "/v1/portal/auth/start",
        params: {},
        query: new URLSearchParams(),
        body: { email },
        persona: undefined,
      });
      const body = (await response?.json()) as Record<string, unknown>;
      return { status: response?.status, keys: Object.keys(body).sort() };
    };
    expect(await answer("someone.unknown@sink.brightwaterhale.test")).toEqual(
      await answer(CLAIRE),
    );
  });

  it("an owner's code goes on to two-step verification (the card itself is P-08-T19's)", async () => {
    const { landed } = show("a", { scenario: all.c, opening: START.c });
    expect(await screen.findByRole("heading", { name: "Two-step verification" })).toBeTruthy();
    expect(landed).not.toHaveBeenCalled();
  });
});

describe("POR-01 non-artboard states", () => {
  const withVerify = (status: number, detail: string): Scenario => ({
    ...scenarios.b,
    handlers: {
      ...scenarios.b.handlers,
      "POST /v1/portal/auth/verify": () => json({ detail }, status),
    },
  });

  it("code expired: the helper offers Resend", async () => {
    show("b", { scenario: withVerify(410, "code_expired"), opening: START.f });
    expect(
      await screen.findByText("That code has expired. Use Resend code to get a new one."),
    ).toBeTruthy();
  });

  it("sign-in paused names the firm's support contact", async () => {
    show("b", { scenario: withVerify(503, "sign_in_paused"), opening: START.f });
    expect(
      await screen.findByText(
        "Sign-in is paused for now. If you need help, contact Grace Holloway at Brightwater Hale.",
      ),
    ).toBeTruthy();
  });

  it("an unknown portal host: the same card with no firm name, mark, address or person", async () => {
    show("a", {
      scenario: {
        ...scenarios.a,
        handlers: {
          ...scenarios.a.handlers,
          "GET /v1/portal/branding": () => json(NEUTRAL_BRANDING),
        },
      },
    });
    await screen.findByRole("heading", { name: "Sign in to your client portal" });
    expect(
      screen.getByText(
        "Use your email address. We'll send you a 6-digit code — no password needed.",
      ),
    ).toBeTruthy();
    expect(document.body.textContent).not.toContain("Brightwater");
    expect(screen.queryByRole("link", { name: "Help" })).toBeNull();
  });
});

describe("POR-01 avoid", () => {
  it("POR-01 avoid: password fields, social sign-in, CAPTCHA, the product's name", async () => {
    for (const state of ["a", "b", "e", "f", "g"] as const) {
      show(state);
      await screen.findByRole("heading");
      await waitFor(() => {
        expect(document.querySelector("[data-screen='POR-01']")).not.toBeNull();
      });
      // The handoff's own "no password needed." is the one place the word may appear.
      const text = everything().replace("no password needed.", "");
      expect(text, state).not.toMatch(/accrued|password|captcha|google|apple|microsoft|facebook/i);
      expect(document.querySelector("input[type='password']"), state).toBeNull();
      cleanup();
      restore?.();
      restore = undefined;
    }
  });
});
