import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  AgentAvatar,
  FirmMark,
  MONOGRAM_SIZES,
  Monogram,
  Person,
  PersonStack,
  Wordmark,
  firmInitials,
  personInitials,
  tintForJoin,
} from ".";

// The identity primitives (F-05-T14): Foundations 01 Brand, C-00 firm logo slot, C-28 Presence.

afterEach(cleanup);

describe("initials", () => {
  it("takes a person's first and last initials", () => {
    expect(personInitials("Hannah Leclerc")).toBe("HL");
    expect(personInitials("Margaret Okonkwo")).toBe("MO");
    expect(personInitials("Cole A. Hart")).toBe("CH");
    expect(personInitials("Thomas")).toBe("T");
    expect(personInitials("  simone   baptiste ")).toBe("SB");
    expect(personInitials("")).toBe("?");
  });

  it("takes a firm's first two words", () => {
    expect(firmInitials("Brightwater Hale")).toBe("BH");
    expect(firmInitials("Brightwater Hale LLP")).toBe("BH");
    expect(firmInitials("Granite")).toBe("G");
    expect(firmInitials("")).toBe("?");
  });
});

describe("Wordmark", () => {
  it("is the lowercase word with the posted dot, built in type", () => {
    const { container } = render(<Wordmark size={44} />);
    const mark = screen.getByRole("img", { name: "Accrued" });
    expect(mark.textContent).toBe("accrued");
    expect(mark.style.fontSize).toBe("44px");
    expect(mark.className).toContain("font-medium");
    expect(mark.className).toContain("tracking-[-0.035em]");
    expect(mark.className).toContain("text-espresso");
    const spans = [...container.querySelectorAll("span span span")];
    expect(spans.find((s) => s.textContent === "c")?.className).toContain("tracking-[-0.045em]");
    expect(spans.find((s) => s.textContent === "d")?.className).toContain("tracking-[0]");
    const dot = spans.find((s) => s.textContent === "");
    expect(dot?.className).toContain("size-[0.18em]");
    expect(dot?.className).toContain("rounded-[0.04em]");
    expect(dot?.className).toContain("ml-[0.06em]");
    expect(dot?.className).toContain("bg-green");
  });

  it("never goes under 12px", () => {
    render(<Wordmark size={8} />);
    expect(screen.getByRole("img").style.fontSize).toBe("12px");
  });

  it("takes the fractional 12.5px of the palette footer", () => {
    render(<Wordmark size={12.5} />);
    expect(screen.getByRole("img").style.fontSize).toBe("12.5px");
  });
});

describe("Monogram and AgentAvatar", () => {
  it("draws the espresso tile at each brand size", () => {
    const { container } = render(
      <>
        {MONOGRAM_SIZES.map((size) => (
          <Monogram key={size} size={size} />
        ))}
      </>,
    );
    const tiles = [...container.querySelectorAll("svg[data-glyph='agent-monogram']")];
    expect(tiles.map((t) => t.getAttribute("width"))).toEqual(MONOGRAM_SIZES.map(String));
    expect(tiles.every((t) => t.getAttribute("aria-hidden") === "true")).toBe(true);
    expect(tiles[0]?.querySelector("rect")?.getAttribute("rx")).toBe("28");
    expect(tiles[0]?.querySelector("text")?.textContent).toBe("a");
  });

  it("raises a size under 16 to 16", () => {
    const { container } = render(<Monogram size={10 as 16} />);
    expect(container.querySelector("svg")?.getAttribute("width")).toBe("16");
  });

  it("names itself only when asked", () => {
    render(<Monogram label="Accrued" />);
    expect(screen.getByRole("img", { name: "Accrued" })).toBeTruthy();
  });

  it("is the 16px tile for the Agent, with no initials and no tint", () => {
    const { container } = render(<AgentAvatar label="Accrued Agent" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("16");
    expect(svg?.getAttribute("data-actor")).toBe("agent");
    expect(svg?.getAttribute("data-glyph")).toBe("agent-monogram");
    expect(container.querySelector("[data-person-avatar]")).toBeNull();
    expect(container.textContent).toBe("a");
    expect(screen.getByRole("img", { name: "Accrued Agent" })).toBeTruthy();
  });
});

describe("FirmMark", () => {
  it("draws the firm's initials in a radius-5 tile", () => {
    render(<FirmMark name="Brightwater Hale" />);
    const mark = screen.getByRole("img", { name: "Brightwater Hale" });
    expect(mark.textContent).toBe("BH");
    expect(mark.className).toContain("rounded-prop");
    expect(mark.className).toContain("bg-chip");
    expect(mark.className).toContain("size-[20px]");
    expect(mark.style.fontSize).toBe("8.5px");
  });

  it("scales to the auth card's 34px", () => {
    render(<FirmMark name="Brightwater Hale" size={34} />);
    const mark = screen.getByRole("img");
    expect(mark.className).toContain("size-[34px]");
    expect(mark.style.fontSize).toBe("14.45px");
  });

  it("draws the demo firm's wave mark", () => {
    const { container } = render(<FirmMark name="Brightwater Hale" mark="wave" />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("data-mark")).toBe("wave");
    expect(svg?.getAttribute("aria-label")).toBe("Brightwater Hale");
    expect(container.querySelectorAll("path")).toHaveLength(2);
  });

  it("shows the tenant's uploaded logo in preference to a drawn mark", () => {
    render(<FirmMark name="Brightwater Hale" mark="wave" src="/branding/logo.png" />);
    const img = screen.getByRole("img", { name: "Brightwater Hale" });
    expect(img.tagName).toBe("IMG");
    expect(img.getAttribute("src")).toBe("/branding/logo.png");
  });

  it("never says Accrued, in any form (the portal is white-labelled)", () => {
    const { container } = render(
      <>
        <FirmMark name="Brightwater Hale" />
        <FirmMark name="Brightwater Hale" mark="wave" size={34} />
        <FirmMark name="Brightwater Hale" src="/branding/logo.png" />
      </>,
    );
    expect(container.innerHTML).not.toMatch(/accrued/i);
  });
});

describe("Person", () => {
  it("is an avatar with initials and the name beside it", () => {
    const { container } = render(<Person name="Hannah Leclerc" tint={1} />);
    expect(container.textContent).toBe("HLHannah Leclerc");
    const avatar = container.querySelector("[data-person-avatar]");
    expect(avatar?.getAttribute("aria-hidden")).toBe("true");
    expect(avatar?.className).toContain("bg-viz-p1");
    expect(avatar?.className).toContain("size-[20px]");
    expect(avatar?.className).toContain("rounded-pill");
  });

  it("is named by the person when the name is not drawn", () => {
    render(<Person name="Simone Baptiste" tint={2} showName={false} />);
    const avatar = screen.getByRole("img", { name: "Simone Baptiste" });
    expect(avatar.textContent).toBe("SB");
    expect(avatar.className).toContain("bg-viz-p2");
  });

  it("falls back to the neutral chip with a single initial", () => {
    render(<Person name="Thomas" showName={false} />);
    const avatar = screen.getByRole("img");
    expect(avatar.textContent).toBe("T");
    expect(avatar.className).toContain("bg-chip");
    expect(avatar.getAttribute("data-tint")).toBe("none");
  });

  it("fades the fill when idle and keeps the initials at full ink", () => {
    render(<Person name="Hannah Leclerc" tint={3} idle showName={false} />);
    const avatar = screen.getByRole("img");
    expect(avatar.className).toContain("bg-viz-p3/60");
    expect(avatar.className).toContain("text-ink");
    expect(avatar.className).not.toMatch(/(^|\s)opacity-/);
  });

  it("gives tints in join order, the fifth reusing the first", () => {
    expect([0, 1, 2, 3, 4, 5].map(tintForJoin)).toEqual([1, 2, 3, 4, 1, 2]);
  });
});

describe("PersonStack", () => {
  const NAMES = ["Hannah Leclerc", "Simone Baptiste", "Cole Hart", "Margaret Okonkwo"];

  it("shows at most three then a +n circle, with a 1.5px ring and a 6px overlap", () => {
    const { container } = render(<PersonStack people={NAMES.map((name) => ({ name }))} />);
    const avatars = [...container.querySelectorAll("[data-person-avatar]")];
    expect(avatars.map((a) => a.textContent)).toEqual(["HL", "SB", "CH"]);
    expect(avatars.map((a) => a.getAttribute("data-tint"))).toEqual(["1", "2", "3"]);
    expect(avatars.every((a) => a.className.includes("ring-[1.5px]"))).toBe(true);
    expect(avatars[0]?.className).not.toContain("-ml-[6px]");
    expect(avatars[1]?.className).toContain("-ml-[6px]");
    expect(container.textContent).toContain("+1");
    expect(screen.getByRole("group").getAttribute("aria-label")).toBe(NAMES.join(", "));
  });

  it("has no +n circle when everyone fits", () => {
    const { container } = render(
      <PersonStack people={NAMES.slice(0, 2).map((name) => ({ name }))} />,
    );
    expect(container.textContent).not.toContain("+");
  });
});
