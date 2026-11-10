// A-07-T38 (AUD-24 in fixture mode): the six artboards, G5 to G7 with their values, G8 recorded
// only at release, the partner's release behind the attestation, and the filing card.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FRAMES } from "./copy";
import { Issuance } from "./Issuance";

afterEach(cleanup);

const release = (): HTMLButtonElement | null =>
  screen.queryByRole("button", { name: /Release report…/ });

describe("AUD-24 issuance and release", () => {
  it.each(FRAMES)("%s renders its artboard from the fixture", (frame) => {
    render(<Issuance frame={frame} canRelease={frame !== "e"} />);
    expect(document.querySelector(`[data-screen='AUD-24'][data-frame='${frame}']`)).not.toBeNull();
    expect(document.querySelectorAll("[data-gate]").length).toBe(4); // G5, G6, G7, G8
  });

  it("Release report… is enabled only in state a for the engagement partner", () => {
    for (const frame of FRAMES) {
      render(<Issuance frame={frame} canRelease={frame !== "e"} />);
      const button = release();
      if (frame === "a") expect(button?.disabled).toBe(false);
      else if (button !== null) expect(button.disabled).toBe(true);
      cleanup();
    }
    render(<Issuance frame="a" canRelease={false} />);
    expect(release()?.disabled).toBe(true);
  });

  it("a: the three gates are met with the handoff's numbers and G8 waits", () => {
    render(<Issuance frame="a" canRelease />);
    expect(screen.getByText("26 of 26 prepared and reviewed")).toBeTruthy();
    expect(screen.getByText("Oct 5, 2026 · 4:40 PM")).toBeTruthy();
    expect(screen.getByText("Oct 9, 2026 · 9:12 AM")).toBeTruthy();
    expect(screen.getByText("G8 · Released — recorded when you release")).toBeTruthy();
    expect(screen.getByText("Reserved to the engagement partner")).toBeTruthy();
    expect(document.querySelector("[data-gate='G8'][data-met='false']")).not.toBeNull();
  });

  it("b: G7 is not met and the release is blocked by it", () => {
    render(<Issuance frame="b" canRelease />);
    expect(document.querySelector("[data-gate='G7'][data-met='false']")).not.toBeNull();
    expect(screen.getByText("Out for signature since Oct 6")).toBeTruthy();
    expect(screen.getByText("Blocked by G7 · representation letter")).toBeTruthy();
    expect(release()?.disabled).toBe(true);
  });

  it("c: the dialog needs the partner's attestation before it releases", () => {
    const onRelease = vi.fn();
    render(<Issuance frame="c" canRelease onRelease={onRelease} />);
    const dialog = screen.getByRole("dialog", { name: "Release report" });
    expect(dialog).toBeTruthy();
    const confirm = screen.getAllByRole("button", { name: "Release report" }).at(-1);
    expect(confirm?.hasAttribute("disabled")).toBe(true);
    fireEvent.click(
      screen.getByLabelText("I am the engagement partner and I authorize release of this report"),
    );
    if (confirm !== undefined) fireEvent.click(confirm);
    expect(onRelease).toHaveBeenCalledTimes(1);
  });

  it("d: G8 is recorded, the clock starts and the toast names the client", () => {
    render(<Issuance frame="d" canRelease />);
    expect(screen.getByText("Released Oct 9, 2026 · 10:07 AM · Margaret Okonkwo")).toBeTruthy();
    expect(screen.getByText("Archive in 60 days · by Dec 8, 2026")).toBeTruthy();
    expect(screen.getByText("Report released · delivered to Dana Kowalski")).toBeTruthy();
    expect(screen.getByText("Delivered")).toBeTruthy();
    expect(release()).toBeNull();
  });

  it("e: a non-partner viewer sees who can release", () => {
    render(<Issuance frame="e" />);
    expect(screen.getByText("Only Margaret Okonkwo can release this report")).toBeTruthy();
    expect(release()?.disabled).toBe(true);
  });

  it("f: the client's filing is tracked, never filed by the firm", () => {
    render(<Issuance frame="f" />);
    expect(screen.getByText("Filed Oct 14, 2026 · EFAST2 acknowledgment received")).toBeTruthy();
    expect(screen.queryByText("Awaiting client filing")).toBeNull();
  });
});
