import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PortalBrandProvider } from "../brand/portal-brand";
import { BRIGHTWATER_BRAND } from "../specimens/portal";
import { T15Specimen, Tpl15Specimen } from "../specimens/auth";
import { AuthCard, AuthFrame, CodeInput } from "./auth-card";

// F-05-T37 acceptance: "TPL-15b waits for all six digits, TPL-15d says invites last 14 days, and
// TPL-15e and TPL-15j render at 390px without horizontal scroll." Plus the code boxes (auto-advance,
// Backspace, paste), the second steps from the brand, the confirmation's computed difference and
// Submit gate, and the white label.

afterEach(cleanup);

function board(container: HTMLElement, id: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no artboard ${id}`);
  return el;
}

function Code({ onComplete }: { onComplete?: (v: string) => void }): JSX.Element {
  const [v, setV] = useState("");
  return (
    <CodeInput
      value={v}
      onChange={setV}
      label="6-digit code"
      {...(onComplete === undefined ? {} : { onComplete })}
    />
  );
}

describe("CodeInput: six boxes", () => {
  it("typing a digit moves to the next box; letters are ignored", () => {
    render(<Code />);
    const boxes = screen.getAllByRole("textbox");
    expect(boxes).toHaveLength(6);
    act(() => {
      (boxes[0] as HTMLInputElement).focus();
    });
    fireEvent.change(boxes[0] as HTMLInputElement, { target: { value: "7" } });
    expect(document.activeElement).toBe(boxes[1]);
    fireEvent.change(boxes[1] as HTMLInputElement, { target: { value: "x" } });
    expect((boxes[1] as HTMLInputElement).value).toBe("");
    fireEvent.change(boxes[1] as HTMLInputElement, { target: { value: "2" } });
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("72");
    expect(document.activeElement).toBe(boxes[2]);
  });

  it("Backspace on an empty box clears the one before and moves back", () => {
    render(<Code />);
    const boxes = screen.getAllByRole("textbox");
    fireEvent.change(boxes[0] as HTMLInputElement, { target: { value: "7" } });
    fireEvent.change(boxes[1] as HTMLInputElement, { target: { value: "2" } });
    fireEvent.keyDown(boxes[2] as HTMLInputElement, { key: "Backspace" });
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("7");
    expect(document.activeElement).toBe(boxes[1]);
  });

  it("a paste fills every box and completes once", () => {
    const onComplete = vi.fn();
    render(<Code onComplete={onComplete} />);
    const boxes = screen.getAllByRole("textbox");
    fireEvent.paste(boxes[0] as HTMLInputElement, {
      clipboardData: { getData: () => "481 027" },
    });
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("481027");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("481027");
  });

  it("an autofill of six digits into the first box fills them all", () => {
    render(<Code />);
    const boxes = screen.getAllByRole("textbox");
    fireEvent.change(boxes[0] as HTMLInputElement, { target: { value: "729104" } });
    expect(boxes.map((b) => (b as HTMLInputElement).value).join("")).toBe("729104");
  });

  it("the boxes are 44 × 52, radius 10, and the group is named", () => {
    render(<Code />);
    expect(screen.getByRole("group", { name: "6-digit code" })).toBeTruthy();
    const box = screen.getAllByRole("textbox")[0] as HTMLElement;
    expect(box.className).toContain("w-[44px]");
    expect(box.className).toContain("h-[52px]");
    expect(box.className).toContain("rounded-nested");
  });
});

describe("TPL-15 (Jonah Feld's sign-in)", () => {
  it("TPL-15b waits for all six digits; six typed or pasted enable Continue", () => {
    const { container } = render(<Tpl15Specimen />);
    const b = board(container, "tpl-15b");
    const cont = within(b).getByRole("button", { name: "Continue" });
    expect(cont.hasAttribute("disabled")).toBe(true);
    const boxes = within(b).getAllByRole("textbox");
    expect(boxes.map((x) => (x as HTMLInputElement).value).join("")).toBe("729");
    fireEvent.change(boxes[3] as HTMLInputElement, { target: { value: "1" } });
    expect(cont.hasAttribute("disabled")).toBe(true);
    fireEvent.paste(boxes[4] as HTMLInputElement, { clipboardData: { getData: () => "04" } });
    expect(within(b).getByRole("button", { name: "Continue" }).hasAttribute("disabled")).toBe(
      false,
    );
    fireEvent.click(within(b).getByRole("button", { name: "Continue" }));
    expect(within(b).getByRole("heading", { name: "One more step" })).toBeTruthy();
  });

  it("TPL-15d says invites last 14 days, with Send a new invite link", () => {
    const { container } = render(<Tpl15Specimen />);
    const d = board(container, "tpl-15d");
    expect(within(d).getByText("Invites last 14 days. We can send you a new one.")).toBeTruthy();
    expect(within(d).getByRole("button", { name: "Send a new invite link" })).toBeTruthy();
    expect(within(d).getByRole("heading", { name: "This invite link has expired" })).toBeTruthy();
  });

  it("TPL-15c offers the second steps the brand lists, and no password", () => {
    const { container } = render(<Tpl15Specimen />);
    const c = board(container, "tpl-15c");
    expect(
      within(c)
        .getAllByRole("radio")
        .map((r) => r.textContent),
    ).toEqual(["Text a code to •••-•••-0142", "Use a passkey on this device"]);
    expect(container.querySelector('input[type="password"]')).toBeNull();
  });

  it("TPL-15e and TPL-15j render at 390, fluid, with no fixed width over 390", () => {
    const { container } = render(
      <>
        <Tpl15Specimen />
      </>,
    );
    for (const id of ["tpl-15e", "tpl-15j"]) {
      const art = board(container, id);
      const phone = art.querySelector<HTMLElement>('[data-variant="auth-mobile"]');
      expect(phone?.className).toContain("w-[390px]");
      expect(phone?.style.height).toBe("844px");
      expect(art.querySelector('[data-shell="mobile-header"]')).not.toBeNull();
      // Nothing inside the phone asks for more than its width.
      for (const el of phone?.querySelectorAll<HTMLElement>("*") ?? []) {
        const widths = (el.getAttribute("class") ?? "").match(/\b(?:min-)?w-\[(\d+)px\]/g) ?? [];
        for (const w of widths) {
          expect(Number(/\d+/.exec(w)?.[0]), `${id}: ${w}`).toBeLessThanOrEqual(358);
        }
      }
    }
    const card = board(container, "tpl-15e").querySelector('[data-auth="card"]');
    expect(card?.parentElement?.className).toContain("w-full");
    expect(board(container, "tpl-15e").querySelector('[data-auth="code"]')?.className).toContain(
      "gap-[6px]",
    );
  });

  it("targets at 390 are at least 44 high or a 36 full-width button", () => {
    const { container } = render(<Tpl15Specimen />);
    const e = board(container, "tpl-15e");
    for (const box of within(e).getAllByRole("textbox")) {
      expect(box.className).toContain("h-[52px]");
    }
    expect(within(e).getByRole("button", { name: "Continue" }).className).toContain("w-full");
  });
});

describe("TPL-15 (the confirmation response)", () => {
  it("TPL-15f: Summit Trail's balance from the decimal, Submit open once verified and authorized", () => {
    const { container } = render(<Tpl15Specimen />);
    const f = board(container, "tpl-15f");
    expect(f.querySelector('[data-amount="balance"]')?.textContent).toBe("$412,600.00");
    expect(within(f).getByText("Verified 10:14 AM")).toBeTruthy();
    expect(
      within(f).getByRole("button", { name: "Submit response" }).hasAttribute("disabled"),
    ).toBe(false);
    expect(within(f).getByText(/This is not a request for payment/)).toBeTruthy();
  });

  it("TPL-15g: the difference is computed, $4,300.00, and Submit waits on verification", () => {
    const { container } = render(<Tpl15Specimen />);
    const g = board(container, "tpl-15g");
    expect(g.querySelector('[data-amount="balance"]')?.textContent).toBe("$286,900.00");
    expect(g.querySelector('[data-amount="difference"]')?.textContent).toBe("$4,300.00");
    const submit = within(g).getByRole("button", { name: "Submit response" });
    expect(submit.hasAttribute("disabled")).toBe(true);
    expect(submit.title).toBe("Verify your work email and confirm your authority first");
    fireEvent.change(within(g).getByRole("textbox", { name: "Amount per your records" }), {
      target: { value: "286,000.50" },
    });
    expect(g.querySelector('[data-amount="difference"]')?.textContent).toBe("$899.50");
  });

  it("TPL-15h and TPL-15i: the receipt, and an answered link with no form", () => {
    const { container } = render(<Tpl15Specimen />);
    const h = board(container, "tpl-15h");
    expect(within(h).getByText("Thank you. Your response was received.")).toBeTruthy();
    expect(within(h).getByText("Rachel Imholt, verified email")).toBeTruthy();
    const i = board(container, "tpl-15i");
    expect(within(i).getByText("This confirmation has already been answered")).toBeTruthy();
    expect(within(i).queryByRole("button", { name: "Submit response" })).toBeNull();
  });

  it("never shows a password field, a payment link or the product's name", () => {
    const { container } = render(<Tpl15Specimen />);
    expect(container.querySelector('input[type="password"]')).toBeNull();
    expect(container.textContent).not.toMatch(/accrued/i);
    expect(container.textContent).not.toMatch(/\bpay now\b/i);
  });
});

describe("T15 (the template's artboards)", () => {
  it("T15a signs in, T15b waits for six digits, T15c is the 720 page", () => {
    const { container } = render(<T15Specimen />);
    expect(
      within(board(container, "t15a")).getByRole("heading", {
        name: "Sign in to Brightwater Hale",
      }),
    ).toBeTruthy();
    const verify = within(board(container, "t15b")).getByRole("button", { name: "Verify" });
    expect(verify.hasAttribute("disabled")).toBe(true);
    const page = board(container, "t15c").querySelector('[data-auth="page"]');
    expect(page?.parentElement?.className).toContain("w-[720px]");
    expect(within(board(container, "t15c")).getAllByRole("radio")).toHaveLength(3);
  });

  it("the card is 400 wide, radius 14, padding 28 28 24, with no toolbar", () => {
    const { container } = render(
      <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
        <AuthFrame layout="card">
          <AuthCard title="Check your email" />
        </AuthFrame>
      </PortalBrandProvider>,
    );
    const card = container.querySelector<HTMLElement>('[data-auth="card"]');
    expect(card?.parentElement?.className).toContain("w-[400px]");
    expect(card?.className).toContain("rounded-dialog");
    expect(card?.className).toContain("px-[28px]");
    expect(card?.className).toContain("pt-[28px]");
    expect(card?.className).toContain("pb-[24px]");
    expect(container.querySelector('[data-shell="portal-toolbar"]')).toBeNull();
    expect(container.textContent).toContain("Brightwater Hale");
  });
});

// P-01-T11 (SHL-06g): the firm app's own sign-in passes its marks; the card needs no portal brand.
describe("AuthCard marks", () => {
  it("draws the caller's marks above and inside, centred, without a brand provider", () => {
    const { container } = render(
      <AuthCard
        brand="marks"
        marks={{ above: <span>Above mark</span>, inside: <span>Inside mark</span> }}
        title="Sign in"
      />,
    );
    const above = container.querySelector<HTMLElement>('[data-auth="brand"]');
    expect(above?.textContent).toBe("Above mark");
    const card = container.querySelector<HTMLElement>('[data-auth="card"]');
    expect(card?.className).toContain("text-center");
    expect(within(card ?? container).getByText("Inside mark")).toBeTruthy();
  });

  it("a tile replaces the inside mark and centres under it", () => {
    const { container } = render(
      <AuthCard
        brand="marks"
        marks={{ above: <span>Above mark</span>, inside: <span>Inside mark</span> }}
        tile={{ icon: "lock", tone: "red" }}
        title="Sign-in didn't complete"
      />,
    );
    expect(screen.queryByText("Inside mark")).toBeNull();
    const tile = container.querySelector<HTMLElement>('[data-auth="card"] > span');
    expect(tile?.className).toContain("self-center");
  });
});
