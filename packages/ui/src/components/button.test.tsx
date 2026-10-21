// F-05-T14 (C-00, Component Sheet E): Button and IconButton. A control is a pill (DEC-124), draws
// every variant and size from tokens, holds a forced state without a pointer, keeps a 24px hit
// area under 24px, and a label that opens a dialog ends with U+2026.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  BUTTON_SIZES,
  BUTTON_VARIANTS,
  Button,
  type ButtonSize,
  type ButtonVariant,
  ICON_BUTTON_VARIANTS,
  IconButton,
} from "./button";

afterEach(cleanup);

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

const FILL: Record<ButtonVariant, string[]> = {
  primary: ["bg-espresso", "text-on-dark", "shadow-cta", "font-medium"],
  secondary: ["bg-card", "text-ink", "shadow-e1"],
  tonal: ["bg-chip", "text-ink"],
  ghost: ["text-ink-2"],
  destructive: ["bg-card", "text-red-ink", "shadow-e1", "font-medium"],
  success: ["bg-green", "text-on-dark", "shadow-cta", "font-medium"],
  link: ["text-ink-2"],
};

describe("Button", () => {
  it.each(BUTTON_VARIANTS)("draws %s from tokens, as a pill", (variant) => {
    render(<Button variant={variant}>Word</Button>);
    const button = screen.getByRole("button", { name: "Word" });
    expect(classes(button)).toEqual(expect.arrayContaining([...FILL[variant], "rounded-pill"]));
    expect(button.className).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i);
    expect(button.className).not.toMatch(/rounded-\[/);
    expect(button.getAttribute("type")).toBe("button");
  });

  const HEIGHT: Record<ButtonSize, string> = {
    xs: "h-[23px]",
    sm: "h-[28px]",
    md: "h-[30px]",
    lg: "h-[32px]",
    footer: "h-[34px]",
    xl: "h-[36px]",
  };

  it.each(BUTTON_SIZES)("sets the height and type role of size %s", (size) => {
    render(<Button size={size}>Word</Button>);
    const button = screen.getByRole("button");
    expect(classes(button)).toContain(HEIGHT[size]);
    expect(button.className).toMatch(/text-(meta|btn-sm|body|btn)\b/);
  });

  it("is a primary of 30 pixels by default", () => {
    render(<Button>Word</Button>);
    const button = screen.getByRole("button");
    expect(button.getAttribute("data-variant")).toBe("primary");
    expect(button.getAttribute("data-size")).toBe("md");
    expect(classes(button)).toContain("h-[30px]");
  });

  it("keeps the type role and the ink together (cn knows the roles)", () => {
    render(<Button variant="primary">Word</Button>);
    const button = screen.getByRole("button");
    expect(classes(button)).toEqual(expect.arrayContaining(["text-body", "text-on-dark"]));
  });

  it("lets a caller's class override the kit's", () => {
    render(
      <Button variant="link" className="text-ink">
        Word
      </Button>,
    );
    const names = classes(screen.getByRole("button"));
    expect(names).toContain("text-ink");
    expect(names).not.toContain("text-ink-2");
  });

  it("presses and fades with the shared utilities", () => {
    render(<Button>Word</Button>);
    expect(classes(screen.getByRole("button"))).toEqual(
      expect.arrayContaining(["press", "active:pressed", "data-[force=pressed]:pressed"]),
    );
  });

  it("gives a 24px hit area to the 23px size and to a link", () => {
    render(
      <>
        <Button size="xs">Small</Button>
        <Button variant="link">Link</Button>
        <Button>Normal</Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Small" }).className).toContain(
      "before:-inset-y-px",
    );
    expect(screen.getByRole("button", { name: "Link" }).className).toContain(
      "before:-inset-y-[3px]",
    );
    expect(screen.getByRole("button", { name: "Normal" }).className).not.toContain("before:");
  });

  it("draws a registry icon before and after the label", () => {
    const { container } = render(
      <Button icon="check" iconAfter="arrow-right">
        Word
      </Button>,
    );
    const icons = [...container.querySelectorAll("svg")].map((svg) => svg.dataset["icon"]);
    expect(icons).toEqual(["check", "arrow-right"]);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  describe("forceState", () => {
    it.each(["hover", "focus", "pressed"] as const)("holds %s without a pointer", (state) => {
      render(<Button forceState={state}>Word</Button>);
      expect(screen.getByRole("button").getAttribute("data-force")).toBe(state);
    });

    it("holds nothing by default", () => {
      render(<Button>Word</Button>);
      expect(screen.getByRole("button").hasAttribute("data-force")).toBe(false);
    });
  });

  describe("loading", () => {
    it.each([true, false])("shows a ring in place of the icon (forced: %s)", (forced) => {
      const { container } = render(
        <Button
          icon="check"
          {...(forced ? { forceState: "loading" as const } : { loading: true })}
        >
          Saving
        </Button>,
      );
      const button = screen.getByRole("button", { name: "Saving" });
      expect(button.getAttribute("aria-busy")).toBe("true");
      expect(container.querySelector("[data-icon]")).toBeNull();
      expect(container.querySelector("svg.motion-spin")).not.toBeNull();
    });

    it("ignores clicks while loading and takes them otherwise", () => {
      const onClick = vi.fn();
      const { rerender } = render(
        <Button loading onClick={onClick}>
          Saving
        </Button>,
      );
      fireEvent.click(screen.getByRole("button"));
      expect(onClick).not.toHaveBeenCalled();
      rerender(<Button onClick={onClick}>Save</Button>);
      fireEvent.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledOnce();
    });
  });

  it("does not click when disabled", () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Word
      </Button>,
    );
    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(classes(button)).toEqual(
      expect.arrayContaining([
        "disabled:pointer-events-none",
        "disabled:bg-nested",
        "disabled:text-ink-4",
      ]),
    );
  });

  it("renders its child with the classes under asChild", () => {
    render(
      <Button asChild variant="secondary">
        <a href="/x">Go</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Go" });
    expect(classes(link)).toEqual(expect.arrayContaining(["bg-card", "rounded-pill"]));
    expect(link.hasAttribute("type")).toBe(false);
  });

  describe("opensDialog (plan 04 rule 9, L3)", () => {
    it("accepts a label that ends with U+2026 and says it opens a dialog", () => {
      render(<Button opensDialog>Rename…</Button>);
      expect(screen.getByRole("button", { name: "Rename…" }).getAttribute("aria-haspopup")).toBe(
        "dialog",
      );
    });

    it.each(["Rename", "Rename...", "Rename. . ."])("refuses the label %j", (label) => {
      expect(() => render(<Button opensDialog>{label}</Button>)).toThrow(/U\+2026/);
    });

    it("reads the label through elements", () => {
      expect(() =>
        render(
          <Button opensDialog>
            <span>Rename</span>
          </Button>,
        ),
      ).toThrow(/U\+2026/);
      cleanup();
      render(
        <Button opensDialog>
          <span>Rename</span>…
        </Button>,
      );
      expect(screen.getByRole("button")).toBeTruthy();
    });

    it("asserts nothing without the prop", () => {
      expect(() => render(<Button>Rename</Button>)).not.toThrow();
      expect(screen.getByRole("button").hasAttribute("aria-haspopup")).toBe(false);
    });
  });
});

describe("IconButton", () => {
  it("is named by its label and draws a registry icon", () => {
    const { container } = render(<IconButton icon="pencil" label="Edit" />);
    const button = screen.getByRole("button", { name: "Edit" });
    expect(button.getAttribute("title")).toBe("Edit");
    expect(container.querySelector("[data-icon='pencil']")).not.toBeNull();
  });

  const SIZE = { white: "size-[28px]", fill: "size-[30px]", dark: "size-[29px]" } as const;
  it.each(ICON_BUTTON_VARIANTS)("draws %s as a round control", (variant) => {
    render(<IconButton variant={variant} icon="x" label="Close" />);
    const names = classes(screen.getByRole("button"));
    expect(names).toEqual(expect.arrayContaining(["rounded-pill", SIZE[variant]]));
    expect(names.join(" ")).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i);
  });

  it("is 28 white on e1, 30 nav-fill, 29 espresso", () => {
    render(
      <>
        <IconButton icon="pencil" label="White" />
        <IconButton variant="fill" icon="x" label="Fill" />
        <IconButton variant="dark" icon="plus" label="Dark" />
      </>,
    );
    expect(classes(screen.getByLabelText("White"))).toEqual(
      expect.arrayContaining(["bg-card", "shadow-e1"]),
    );
    expect(classes(screen.getByLabelText("Fill"))).toContain("bg-nav-fill");
    expect(classes(screen.getByLabelText("Dark"))).toEqual(
      expect.arrayContaining(["bg-espresso", "text-on-dark", "shadow-cta"]),
    );
  });

  it("holds a forced state and loads", () => {
    const { container } = render(<IconButton icon="pencil" label="Edit" forceState="loading" />);
    const button = screen.getByRole("button", { name: "Edit" });
    expect(button.getAttribute("data-force")).toBe("loading");
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector("[data-icon]")).toBeNull();
  });

  it("asserts the ellipsis on an icon that opens a dialog", () => {
    render(<IconButton icon="pencil" label="Rename…" opensDialog />);
    expect(screen.getByRole("button", { name: "Rename…" }).getAttribute("aria-haspopup")).toBe(
      "dialog",
    );
    cleanup();
    expect(() => render(<IconButton icon="pencil" label="Rename" opensDialog />)).toThrow(
      /U\+2026/,
    );
  });

  it("ignores clicks while loading", () => {
    const onClick = vi.fn();
    render(<IconButton icon="pencil" label="Edit" loading onClick={onClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
