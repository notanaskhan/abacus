import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { App } from "./App";

// Tell React this is a test environment so act() flushes updates synchronously.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

afterEach(() => {
  document.body.innerHTML = "";
});

describe("App", () => {
  it("renders the product name", () => {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);

    act(() => {
      root.render(<App />);
    });

    expect(container.querySelector("h1")?.textContent).toBe("Abacus");
    act(() => {
      root.unmount();
    });
  });
});
