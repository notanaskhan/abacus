import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tpl16Specimen, e6Envelope } from ".";

// F-06-T04 (SPEC-400 AC-1, AC-2, AC-3): TPL-16b reads "1 of 2 signed" with only Mira's fields
// actionable, and TPL-16d lists all six evidence items, from envelope E6 in the tax seed.

afterEach(cleanup);

describe("TPL-16b: Mira signs E6", () => {
  it("AC-1: 1 of 2 signed, Dev's chips signed Sep 9 and Mira's open on both forms", () => {
    render(<Tpl16Specimen state="b" />);
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toBe("1 of 2 signed");
    const chips = [...document.querySelectorAll("[data-signer-chips]")].map((c) => c.textContent);
    expect(chips).toEqual(["✓ Dev · Sep 9○ Mira", "✓ Dev · Sep 9○ Mira"]);
  });

  it("AC-1: the authorizing card states $2,296 and $410", () => {
    render(<Tpl16Specimen state="b" />);
    expect(
      screen.getByText(/Your federal refund is \$2,296 and your New York refund is \$410\./),
    ).toBeTruthy();
  });

  it("AC-2: only Mira's fields are controls; Dev's read as signed", () => {
    render(<Tpl16Specimen state="b" />);
    expect(screen.getAllByRole("button", { name: /^Sign here:/ })).toHaveLength(1);
    expect(screen.getByText("Dev Kapoor · signed electronically Sep 9, 2026")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/);
  });
});

describe("TPL-16d: completed", () => {
  it("AC-3: all six evidence items, attributed to Mira, and the Completed pill", () => {
    render(<Tpl16Specimen state="d" />);
    const labels = [...document.querySelectorAll('[data-signing="evidence"] dt')].map(
      (d) => d.textContent,
    );
    expect(labels).toEqual(["Signed", "Method", "Identity", "IP address", "Login", "Documents"]);
    expect(screen.getByText("Signed. Thank you, Mira.")).toBeTruthy();
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toContain("Completed");
    expect(document.body.textContent).not.toMatch(/Accrued/);
  });
});

// F-06-T05 (Stories 1.1, 1.4, 1.5, 1.7): identity and exception states. F-06-T06 (Story 1.6): 390.

describe("TPL-16e: verification failed (DF-11)", () => {
  it("names the paper-form path and Dina Sato, and offers no retry, countdown or method", () => {
    render(<Tpl16Specimen state="e" />);
    const card = document.querySelector('[data-signing="verification-failed"]');
    expect(card?.textContent).toContain("We couldn't verify your identity.");
    expect(card?.textContent).toContain("paper form");
    expect(card?.textContent).toContain("Dina Sato");
    expect(card?.querySelector("button")).toBeNull();
    expect(document.body.textContent).not.toMatch(/try again|tomorrow|SMS|text message/i);
    expect(screen.queryAllByRole("button", { name: /^Sign here:/ })).toHaveLength(0);
  });
});

describe("TPL-16f: decline", () => {
  it("offers the four reasons and keeps Decline disabled until one is chosen", () => {
    const decided: { reason: string; note: string }[] = [];
    render(<Tpl16Specimen state="f" onDecline={(c) => decided.push(c)} />);
    for (const reason of [
      "The amounts look wrong",
      "I have a question first",
      "Someone else should sign",
      "Other",
    ]) {
      expect(screen.getByRole("radio", { name: reason })).toBeTruthy();
    }
    const confirm = document.querySelector<HTMLButtonElement>('[data-signing="decline-confirm"]');
    expect(confirm?.disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "I have a question first" }));
    const enabled = document.querySelector<HTMLButtonElement>('[data-signing="decline-confirm"]');
    expect(enabled?.disabled).toBe(false);
    if (enabled !== null) {
      fireEvent.click(enabled);
      fireEvent.click(enabled);
    }
    expect(decided).toEqual([{ reason: "I have a question first", note: "" }]);
  });
});

describe("provider mode: the return is a hint (Story 1.1)", () => {
  it("shows Checking, never Completed, while the server says Mira hasn't signed", () => {
    render(<Tpl16Specimen state="pending" />);
    expect(document.querySelector('[data-signing="pending-confirmation"]')).toBeTruthy();
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toBe("1 of 2 signed");
    expect(document.querySelector('[data-signing="evidence"]')).toBeNull();
  });

  it("hosts the provider in a titled, sandboxed frame during verify", () => {
    const base = e6Envelope("b");
    render(
      <Tpl16Specimen
        state="b"
        envelope={{
          ...base,
          steps: base.steps.map((s) => ({ ...s, state: s.key === "verify" ? "current" : "todo" })),
          signingSession: {
            url: "https://provider.example/session/abc",
            presentation: "iframe",
            expiresAt: "2026-09-14T15:00:00Z",
          },
        }}
      />,
    );
    const frame = document.querySelector<HTMLIFrameElement>('[data-signing="provider-frame"]');
    expect(frame?.title).toBe("Verify your identity and sign: Form 8879");
    expect(frame?.getAttribute("sandbox")).toContain("allow-scripts");
    expect(frame?.getAttribute("sandbox")).not.toContain("allow-top-navigation");
  });
});

describe("TPL-16g: 390", () => {
  it("one column with the step chips and a 64 sticky bar holding the sign control", () => {
    render(<Tpl16Specimen state="g" frame />);
    expect(document.querySelector('[data-layout="phone"]')).toBeTruthy();
    expect(document.querySelector('[data-signing="step-chips"]')?.textContent).toBe(
      "Verify ✓·Review ✓·Sign·Done",
    );
    const bar = document.querySelector('[data-signing="mobile-sign-bar"]');
    expect(bar?.getAttribute("data-height")).toBe("64");
    expect(bar?.querySelector("button")?.textContent).toBe("Adopt signature & sign…");
  });
});

// F-06-T13 (SPEC-400 AC-37; DEC-1250): TPL-16a in production is the provider's view in the well,
// titled and sandboxed, on a host that never resolves; no native KBA card, no page, no sign control.
describe("TPL-16a: the provider's view (DF-12)", () => {
  it("AC-37: the well hosts the provider frame and nothing of the native card", () => {
    render(<Tpl16Specimen state="a" />);
    const frame = document.querySelector('[data-signing="provider-frame"]');
    expect(frame?.getAttribute("title")).toBe("Verify your identity and sign: Form 8879");
    expect(new URL(frame?.getAttribute("src") ?? "").hostname.endsWith(".invalid")).toBe(true);
    expect(document.querySelector('[data-signing="page"]')).toBeNull();
    expect(screen.queryByText(/Question \d of \d/)).toBeNull();
    expect(screen.queryAllByRole("button", { name: /^Sign here:/ })).toHaveLength(0);
    expect(screen.getByText("verifying identity")).toBeTruthy();
  });

  it("AC-37: the verify step is current and nothing is signed for Mira", () => {
    const envelope = e6Envelope("a");
    expect(envelope.steps.find((s) => s.state === "current")?.key).toBe("verify");
    expect(envelope.signers.find((s) => s.isViewer)?.status).toBe("viewed");
    expect(envelope.signedCount).toBe(1);
  });
});
