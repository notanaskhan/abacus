import { act, cleanup, render, renderHook, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveDot, Pulse, Reveal, Spinner, TypingDots } from "./components/motion";
import { REDUCED_MOTION_QUERY, useReducedMotion, useWordReveal, wordsOf } from "./motion";

// The motion primitives and useReducedMotion (F-05-T14). The browser-level proof, that
// document.getAnimations() is empty with reduced motion emulated, is the Playwright check in
// apps/web/e2e/components.spec.ts; jsdom has no Web Animations, so here the proof is the DOM:
// under the preference no component carries an animation class or an animation timing.

type Listener = () => void;

/** A matchMedia that answers the reduced-motion query and lets the test flip it. */
function mockReducedMotion(initial: boolean): { set: (value: boolean) => void } {
  let matches = initial;
  const listeners = new Set<Listener>();
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      get matches() {
        return query === REDUCED_MOTION_QUERY && matches;
      },
      media: query,
      addEventListener: (_: string, l: Listener) => listeners.add(l),
      removeEventListener: (_: string, l: Listener) => listeners.delete(l),
    })),
  );
  return {
    set(value) {
      matches = value;
      act(() => {
        listeners.forEach((l) => {
          l();
        });
      });
    },
  };
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Every element that would start an animation: a motion utility class or an animation timing. */
function animated(root: HTMLElement): Element[] {
  return [...root.querySelectorAll("*")].filter((el) => {
    const style = (el as HTMLElement).style;
    return /\bmotion-/.test(el.getAttribute("class") ?? "") || style.animationDelay !== "";
  });
}

function Everything({ still = false }: { still?: boolean }): React.JSX.Element {
  return (
    <div>
      <Spinner label="Loading" still={still} />
      <Spinner label="Loading" size={10} showLabel={false} still={still} />
      <Pulse index={2} still={still}>
        bar
      </Pulse>
      <Pulse rhythm="breathe" still={still} />
      <LiveDot still={still} />
      <Reveal delay={260} still={still}>
        block
      </Reveal>
      <TypingDots label="Typing" still={still} />
    </div>
  );
}

describe("useReducedMotion", () => {
  it("is false without matchMedia (jsdom, the server)", () => {
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it("reads the system preference", () => {
    mockReducedMotion(true);
    expect(renderHook(() => useReducedMotion()).result.current).toBe(true);
    cleanup();
    mockReducedMotion(false);
    expect(renderHook(() => useReducedMotion()).result.current).toBe(false);
  });

  it("follows the preference while mounted", () => {
    const media = mockReducedMotion(false);
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    media.set(true);
    expect(result.current).toBe(true);
    media.set(false);
    expect(result.current).toBe(false);
  });
});

describe("reduced motion renders no animation at all", () => {
  it("animates when motion is allowed", () => {
    mockReducedMotion(false);
    const { container } = render(<Everything />);
    expect(animated(container).length).toBeGreaterThanOrEqual(6);
    expect(container.querySelector("svg.motion-spin")).not.toBeNull();
    expect(container.querySelector(".motion-pulse")).not.toBeNull();
    expect(container.querySelector(".motion-breathe")).not.toBeNull();
    expect(container.querySelector(".motion-reveal")).not.toBeNull();
    expect(container.querySelectorAll(".motion-typing")).toHaveLength(3);
  });

  it("staggers rows by 70ms and typing dots by 150ms", () => {
    mockReducedMotion(false);
    const { container } = render(<Everything />);
    const pulse = container.querySelector<HTMLElement>("[data-pulse='skeleton']");
    expect(pulse?.style.animationDelay).toBe("140ms");
    const dots = [...container.querySelectorAll<HTMLElement>(".motion-typing")];
    expect(dots.map((d) => d.style.animationDelay)).toEqual(["", "150ms", "300ms"]);
    expect(container.querySelector<HTMLElement>("[data-reveal]")?.style.animationDelay).toBe(
      "260ms",
    );
  });

  it("carries no animation class or timing under the preference", () => {
    mockReducedMotion(true);
    const { container } = render(<Everything />);
    expect(animated(container)).toEqual([]);
    expect(container.querySelectorAll("[data-spinner='still']")).toHaveLength(2);
    expect(container.querySelector("[data-reveal='still']")).not.toBeNull();
    expect(container.querySelector("[data-typing='still']")).not.toBeNull();
    // jsdom has no Web Animations; a browser reports none either.
    const doc: unknown = document;
    expect((doc as { getAnimations?: () => unknown[] }).getAnimations?.() ?? []).toEqual([]);
  });

  it("carries none with `still`, whatever the preference", () => {
    mockReducedMotion(false);
    const { container } = render(<Everything still />);
    expect(animated(container)).toEqual([]);
  });

  it("stops at once when the preference turns on", () => {
    const media = mockReducedMotion(false);
    const { container } = render(<Everything />);
    expect(animated(container).length).toBeGreaterThan(0);
    media.set(true);
    expect(animated(container)).toEqual([]);
  });

  it("keeps the same size and the same words when still", () => {
    mockReducedMotion(true);
    render(<Spinner label="Loading" size={15} />);
    const ring = screen.getByRole("status").querySelector("svg");
    expect(ring?.getAttribute("width")).toBe("15");
    expect(screen.getByRole("status").textContent).toBe("Loading");
  });
});

describe("Spinner", () => {
  it("is named, and its label can be for assistive technology only", () => {
    mockReducedMotion(false);
    render(<Spinner label="Signing you in…" showLabel={false} />);
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Signing you in…");
    expect(status.querySelector(".sr-only")?.textContent).toBe("Signing you in…");
  });

  it("draws a 28% arc on a faint track", () => {
    mockReducedMotion(false);
    const { container } = render(<Spinner label="Loading" size={15} />);
    const [track, arc] = container.querySelectorAll("circle");
    expect(track?.getAttribute("class")).toContain("stroke-rule");
    const [dash, gap] = (arc?.getAttribute("stroke-dasharray") ?? "").split(" ").map(Number);
    expect((dash ?? 0) / (gap ?? 1)).toBeCloseTo(0.28, 5);
    expect(arc?.getAttribute("stroke-linecap")).toBe("round");
  });
});

describe("useWordReveal", () => {
  const TEXT = "I’ll start with read-only discovery.";

  /** Advance in 20ms steps: each word schedules the next once it has rendered. */
  function words(n: number): void {
    for (let i = 0; i < n; i++) {
      act(() => {
        vi.advanceTimersByTime(20);
      });
    }
  }

  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("splits a text into words that join back to it", () => {
    expect(wordsOf("a b  c")).toEqual(["a ", "b  ", "c"]);
    expect(wordsOf("")).toEqual([]);
    expect(wordsOf(TEXT).join("")).toBe(TEXT);
  });

  it("reveals one word every 20ms", () => {
    mockReducedMotion(false);
    const { result } = renderHook(() => useWordReveal(TEXT));
    expect(result.current).toEqual({ text: "", done: false });
    words(1);
    expect(result.current.text).toBe("I’ll ");
    words(2);
    expect(result.current.text).toBe("I’ll start with ");
    words(2);
    expect(result.current).toEqual({ text: TEXT, done: true });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("shows the whole text at once, with no timer, under reduced motion", () => {
    mockReducedMotion(true);
    const { result } = renderHook(() => useWordReveal(TEXT));
    expect(result.current).toEqual({ text: TEXT, done: true });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("starts again when the text changes", () => {
    mockReducedMotion(false);
    const { result, rerender } = renderHook(({ text }) => useWordReveal(text), {
      initialProps: { text: TEXT },
    });
    words(10);
    expect(result.current.done).toBe(true);
    rerender({ text: "Another line of text." });
    expect(result.current).toEqual({ text: "", done: false });
    words(1);
    expect(result.current.text).toBe("Another ");
  });
});

describe("motion.css", () => {
  const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "motion.css"), "utf8");
  const frames = (name: string): string =>
    new RegExp(`@keyframes ${name} \\{([\\s\\S]*?)\\n\\}`).exec(css)?.[1] ?? "";

  it("pulses 1 to .55 to 1 and breathes 1 to .35 to 1 (C-20)", () => {
    expect(frames("ac-pulse")).toMatch(/100% \{\s*opacity: 1;/);
    expect(frames("ac-pulse")).toMatch(/50% \{\s*opacity: 0\.55;/);
    expect(frames("ac-breathe")).toMatch(/50% \{\s*opacity: 0\.35;/);
  });

  it("lifts the typing dots 2px at the top of the beat (C-10)", () => {
    expect(frames("ac-typing")).toMatch(/40% \{\s*opacity: 1;\s*transform: translateY\(-2px\);/);
  });

  it("clears animation delays under reduced motion, not only durations", () => {
    expect(css).toMatch(/animation-delay: 0s !important/);
  });
});
