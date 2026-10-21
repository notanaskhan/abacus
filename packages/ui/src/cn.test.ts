// F-05-T14: cn() knows the type roles. tailwind-merge reads an unknown `text-*` class as a colour,
// so the status kit (F-05-T12) joined classes with clsx to keep text-pill and text-amber-ink.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { cn } from "./cn";
import { textRoles } from "./tokens/tokens";

const THEME = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "theme.css"), "utf8");
// `--text-body: 13px;`, not `--text-body--line-height` and not the `--text-*: initial` reset.
const THEME_ROLES = [...THEME.matchAll(/^\s*--text-([a-z0-9-]+?)\s*:\s*[0-9.]+px\s*;/gm)].flatMap(
  (m) => (m[1] === undefined ? [] : [m[1]]),
);

describe("cn", () => {
  it("lets a later utility override an earlier one", () => {
    expect(cn("px-2", "px-3")).toBe("px-3");
    expect(cn("bg-card", "bg-nested")).toBe("bg-nested");
  });

  it("drops falsy values like clsx", () => {
    expect(cn("a", false, undefined, null, "b")).toBe("a b");
  });

  it("keeps a type role and a text colour together, in either order", () => {
    expect(cn("text-meta", "text-ink-2")).toBe("text-meta text-ink-2");
    expect(cn("text-ink-2", "text-meta")).toBe("text-ink-2 text-meta");
    expect(cn("text-pill", "text-amber-ink")).toBe("text-pill text-amber-ink");
    expect(cn("text-body", "text-on-dark")).toBe("text-body text-on-dark");
    expect(cn("text-nav", "text-ink")).toBe("text-nav text-ink");
    expect(cn("text-dashboard", "text-red-ink")).toBe("text-dashboard text-red-ink");
  });

  it("lets a later type role replace an earlier one", () => {
    expect(cn("text-body", "text-meta")).toBe("text-meta");
    expect(cn("text-btn", "text-btn-sm")).toBe("text-btn-sm");
  });

  it("lets a later colour replace an earlier colour", () => {
    expect(cn("text-ink-2", "text-ink")).toBe("text-ink");
    expect(cn("text-meta text-ink-3", "text-amber-ink")).toBe("text-meta text-amber-ink");
  });

  it("knows every role theme.css defines, and no more", () => {
    expect(Object.keys(textRoles).sort()).toEqual([...THEME_ROLES].sort());
    for (const role of THEME_ROLES) {
      expect(cn(`text-${role}`, "text-ink-2"), role).toBe(`text-${role} text-ink-2`);
      expect(cn("text-ink-2", `text-${role}`), role).toBe(`text-ink-2 text-${role}`);
    }
  });
});
