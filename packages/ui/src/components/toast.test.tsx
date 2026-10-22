import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toast, ToastHost } from "./toast";
import { DEFAULT_MS, LEAVE_MS, createToast, createToastStore } from "./toast-store";

// The C-21 host and toast (F-05-T21): roles, the action and close buttons, hover pause, and the
// still form under reduced motion.

function reduceMotion(reduce: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: reduce && query.includes("reduce"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      onchange: null,
      dispatchEvent: () => false,
    }),
  });
}

beforeEach(() => {
  reduceMotion(false);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ToastHost", () => {
  it("renders the store's toasts with their roles", () => {
    const store = createToastStore();
    const toast = createToast(store);
    render(<ToastHost store={store} />);
    act(() => {
      toast.show("Approved 3 adjustments");
      toast.show({ kind: "error", text: "Couldn’t connect to Cascadia Bank" });
    });
    expect(screen.getByRole("status").textContent).toContain("Approved 3 adjustments");
    expect(screen.getByRole("alert").textContent).toContain("Couldn’t connect to Cascadia Bank");
    expect(screen.getByRole("alert").getAttribute("aria-live")).toBe("assertive");
  });

  it("sits fixed at bottom 24, or absolute when contained", () => {
    const store = createToastStore();
    const { container, rerender } = render(<ToastHost store={store} />);
    const host = container.querySelector("[data-toast-host]");
    expect(host?.classList.contains("fixed")).toBe(true);
    expect((host as HTMLElement).style.bottom).toBe("24px");
    rerender(<ToastHost store={store} contained />);
    expect(container.querySelector("[data-toast-host]")?.classList.contains("absolute")).toBe(
      true,
    );
  });

  it("the action dismisses the toast, then runs the caller's command", () => {
    const store = createToastStore();
    const toast = createToast(store);
    const retry = vi.fn();
    render(<ToastHost store={store} />);
    act(() => {
      toast.show({ kind: "error", text: "Couldn’t connect", action: "Retry", onAction: retry });
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(store.list()[0]?.leaving).toBe(true);
  });

  it("the close button dismisses", () => {
    const store = createToastStore();
    const toast = createToast(store);
    render(<ToastHost store={store} />);
    act(() => {
      toast.show({ kind: "error", text: "Couldn’t connect" });
    });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    act(() => {
      vi.advanceTimersByTime(LEAVE_MS);
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("hovering pauses the timer", () => {
    const store = createToastStore();
    const toast = createToast(store);
    render(<ToastHost store={store} />);
    act(() => {
      toast.show("Saved");
    });
    fireEvent.mouseEnter(screen.getByRole("status"));
    act(() => {
      vi.advanceTimersByTime(DEFAULT_MS * 3);
    });
    expect(store.list()[0]?.leaving).toBe(false);
    fireEvent.mouseLeave(screen.getByRole("status"));
    act(() => {
      vi.advanceTimersByTime(DEFAULT_MS);
    });
    expect(store.list()[0]?.leaving).toBe(true);
  });
});

describe("Toast", () => {
  it("draws a 36px espresso pill with the kind's glyph", () => {
    const { container } = render(
      <Toast kind="warning" text="Uploaded 3 of 4 files" action="View" />,
    );
    const pill = container.querySelector("[data-toast]");
    expect(pill?.getAttribute("data-toast")).toBe("warning");
    for (const name of ["h-9", "rounded-pill", "bg-espresso", "text-on-dark", "shadow-e3"]) {
      expect(pill?.classList.contains(name)).toBe(true);
    }
    expect(screen.getByRole("button", { name: "View" })).toBeTruthy();
  });

  it("rises and turns its spinner, and does neither under reduced motion", () => {
    const { container, rerender } = render(<Toast kind="running" text="Uploading 4 files…" />);
    expect(container.querySelector("[data-toast]")?.classList.contains("motion-toast-in")).toBe(
      true,
    );
    expect(container.querySelector(".motion-spin")).not.toBeNull();
    reduceMotion(true);
    rerender(<Toast kind="running" text="Uploading 4 files…" still />);
    expect(container.querySelector("[data-toast]")?.classList.contains("motion-toast-in")).toBe(
      false,
    );
    expect(container.querySelector(".motion-spin")).toBeNull();
  });
});
