import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PortalBrandProvider } from "../../brand";
import type { EnvelopeVM } from "../../signing/types";
import { BRIGHTWATER_BRAND } from "../../specimens/portal";
import { t16Envelope } from "../../specimens/signing";
import { SigningCeremony } from "./SigningCeremony";

// F-06-T04 (SPEC-400 AC-1, AC-2, AC-3, AC-8): "T16b and TPL-16b read 1 of 2 signed with only the
// viewer's fields actionable, Sign here moves focus to the next empty field, and TPL-16d lists
// all six evidence items." F-06-T07 owns the independent suite; these are the build's own tests.

afterEach(cleanup);

function ceremony(
  envelope: EnvelopeVM,
  extra: Partial<Parameters<typeof SigningCeremony>[0]> = {},
) {
  return render(
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <SigningCeremony
        envelope={envelope}
        user="Claire Feld"
        backLabel="All documents to sign"
        completion={{ title: "Signed. Thank you, Claire." }}
        {...extra}
      />
    </PortalBrandProvider>,
  );
}

describe("T16b: signing", () => {
  it("AC-1: the envelope header reads 1 of 2 signed from the server's counts", () => {
    ceremony(t16Envelope("b"));
    const pill = document.querySelector("[data-envelope-pill]");
    expect(pill?.textContent).toBe("1 of 2 signed");
  });

  it("AC-1: the counts are the server's, never the browser's", () => {
    ceremony({ ...t16Envelope("b"), signedCount: 7, signerCount: 9 });
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toBe("7 of 9 signed");
  });

  it("AC-2: only the viewer's open field is a control; another signer's field is text", () => {
    ceremony(t16Envelope("b"));
    const fields = screen.getAllByRole("button", { name: /^Sign here:/ });
    expect(fields).toHaveLength(1);
    expect(fields[0]?.getAttribute("aria-label")).toBe(
      "Sign here: spouse signature, Form 8879 · federal, page 1",
    );
    const jonah = document.querySelector('[data-field="t16-jonah-sig"]');
    expect(jonah?.tagName).toBe("SPAN");
    expect(jonah?.textContent).toBe("Jonah Feld · signed electronically");
  });

  it("AC-2: the Sign here tab marks the viewer's next empty field and moves focus to it", () => {
    ceremony(t16Envelope("b"));
    const tab = document.querySelector<HTMLButtonElement>("[data-sign-here-tab]");
    expect(tab).not.toBeNull();
    act(() => tab?.click());
    expect(document.activeElement?.getAttribute("data-field")).toBe("t16-claire-sig");
  });

  it("AC-2: a field click asks for that field; the sign call to action asks for the next one", () => {
    const onSignField = vi.fn();
    ceremony(t16Envelope("b"), { onSignField });
    fireEvent.click(screen.getByRole("button", { name: /^Sign here:/ }));
    fireEvent.click(screen.getByRole("button", { name: "Adopt signature & sign" }));
    expect(onSignField.mock.calls).toEqual([["t16-claire-sig"], ["t16-claire-sig"]]);
  });

  it("AC-2: a viewer who is not a signer gets the restricted state, no page and no field", () => {
    const env = t16Envelope("b");
    ceremony({ ...env, signers: env.signers.map((s) => ({ ...s, isViewer: false })) });
    expect(document.querySelector('[data-signing="restricted"]')).not.toBeNull();
    expect(document.querySelector('[data-signing="page"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /^Sign here:/ })).toBeNull();
  });

  it("AC-8: the steps are an ordered list with the current step marked", () => {
    ceremony(t16Envelope("b"));
    const steps = screen.getByRole("list", { name: "Signing steps" });
    const items = within(steps).getAllByRole("listitem");
    expect(items.map((li) => li.textContent.split(/\d/)[0])).toEqual([
      // T16b draws each step on one line (the handoff); the step words come from the registry.
      "Verify identity",
      "Review",
      "Sign",
      "Done",
    ]);
    expect(steps.querySelector('[aria-current="step"]')?.getAttribute("data-step")).toBe("sign");
  });

  it("AC-8: the sign control is a HumanAction and nothing names an agent", () => {
    ceremony(t16Envelope("b"));
    const cta = screen.getByRole("button", { name: "Adopt signature & sign" });
    expect(cta.getAttribute("data-human-verb")).toBe("Adopt");
    expect(document.body.textContent).not.toMatch(/Agent|Accrued/);
  });
});

describe("T16 page images (security review, S14 batch)", () => {
  it("draws only the server's page images: another host or an SVG is refused", () => {
    for (const src of ["https://evil.example/p.png", "data:image/svg+xml;base64,PHN2Zz4="]) {
      const env = t16Envelope("b");
      const doc = env.documents[0];
      if (doc === undefined) throw new Error("no document");
      const page = doc.pages[0];
      if (page === undefined) throw new Error("no page");
      ceremony({ ...env, documents: [{ ...doc, pages: [{ ...page, src }] }] });
      expect(document.querySelector('[data-signing="page"] img')).toBeNull();
      expect(document.querySelector("[data-page-refused]")).not.toBeNull();
      cleanup();
    }
  });
});

describe("T16c: done", () => {
  it("AC-3: the completion card replaces the steps with the evidence record", () => {
    ceremony(t16Envelope("c"));
    expect(document.querySelector("[data-envelope-pill]")?.textContent).toContain("Completed");
    const record = document.querySelector('[data-signing="evidence"]');
    expect(record?.querySelectorAll("dt")).toHaveLength(5);
    expect(screen.queryByRole("button", { name: /^Sign here:/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Decline…" })).toBeNull();
  });
});

describe("T16 geometry and states", () => {
  it("draws documents 240, the well 816 and steps 300 (Tier D)", () => {
    ceremony(t16Envelope("b"));
    expect(document.querySelector('[data-signing="documents"]')?.className).toContain("w-[240px]");
    expect(document.querySelector('[data-signing="well"]')?.className).toContain("w-[816px]");
    expect(document.querySelector('[data-signing="steps"]')?.className).toContain("w-[300px]");
    expect(document.querySelector('[data-signing="envelope-header"]')?.className).toContain(
      "h-[46px]",
    );
  });

  it("the error state offers Try again and no page", () => {
    const onRetry = vi.fn();
    ceremony(t16Envelope("b"), { view: "error", onRetry });
    expect(document.querySelector('[data-signing="page"]')).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Try again|Retry/ }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
