// F-05-T14 (C-06): Pill, Count, Tag, DoneCount and CheckPill. A pill is radius 999 (DEC-124) on its
// variant's tokens, holds nothing but words, a check and a ring, and StatusPill is built on Pill.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CheckPill, Count, DoneCount, PILL_SIZES, PILL_VARIANTS, Pill, Tag } from "./pill";
import { StatusPill, Tick } from "./status";

afterEach(cleanup);

function classes(element: Element | null): string[] {
  return (element?.getAttribute("class") ?? "").split(/\s+/);
}

describe("Pill", () => {
  it.each(PILL_VARIANTS)("draws %s as a pill from tokens", (variant) => {
    render(<Pill variant={variant}>Word</Pill>);
    const pill = screen.getByText("Word");
    expect(classes(pill)).toEqual(
      expect.arrayContaining(["rounded-pill", "inline-flex", "items-center", "whitespace-nowrap"]),
    );
    expect(pill.className).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i);
    expect(pill.className).not.toMatch(/uppercase/);
  });

  it.each(PILL_SIZES)("draws size %s with a height and a type role", (size) => {
    render(<Pill size={size}>Word</Pill>);
    const names = classes(screen.getByText("Word"));
    expect(names.some((c) => /^h-\[\d+px\]$/.test(c))).toBe(true);
    expect(
      names.some((c) => /^text-(pill|pill-card|pill-sm|micro|dense|count|body)$/.test(c)),
    ).toBe(true);
  });

  it("keeps a type role and an ink together (cn knows the roles)", () => {
    render(
      <Pill variant="amber" size="state">
        Word
      </Pill>,
    );
    expect(classes(screen.getByText("Word"))).toEqual(
      expect.arrayContaining(["text-pill", "text-amber-ink", "bg-amber-tint"]),
    );
  });

  it("lets a caller's class override the kit's", () => {
    render(
      <Pill variant="neutral" className="bg-red-tint text-red-ink">
        Word
      </Pill>,
    );
    const names = classes(screen.getByText("Word"));
    expect(names).toEqual(expect.arrayContaining(["bg-red-tint", "text-red-ink"]));
    expect(names).not.toContain("bg-chip");
    expect(names).not.toContain("text-ink-2");
  });

  it("holds a check or a ring before the word, and a chevron after it", () => {
    const { container } = render(
      <>
        <Pill variant="green" check>
          Done
        </Pill>
        <Pill variant="amber" spin>
          Working
        </Pill>
        <Pill size="status">Pick</Pill>
      </>,
    );
    const [check, spin, pick] = [...container.children] as HTMLElement[];
    expect(check?.querySelector("svg")).not.toBeNull();
    expect(spin?.querySelector("svg.motion-spin")).not.toBeNull();
    expect(pick?.querySelector("svg")).not.toBeNull();
    expect(container.querySelectorAll("[aria-hidden='true']").length).toBe(3);
  });

  it("is what StatusPill and Tick draw on", () => {
    render(
      <>
        <StatusPill variant="amber">Status</StatusPill>
        <StatusPill tone="success">Tone</StatusPill>
        <Tick code="MS" />
      </>,
    );
    expect(classes(screen.getByText("Status"))).toEqual(
      expect.arrayContaining(["rounded-pill", "bg-amber-tint", "text-pill"]),
    );
    expect(classes(screen.getByText("Tone"))).toEqual(
      expect.arrayContaining(["bg-green-tint", "text-green-ink"]),
    );
    expect(classes(screen.getByText("MS"))).toEqual(
      expect.arrayContaining(["bg-green", "text-micro", "rounded-pill"]),
    );
  });
});

describe("Count", () => {
  it("is 19 high, 19 wide at least and centred", () => {
    render(<Count value={7} />);
    const count = screen.getByText("7");
    expect(classes(count)).toEqual(
      expect.arrayContaining([
        "h-[19px]",
        "min-w-[19px]",
        "justify-center",
        "bg-chip",
        "text-ink-2",
      ]),
    );
    expect(count.getAttribute("data-tone")).toBe("default");
  });

  it("is red-tint and red ink when bad", () => {
    render(<Count value={16} tone="bad" />);
    const names = classes(screen.getByText("16"));
    expect(names).toEqual(expect.arrayContaining(["bg-red-tint", "text-red-ink"]));
    expect(names).not.toContain("bg-chip");
  });

  it("sits on the deep surface in a Segmented option", () => {
    render(<Count value={7} tone="segment" />);
    const names = classes(screen.getByText("7"));
    expect(names).toEqual(expect.arrayContaining(["bg-surface-deep", "text-ink-2"]));
    expect(names).not.toContain("bg-chip");
  });

  it("groups thousands through format.ts", () => {
    render(<Count value={1204} />);
    expect(screen.getByText("1,204")).toBeTruthy();
  });
});

describe("Tag", () => {
  it("is 23 high on the nested fill with a hair", () => {
    render(<Tag>Category</Tag>);
    expect(classes(screen.getByText("Category"))).toEqual(
      expect.arrayContaining([
        "h-[23px]",
        "bg-nested",
        "text-ink-2",
        "inset-shadow-hair",
        "rounded-pill",
      ]),
    );
  });
});

describe("DoneCount", () => {
  it("is solid green with a check when complete", () => {
    const { container } = render(<DoneCount done={5} total={5} />);
    const pill = screen.getByText("5 of 5");
    expect(classes(pill)).toEqual(
      expect.arrayContaining(["bg-green", "text-on-dark", "h-[21px]"]),
    );
    expect(pill.getAttribute("data-state")).toBe("complete");
    expect(container.querySelector("svg.motion-spin")).toBeNull();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("is neutral with a turning ring when partial", () => {
    const { container } = render(<DoneCount done={4} total={5} />);
    const pill = screen.getByText("4 of 5");
    expect(classes(pill)).toEqual(expect.arrayContaining(["bg-chip", "text-ink-2"]));
    expect(pill.getAttribute("data-state")).toBe("partial");
    expect(container.querySelector("svg.motion-spin")).not.toBeNull();
  });

  it("is neutral and bare when nothing is done, and never complete at zero of zero", () => {
    const { container, rerender } = render(<DoneCount done={0} total={5} />);
    expect(screen.getByText("0 of 5").getAttribute("data-state")).toBe("none");
    expect(container.querySelector("svg")).toBeNull();
    rerender(<DoneCount done={0} total={0} />);
    expect(screen.getByText("0 of 0").getAttribute("data-state")).toBe("none");
  });
});

describe("CheckPill", () => {
  it("is white on e1 with an ink check and an ink-2 count when approved", () => {
    const { container } = render(<CheckPill approved count={3} />);
    const pill = screen.getByText("3");
    expect(classes(pill)).toEqual(
      expect.arrayContaining(["bg-card", "shadow-e1", "text-ink-2", "h-[21px]"]),
    );
    expect(classes(container.querySelector("svg"))).toContain("text-ink");
    expect(pill.textContent).toContain("Approved");
    expect(pill.getAttribute("data-state")).toBe("approved");
  });

  it("is a bare ink-3 check, 21 square, when not approved", () => {
    const { container } = render(<CheckPill approved={false} count={3} />);
    const pill = screen.getByRole("img", { name: "Not approved" });
    expect(classes(pill)).toEqual(expect.arrayContaining(["w-[21px]", "h-[21px]", "bg-card"]));
    expect(pill.textContent).toBe("");
    expect(classes(container.querySelector("svg"))).toContain("text-ink-3");
  });

  it("is never green", () => {
    render(
      <>
        <CheckPill approved count={1} data-testid="a" />
        <CheckPill approved={false} data-testid="b" />
      </>,
    );
    for (const id of ["a", "b"]) {
      expect(screen.getByTestId(id).outerHTML).not.toMatch(/green/);
    }
  });
});
